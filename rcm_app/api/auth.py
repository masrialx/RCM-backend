from datetime import timedelta
from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token
import os


auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/login")
def login():
    payload = request.get_json(silent=True) or {}
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    tenant_id = (payload.get("tenant_id") or os.getenv("DEFAULT_TENANT_ID", "tenant_demo")).strip()

    # Prototype fixed credentials per request: username/email: admin or admin@rcm.local, password: admin12345
    allowed_users = {"admin", "admin@rcm.local"}
    if username not in allowed_users or password != "admin12345":
        return jsonify({"message": "invalid credentials"}), 401

    claims = {"roles": ["admin"], "tenant_id": tenant_id}
    expires = int(os.getenv("JWT_ACCESS_MINUTES", "720"))
    token = create_access_token(identity=username, additional_claims=claims, expires_delta=timedelta(minutes=expires))
    return jsonify({"access_token": token, "tenant_id": tenant_id}), 200

