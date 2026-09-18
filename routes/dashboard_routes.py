"""Dashboard and health routes."""

from flask import Blueprint, jsonify, render_template


dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/")
def index():
    """Render the public product landing page."""
    return render_template("index.html")


@dashboard_bp.get("/dashboard")
def dashboard():
    """Render the initial operator dashboard shell."""
    return render_template("dashboard.html")


@dashboard_bp.get("/api/health")
def health():
    """Return a small readiness response for the application."""
    return jsonify(
        {
            "status": "success",
            "message": "ResQMatrix AI API is running",
        }
    )