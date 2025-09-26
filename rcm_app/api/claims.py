from io import BytesIO
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt
import pandas as pd
from ..pipeline.engine import ValidationEngine
from ..rules.loader import TenantConfigLoader
from ..extensions import db


claims_bp = Blueprint("claims", __name__)


@claims_bp.post("/upload")
@jwt_required()
def upload_claims():
    jwt_claims = get_jwt()
    tenant_id = (request.form.get("tenant_id") or jwt_claims.get("tenant_id") or "").strip()
    if not tenant_id:
        return jsonify({"message": "tenant_id required"}), 400

    file = request.files.get("file")
    if not file:
        return jsonify({"message": "file is required"}), 400

    filename = (file.filename or "").lower()
    try:
        content = file.read()
        buf = BytesIO(content)
        if filename.endswith(".csv"):
            df = pd.read_csv(buf)
        elif filename.endswith(".xlsx") or filename.endswith(".xls"):
            df = pd.read_excel(buf)
        else:
            return jsonify({"message": "unsupported file type"}), 415
    except Exception as exc:  # noqa: BLE001
        return jsonify({"message": f"failed to parse file: {exc}"}), 400

    tenant_loader = TenantConfigLoader()
    rules_bundle = tenant_loader.load_rules_for_tenant(tenant_id)
    engine = ValidationEngine(db.session, tenant_id, rules_bundle)
    try:
        summary = engine.ingest_and_validate_dataframe(df)
        return jsonify(summary), 200
    except ValueError as ve:
        return jsonify({"message": str(ve)}), 400
    except Exception as exc:  # noqa: BLE001
        return jsonify({"message": f"processing error: {exc}"}), 500


@claims_bp.post("/validate")
@jwt_required()
def validate_claims():
    jwt_claims = get_jwt()
    tenant_id = (request.json or {}).get("tenant_id") or jwt_claims.get("tenant_id")
    claim_ids = (request.json or {}).get("claim_ids") or []
    if not tenant_id or not claim_ids:
        return jsonify({"message": "tenant_id and claim_ids required"}), 400
    tenant_loader = TenantConfigLoader()
    rules_bundle = tenant_loader.load_rules_for_tenant(tenant_id)
    engine = ValidationEngine(db.session, tenant_id, rules_bundle)
    result = engine.validate_specific_claims(claim_ids)
    return jsonify(result), 200


@claims_bp.get("/results")
@jwt_required()
def get_results():
    from ..models.models import Master
    jwt_claims = get_jwt()
    tenant_id = request.args.get("tenant_id") or jwt_claims.get("tenant_id")
    if not tenant_id:
        return jsonify({"message": "tenant_id required"}), 400
    q = Master.query.filter_by(tenant_id=tenant_id)
    status = request.args.get("status")
    error_type = request.args.get("error_type")
    service_code = request.args.get("service_code")
    if status:
        q = q.filter(Master.status == status)
    if error_type:
        q = q.filter(Master.error_type == error_type)
    if service_code:
        q = q.filter(Master.service_code == service_code)
    rows = q.order_by(Master.created_at.desc()).limit(500).all()
    def row_to_dict(r):
        return {
            "claim_id": r.claim_id,
            "service_date": r.service_date.isoformat() if r.service_date else None,
            "status": r.status,
            "error_type": r.error_type,
            "service_code": r.service_code,
            "paid_amount_aed": float(r.paid_amount_aed) if r.paid_amount_aed is not None else None,
            "tenant_id": r.tenant_id,
        }
    return jsonify([row_to_dict(r) for r in rows]), 200


@claims_bp.get("/audit")
@jwt_required()
def audit_log():
    # Placeholder simple audit response; extend with real audit storage later
    return jsonify({"message": "audit log not implemented in prototype", "status": "ok"}), 200

