from flask import Flask
from .auth import auth_bp
from .claims import claims_bp


def register_blueprints(app: Flask) -> None:
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(claims_bp, url_prefix="/api")

