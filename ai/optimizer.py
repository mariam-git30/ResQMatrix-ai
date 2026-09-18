"""Local multi-emergency resource matching and optimization prototype."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Iterable, Mapping

from ai.priority_engine import PriorityEngine, rank_emergencies
from services.distance_service import haversine_distance
from services.eta_service import estimated_eta_minutes

from .resource_matcher import (
    COMPATIBILITY_MATRIX,
    compatible_types,
    matching_resources,
)


OPTIMIZATION_WEIGHTS: dict[str, float] = {
    "priority": 0.25,
    "compatibility": 0.15,
    "proximity": 0.12,
    "eta": 0.13,
    "availability": 0.10,
    "scarcity": 0.05,
    "fairness": 0.05,
    "cost": 0.05,
    "risk": 0.10,
}

DEMAND_RULES: dict[str, dict[str, float]] = {
    # These coefficients are deliberately simple prototype estimates.
    "ROAD_ACCIDENT": {
        "base": 1,
        "injured_divisor": 5,
        "critical_multiplier": 2,
    },
    "FIRE": {
        "base": 1,
        "severity_divisor": 45,
        "people_divisor": 250,
    },
    "FLOOD": {
        "base": 1,
        "severity_divisor": 50,
        "people_divisor": 300,
    },
    "BUILDING_COLLAPSE": {
        "base": 1,
        "injured_divisor": 5,
        "critical_multiplier": 2,
    },
    "MEDICAL": {
        "base": 1,
        "injured_divisor": 4,
        "critical_multiplier": 2,
    },
    "LANDSLIDE": {
        "base": 1,
        "injured_divisor": 6,
        "critical_multiplier": 2,
    },
    "CYCLONE": {
        "base": 1,
        "severity_divisor": 60,
        "people_divisor": 400,
    },
    "CHEMICAL": {
        "base": 1,
        "injured_divisor": 6,
        "critical_multiplier": 2,
    },
    "OTHER": {"base": 1},
}

DEFAULT_OPTIMIZATION_CONFIG: dict[str, Any] = {
    "weights": OPTIMIZATION_WEIGHTS,
    "demand_rules": DEMAND_RULES,
    "max_demand_per_type": 10,
    "proximity_reference_km": 100.0,
    "eta_reference_minutes": 180.0,
    "max_distance_km": 750.0,
    "max_eta_minutes": 720.0,
    "cost_reference": 5000.0,
    "min_reserve_quantity": 0,
    "speeds_kmh": {},
}

RESOURCE_SPEEDS_KMH: dict[str, float] = {
    "AMBULANCE": 40.0,
    "FIRE_ENGINE": 35.0,
    "RESCUE_TEAM": 30.0,
    "RESCUE_BOAT": 15.0,
    "MEDICAL_TEAM": 30.0,
    "HELICOPTER": 120.0,
}


def _value(record: Mapping[str, Any], key: str, default: Any = None) -> Any:
    try:
        return record[key]
    except (KeyError, IndexError, TypeError):
        return default


def _number(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


def _copy_config(config: Mapping[str, Any] | None) -> dict[str, Any]:
    merged = {
        "weights": dict(DEFAULT_OPTIMIZATION_CONFIG["weights"]),
        "demand_rules": {
            key: dict(value)
            for key, value in DEFAULT_OPTIMIZATION_CONFIG["demand_rules"].items()
        },
        "max_demand_per_type": DEFAULT_OPTIMIZATION_CONFIG["max_demand_per_type"],
        "proximity_reference_km": DEFAULT_OPTIMIZATION_CONFIG["proximity_reference_km"],
        "eta_reference_minutes": DEFAULT_OPTIMIZATION_CONFIG["eta_reference_minutes"],
        "speeds_kmh": dict(DEFAULT_OPTIMIZATION_CONFIG["speeds_kmh"]),
    }
    if not config:
        return merged
    if isinstance(config.get("weights"), Mapping):
        merged["weights"].update(config["weights"])
    if isinstance(config.get("demand_rules"), Mapping):
        for key, rule in config["demand_rules"].items():
            if isinstance(rule, Mapping):
                merged["demand_rules"][key] = {
                    **merged["demand_rules"].get(key, {}),
                    **rule,
                }
    for key in (
        "max_demand_per_type",
        "proximity_reference_km",
        "eta_reference_minutes",
        "max_distance_km",
        "max_eta_minutes",
        "cost_reference",
        "min_reserve_quantity",
    ):
        if key in config:
            merged[key] = config[key]
    if isinstance(config.get("speeds_kmh"), Mapping):
        merged["speeds_kmh"].update(config["speeds_kmh"])
    return merged


class ResourceOptimizer:
    """Greedy global optimizer with explicit quantity and fairness tracking."""

    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        self.config = _copy_config(config)
        self.weights = {
            name: max(0.0, _number(value))
            for name, value in self.config["weights"].items()
        }
        self.max_demand_per_type = max(
            1,
            int(_number(self.config["max_demand_per_type"], 10)),
        )
        self.proximity_reference_km = max(
            1.0,
            _number(self.config["proximity_reference_km"], 100.0),
        )
        self.eta_reference_minutes = max(
            1.0,
            _number(self.config["eta_reference_minutes"], 180.0),
        )
        self.max_distance_km = max(1.0, _number(self.config.get("max_distance_km"), 750.0))
        self.max_eta_minutes = max(1.0, _number(self.config.get("max_eta_minutes"), 720.0))
        self.cost_reference = max(1.0, _number(self.config.get("cost_reference"), 5000.0))
        self.min_reserve_quantity = max(0, int(_number(self.config.get("min_reserve_quantity"), 0)))
        # User-entered weights are normalized so they remain comparable.
        total_weight = sum(self.weights.values())
        if total_weight > 0:
            self.weights = {key: value / total_weight for key, value in self.weights.items()}
        self.priority_engine = PriorityEngine()

    def estimate_demand(self, emergency: Mapping[str, Any]) -> dict[str, int]:
        """Estimate units per compatible resource type using prototype rules."""
        emergency_type = str(_value(emergency, "type", "OTHER")).upper()
        rule = self.config["demand_rules"].get(
            emergency_type,
            self.config["demand_rules"]["OTHER"],
        )
        estimate = _number(rule.get("base"), 1.0)
        if "injured_divisor" in rule:
            estimate += (
                _number(_value(emergency, "injured")) / max(
                    _number(rule["injured_divisor"], 1.0),
                    1.0,
                )
            )
            estimate += _number(_value(emergency, "critical_injured")) * _number(
                rule.get("critical_multiplier"),
                1.0,
            ) / max(_number(rule.get("injured_divisor"), 1.0), 1.0)
        if "severity_divisor" in rule:
            estimate += _number(_value(emergency, "severity")) / max(
                _number(rule["severity_divisor"], 1.0),
                1.0,
            )
        if "people_divisor" in rule:
            estimate += _number(_value(emergency, "people_affected")) / max(
                _number(rule["people_divisor"], 1.0),
                1.0,
            )
        units = min(self.max_demand_per_type, max(1, math.ceil(estimate)))
        return {
            resource_type: units
            for resource_type in compatible_types(emergency_type)
        }

    def optimize(
        self,
        emergencies: Iterable[Mapping[str, Any]],
        resources: Iterable[Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Optimize all active emergencies together without database writes."""
        active = [
            emergency
            for emergency in emergencies
            if str(_value(emergency, "status", "")).upper()
            in {"ACTIVE", "IN_PROGRESS"}
        ]
        resource_list = list(resources)
        priority_results = rank_emergencies(active, resource_list, engine=self.priority_engine)
        priority_by_id = {
            result["emergency_id"]: result for result in priority_results
        }
        ranked_active = sorted(
            active,
            key=lambda item: priority_by_id.get(_value(item, "id"), {}).get(
                "priority_score",
                0,
            ),
            reverse=True,
        )
        demand_by_emergency = {
            _value(emergency, "id"): self.estimate_demand(emergency)
            for emergency in ranked_active
        }
        total_demand_by_type: dict[str, int] = defaultdict(int)
        for demand in demand_by_emergency.values():
            for resource_type, quantity in demand.items():
                total_demand_by_type[resource_type] += quantity

        remaining_by_resource = {
            _value(resource, "id"): max(
                0,
                min(
                    int(_number(_value(resource, "available_quantity"))),
                    int(_number(_value(resource, "quantity"))),
                ) - self.min_reserve_quantity,
            )
            for resource in resource_list
        }
        assigned_by_emergency: dict[Any, dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        recommendations_by_key: dict[tuple[Any, Any], dict[str, Any]] = {}
        emergency_by_id = {
            _value(emergency, "id"): emergency for emergency in ranked_active
        }

        while True:
            candidates: list[dict[str, Any]] = []
            remaining_by_type: dict[str, int] = defaultdict(int)
            for resource in resource_list:
                resource_id = _value(resource, "id")
                resource_type = str(_value(resource, "type", "")).upper()
                remaining_by_type[resource_type] += remaining_by_resource.get(
                    resource_id,
                    0,
                )
            for emergency in ranked_active:
                emergency_id = _value(emergency, "id")
                for resource in matching_resources(emergency, resource_list):
                    resource_id = _value(resource, "id")
                    remaining_quantity = remaining_by_resource.get(resource_id, 0)
                    resource_type = str(_value(resource, "type", "")).upper()
                    remaining_demand = demand_by_emergency[emergency_id].get(
                        resource_type,
                        0,
                    ) - assigned_by_emergency[emergency_id].get(resource_type, 0)
                    if remaining_quantity <= 0 or remaining_demand <= 0:
                        continue
                    try:
                        candidate = self._candidate(
                            emergency,
                            resource,
                            priority_by_id[emergency_id],
                            remaining_quantity,
                            total_demand_by_type,
                            remaining_by_resource,
                            remaining_by_type,
                            assigned_by_emergency,
                            demand_by_emergency,
                            ranked_active,
                        )
                    except ValueError as exc:
                        if str(exc) in {"candidate_out_of_range", "candidate_eta_too_high"}:
                            continue
                        raise
                    candidates.append(candidate)
            if not candidates:
                break
            selected = max(
                candidates,
                key=lambda candidate: (
                    candidate["match_score"],
                    candidate["priority_score"],
                    -candidate["distance_km"]
                    if candidate["distance_km"] is not None
                    else -float("inf"),
                    -candidate["resource_id"],
                ),
            )
            emergency_id = selected["emergency_id"]
            resource_id = selected["resource_id"]
            resource_type = selected["resource_type"]
            remaining_by_resource[resource_id] -= 1
            assigned_by_emergency[emergency_id][resource_type] += 1
            key = (emergency_id, resource_id)
            if key not in recommendations_by_key:
                recommendations_by_key[key] = {
                    **selected,
                    "quantity": 0,
                }
            recommendations_by_key[key]["quantity"] += 1

        recommendations = list(recommendations_by_key.values())
        for recommendation in recommendations:
            recommendation["priority_score"] = round(
                recommendation["priority_score"],
                2,
            )
            recommendation["match_score"] = round(
                recommendation["match_score"],
                2,
            )
            recommendation["eta_minutes"] = (
                round(recommendation["eta_minutes"], 2)
                if recommendation["eta_minutes"] is not None
                else None
            )
            recommendation["distance_km"] = (
                round(recommendation["distance_km"], 2)
                if recommendation["distance_km"] is not None
                else None
            )
            recommendation["cost_estimate"] = round(recommendation.get("cost_estimate", 0.0) * recommendation["quantity"], 2)
            recommendation["tradeoff_summary"] = (
                f"Balances priority {recommendation['priority_score']:.1f}, response time {recommendation['factors']['eta']:.0f}/100, "
                f"cost efficiency {recommendation['factors']['cost']:.0f}/100 and safety {recommendation['factors']['risk']:.0f}/100."
            )
            recommendation["allocation_reason"] = self._allocation_reason(
                recommendation
            )
            recommendation["status"] = "RECOMMENDED"

        fulfillment: list[dict[str, Any]] = []
        unfulfilled: list[dict[str, Any]] = []
        for emergency in ranked_active:
            emergency_id = _value(emergency, "id")
            estimated = demand_by_emergency[emergency_id]
            fulfilled = dict(assigned_by_emergency[emergency_id])
            remaining = {
                resource_type: quantity - fulfilled.get(resource_type, 0)
                for resource_type, quantity in estimated.items()
                if quantity - fulfilled.get(resource_type, 0) > 0
            }
            is_constrained = bool(remaining)
            report = {
                "emergency_id": emergency_id,
                "emergency_title": _value(emergency, "title"),
                "estimated_demand": estimated,
                "fulfilled_demand": fulfilled,
                "unfulfilled_demand": remaining,
                "status": (
                    "PARTIALLY_FULFILLED"
                    if is_constrained
                    else "FULLY_FULFILLED"
                ),
                "resource_constrained": is_constrained,
            }
            fulfillment.append(report)
            if is_constrained:
                unfulfilled.append(report)

        return {
            "recommendations": sorted(
                recommendations,
                key=lambda item: item["match_score"],
                reverse=True,
            ),
            "fulfillment": fulfillment,
            "unfulfilled_demand": unfulfilled,
            "weights": dict(self.weights),
        }

    def _candidate(
        self,
        emergency: Mapping[str, Any],
        resource: Mapping[str, Any],
        priority: Mapping[str, Any],
        remaining_quantity: int,
        total_demand_by_type: Mapping[str, int],
        remaining_by_resource: Mapping[Any, int],
        remaining_by_type: Mapping[str, int],
        assigned_by_emergency: Mapping[Any, Mapping[str, int]],
        demand_by_emergency: Mapping[Any, Mapping[str, int]],
        ranked_active: list[Mapping[str, Any]],
    ) -> dict[str, Any]:
        emergency_id = _value(emergency, "id")
        resource_id = _value(resource, "id")
        resource_type = str(_value(resource, "type", "")).upper()
        distance = haversine_distance(
            _value(emergency, "latitude"),
            _value(emergency, "longitude"),
            _value(resource, "latitude"),
            _value(resource, "longitude"),
        )
        eta = estimated_eta_minutes(
            distance,
            resource_type,
            self.config["speeds_kmh"] or RESOURCE_SPEEDS_KMH,
        )
        # Hard feasibility guardrails prevent obviously unsuitable long-distance
        # recommendations. Missing coordinates remain eligible but are scored at 0
        # for proximity/ETA so the operator can see the data-quality trade-off.
        if distance is not None and distance > self.max_distance_km:
            raise ValueError("candidate_out_of_range")
        if eta is not None and eta > self.max_eta_minutes:
            raise ValueError("candidate_eta_too_high")
        initial_quantity = max(_number(_value(resource, "quantity")), 1.0)
        proximity = (
            100 / (1 + (distance / self.proximity_reference_km))
            if distance is not None
            else 0.0
        )
        eta_factor = (
            100 / (1 + (eta / self.eta_reference_minutes))
            if eta is not None
            else 0.0
        )
        availability = _clamp((remaining_quantity / initial_quantity) * 100)
        total_demand = max(total_demand_by_type.get(resource_type, 0), 1)
        remaining_type_quantity = remaining_by_type.get(
            resource_type,
            remaining_quantity,
        )
        scarcity = _clamp(
            (1 - (remaining_type_quantity / total_demand)) * 100
        )
        assigned = sum(assigned_by_emergency[emergency_id].values())
        total_emergency_demand = max(
            sum(demand_by_emergency[emergency_id].values()),
            1,
        )
        fairness = _clamp(
            (1 - (assigned / total_emergency_demand)) * 100
        )
        if assigned and any(
            not assigned_by_emergency[_value(other, "id")]
            and _value(other, "id") != emergency_id
            for other in ranked_active
        ):
            fairness *= 0.5
        cost_per_unit = _number(_value(resource, "cost_per_unit"))
        resource_risk = _clamp(_number(_value(resource, "risk_score"), 50.0))
        cost_score = _clamp(100.0 * (1.0 - min(cost_per_unit / self.cost_reference, 1.0)))
        risk_score = _clamp(100.0 - resource_risk)
        factors = {
            "priority": _number(priority.get("priority_score")),
            "compatibility": 100.0,
            "proximity": _clamp(proximity),
            "eta": _clamp(eta_factor),
            "availability": availability,
            "scarcity": scarcity,
            "fairness": fairness,
            "cost": cost_score,
            "risk": risk_score,
        }
        match_score = _clamp(
            sum(factors[name] * self.weights.get(name, 0.0) for name in factors)
        )
        return {
            "emergency_id": emergency_id,
            "emergency_title": _value(emergency, "title"),
            "resource_id": resource_id,
            "resource_name": _value(resource, "name"),
            "resource_type": resource_type,
            "priority_score": factors["priority"],
            "match_score": match_score,
            "distance_km": distance,
            "eta_minutes": eta,
            "distance_km": distance,
            "cost_per_unit": cost_per_unit,
            "cost_estimate": cost_per_unit,
            "risk_score": resource_risk,
            "factors": factors,
        }

    @staticmethod
    def _allocation_reason(recommendation: Mapping[str, Any]) -> str:
        eta = recommendation["eta_minutes"]
        distance = recommendation["distance_km"]
        eta_text = f"{eta:.1f} min" if eta is not None else "ETA unavailable"
        distance_text = f"{distance:.1f} km" if distance is not None else "distance unavailable"
        factors = recommendation["factors"]
        cost = recommendation.get("cost_per_unit", 0.0)
        risk = recommendation.get("risk_score", 50.0)
        tradeoff = (
            "favors response speed" if factors["eta"] >= factors["cost"] and factors["eta"] >= factors["risk"]
            else "favors lower operating cost" if factors["cost"] >= factors["risk"]
            else "favors lower operational risk"
        )
        return (
            f"Decision score {recommendation['match_score']:.2f}/100; priority {recommendation['priority_score']:.2f}/100. "
            f"Response: {distance_text}, {eta_text}. Cost: ₹{cost:,.0f}/unit. Risk: {risk:.0f}/100. "
            f"Availability {factors['availability']:.0f}/100, scarcity {factors['scarcity']:.0f}/100, fairness {factors['fairness']:.0f}/100. "
            f"Trade-off: {tradeoff} within the configured constraints. "
            "Estimated matching only; operator approval is required before deployment."
        )


def optimize_resources(
    emergencies: Iterable[Mapping[str, Any]],
    resources: Iterable[Mapping[str, Any]],
    *,
    config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Convenience function for callers that do not need an optimizer object."""
    return ResourceOptimizer(config).optimize(emergencies, resources)
