"""Route registration for the ResQMatrix AI application."""

from flask import Flask

from .api_routes import api_bp
from .dashboard_routes import dashboard_bp


def register_routes(app: Flask) -> None:
    """Register all application blueprints."""
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_bp)