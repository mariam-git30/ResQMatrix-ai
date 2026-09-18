"""ResQMatrix AI Flask application entry point."""

from flask import Flask

from config import Config
from database.db import initialize_database
from routes import register_routes


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(Config)
    initialize_database(app.config["DATABASE_PATH"])
    register_routes(app)
    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        host=app.config["HOST"],
        port=app.config["PORT"],
        debug=app.config["DEBUG"],
    )