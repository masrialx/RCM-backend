from flask import Flask
from .auth import auth_bp
from .claims import claims_bp
from flask import Blueprint, jsonify
import os


def register_blueprints(app: Flask) -> None:
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(claims_bp, url_prefix="/api")
    
    # Public blueprint for policy and other public endpoints
    public_bp = Blueprint("public", __name__)

    @public_bp.get("/policy")
    def policy():
        """Public core policy endpoint.

        The content can be overridden via CORE_POLICY_TEXT env var.
        """
        default_policy = {
            "name": "RCM Core Policy",
            "version": os.getenv("POLICY_VERSION", "1.0"),
            "public": True,
            "allowed_origins": os.getenv(
                "CORS_ORIGINS",
                "http://localhost:5173,http://localhost:5174,http://localhost:3000,https://rcm-front-end.onrender.com",
            ).split(","),
            "description": "Operational and security policy summary for the RCM API",
            "sections": [
                {
                    "id": "auth",
                    "title": "Authentication",
                    "content": "All non-health/public endpoints require JWT Bearer tokens.",
                },
                {
                    "id": "cors",
                    "title": "CORS",
                    "content": "Only configured origins are allowed to call the API from browsers.",
                },
                {
                    "id": "rate_limits",
                    "title": "Rate Limits",
                    "content": "Abuse and DDoS protections may restrict excessive request rates.",
                },
                {
                    "id": "data_handling",
                    "title": "Data Handling",
                    "content": "Uploaded claim files are processed for validation; inputs must be CSV/XLSX.",
                },
            ],
        }

        override = (os.getenv("CORE_POLICY_TEXT") or "").strip()
        if override:
            return jsonify({"policy": override}), 200
        return jsonify(default_policy), 200

    app.register_blueprint(public_bp, url_prefix="/")

