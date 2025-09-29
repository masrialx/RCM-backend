from io import BytesIO
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt
import pandas as pd
from rcm_app.pipeline.engine import ValidationEngine
from rcm_app.rules.loader import TenantConfigLoader
from rcm_app.extensions import db
from rcm_app.models.models import Master, Metrics, Audit
from rcm_app.agent import RCMValidationAgent
from sqlalchemy import func, desc


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
            # Robust CSV parsing: try common delimiters and encodings
            parse_attempts = [
                {"sep": ",", "encoding": None},
                {"sep": ";", "encoding": None},
                {"sep": "\t", "encoding": None},
            ]
            last_exc = None
            df = None
            for attempt in parse_attempts:
                try:
                    buf.seek(0)
                    df = pd.read_csv(
                        buf,
                        dtype=str,
                        keep_default_na=False,
                        na_filter=False,
                        sep=attempt["sep"],
                    )
                    break
                except Exception as e:  # noqa: BLE001
                    last_exc = e
            if df is None:
                raise last_exc or Exception("could not parse CSV")
        elif filename.endswith(".xlsx") or filename.endswith(".xls"):
            df = pd.read_excel(buf, dtype=str)
        else:
            return jsonify({"message": "unsupported file type"}), 415
    except Exception as exc:  # noqa: BLE001
        return jsonify({"message": f"failed to parse file: {exc}"}), 400

    # Normalize column names (trim, lower)
    df.columns = [str(c).strip().lower() for c in df.columns]
    # Map common aliases to required columns
    col_aliases = {
        "claimid": "claim_id",
        "id": "claim_id",
        "uniqueid": "unique_id",
        "uid": "unique_id",
        "diagnosis": "diagnosis_codes",
        "diagnoses": "diagnosis_codes",
        "paid_amount": "paid_amount_aed",
        "paid_amount_aed": "paid_amount_aed",
        "approval": "approval_number",
        "approvalno": "approval_number",
    }
    df.rename(columns={k: v for k, v in col_aliases.items() if k in df.columns}, inplace=True)
    # Align identifiers as in upload: mirror whichever exists
    if "claim_id" not in df.columns and "unique_id" in df.columns:
        df["claim_id"] = df["unique_id"].astype(str)
    if "unique_id" not in df.columns and "claim_id" in df.columns:
        df["unique_id"] = df["claim_id"].astype(str)
    # Align identifiers: if only one of claim_id/unique_id is provided, mirror it
    if "claim_id" not in df.columns and "unique_id" in df.columns:
        df["claim_id"] = df["unique_id"].astype(str)
    if "unique_id" not in df.columns and "claim_id" in df.columns:
        df["unique_id"] = df["claim_id"].astype(str)

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
    jwt_claims = get_jwt()
    tenant_id = request.args.get("tenant_id") or jwt_claims.get("tenant_id")
    if not tenant_id:
        return jsonify({"message": "tenant_id required"}), 400
    
    # Pagination parameters
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 10))
    
    # Filter parameters
    status = request.args.get("status")
    error_type = request.args.get("error_type")
    service_code = request.args.get("service_code")
    
    # Build query
    q = Master.query.filter_by(tenant_id=tenant_id)
    
    if status:
        q = q.filter(Master.status == status)
    if error_type:
        q = q.filter(Master.error_type == error_type)
    if service_code:
        q = q.filter(Master.service_code == service_code)
    
    # Get total count for pagination
    total_claims = q.count()
    total_pages = (total_claims + page_size - 1) // page_size
    
    # Apply pagination
    offset = (page - 1) * page_size
    claims = q.order_by(desc(Master.created_at)).offset(offset).limit(page_size).all()
    
    # Convert claims to dict with all Master Table fields
    claims_data = []
    for claim in claims:
        claim_dict = {
            "claim_id": claim.claim_id,
            "encounter_type": claim.encounter_type,
            "service_date": claim.service_date.isoformat() if claim.service_date else None,
            "national_id": claim.national_id,
            "member_id": claim.member_id,
            "facility_id": claim.facility_id,
            "unique_id": claim.unique_id,
            "diagnosis_codes": claim.diagnosis_codes,
            "service_code": claim.service_code,
            "paid_amount_aed": float(claim.paid_amount_aed) if claim.paid_amount_aed is not None else None,
            "approval_number": claim.approval_number,
            "status": claim.status,
            "error_type": claim.error_type,
            "error_explanation": claim.error_explanation or [],
            "recommended_action": claim.recommended_action or [],
            "tenant_id": claim.tenant_id,
            "created_at": claim.created_at.isoformat() if claim.created_at else None,
            "updated_at": claim.updated_at.isoformat() if claim.updated_at else None
        }
        claims_data.append(claim_dict)
    
    # Get chart data from Metrics table
    chart_data = _get_chart_data(tenant_id)
    
    # Pagination metadata
    pagination = {
        "page": page,
        "total_pages": total_pages,
        "total_claims": total_claims,
        "page_size": page_size
    }
    
    return jsonify({
        "claims": claims_data,
        "chart_data": chart_data,
        "pagination": pagination
    }), 200


@claims_bp.get("/audit")
@jwt_required()
def audit_log():
    jwt_claims = get_jwt()
    tenant_id = request.args.get("tenant_id") or jwt_claims.get("tenant_id")
    if not tenant_id:
        return jsonify({"message": "tenant_id required"}), 400
    
    # Pagination parameters
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 20))
    
    # Filter parameters
    claim_id = request.args.get("claim_id")
    action = request.args.get("action")
    
    # Build query
    q = Audit.query.filter_by(tenant_id=tenant_id)
    
    if claim_id:
        q = q.filter(Audit.claim_id == claim_id)
    if action:
        q = q.filter(Audit.action == action)
    
    # Get total count for pagination
    total_audits = q.count()
    total_pages = (total_audits + page_size - 1) // page_size
    
    # Apply pagination
    offset = (page - 1) * page_size
    audits = q.order_by(desc(Audit.timestamp)).offset(offset).limit(page_size).all()
    
    # Convert audits to dict
    audit_data = []
    for audit in audits:
        audit_dict = {
            "id": audit.id,
            "claim_id": audit.claim_id,
            "action": audit.action,
            "timestamp": audit.timestamp.isoformat() if audit.timestamp else None,
            "outcome": audit.outcome,
            "details": audit.details or {},
            "tenant_id": audit.tenant_id,
            "created_at": audit.created_at.isoformat() if audit.created_at else None
        }
        audit_data.append(audit_dict)
    
    # Pagination metadata
    pagination = {
        "page": page,
        "total_pages": total_pages,
        "total_audits": total_audits,
        "page_size": page_size
    }
    
    return jsonify({
        "audits": audit_data,
        "pagination": pagination
    }), 200


@claims_bp.post("/adjudicate")
@jwt_required()
def adjudicate_claims():
    """Comprehensive medical claims adjudication with detailed validation and corrections"""
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
            parse_attempts = [
                {"sep": ","},
                {"sep": ";"},
                {"sep": "\t"},
            ]
            last_exc = None
            df = None
            for attempt in parse_attempts:
                try:
                    buf.seek(0)
                    df = pd.read_csv(
                        buf,
                        dtype=str,
                        keep_default_na=False,
                        na_filter=False,
                        sep=attempt["sep"],
                    )
                    break
                except Exception as e:  # noqa: BLE001
                    last_exc = e
            if df is None:
                raise last_exc or Exception("could not parse CSV")
        elif filename.endswith(".xlsx") or filename.endswith(".xls"):
            df = pd.read_excel(buf, dtype=str)
        else:
            return jsonify({"message": "unsupported file type"}), 415
    except Exception as exc:  # noqa: BLE001
        return jsonify({"message": f"failed to parse file: {exc}"}), 400

    # Normalize column names and aliases for adjudication
    df.columns = [str(c).strip().lower() for c in df.columns]
    col_aliases = {
        "claimid": "claim_id",
        "id": "claim_id",
        "uniqueid": "unique_id",
        "uid": "unique_id",
        "diagnosis": "diagnosis_codes",
        "diagnoses": "diagnosis_codes",
        "paid_amount": "paid_amount_aed",
        "paid_amount_aed": "paid_amount_aed",
        "approval": "approval_number",
        "approvalno": "approval_number",
    }
    df.rename(columns={k: v for k, v in col_aliases.items() if k in df.columns}, inplace=True)
    if "claim_id" not in df.columns and "unique_id" in df.columns:
        df["claim_id"] = df["unique_id"].astype(str)
    if "unique_id" not in df.columns and "claim_id" in df.columns:
        df["unique_id"] = df["claim_id"].astype(str)

    tenant_loader = TenantConfigLoader()
    rules_bundle = tenant_loader.load_rules_for_tenant(tenant_id)
    engine = ValidationEngine(db.session, tenant_id, rules_bundle)
    
    try:
        # Process claims with comprehensive validation
        result = engine.comprehensive_adjudication(df)
        return jsonify(result), 200
    except ValueError as ve:
        return jsonify({"message": str(ve)}), 400
    except Exception as exc:  # noqa: BLE001
        return jsonify({"message": f"processing error: {exc}"}), 500


@claims_bp.post("/agent")
@jwt_required()
def query_agent():
    """Query the AI agent for specific analysis"""
    jwt_claims = get_jwt()
    tenant_id = (request.json or {}).get("tenant_id") or jwt_claims.get("tenant_id")
    claim_id = (request.json or {}).get("claim_id")
    query = (request.json or {}).get("query", "")
    
    if not tenant_id or not claim_id:
        return jsonify({"message": "tenant_id and claim_id required"}), 400
    
    try:
        # Get the claim
        claim = Master.query.filter_by(tenant_id=tenant_id, claim_id=claim_id).first()
        if not claim:
            return jsonify({"message": "Claim not found"}), 404
        
        # Enriched, structured analysis while preserving existing keys used by the frontend
        errors_list = claim.error_explanation or []
        recs_list = claim.recommended_action or []
        error_count = len(errors_list)

        def _severity(status: str | None, error_type: str | None, count: int) -> str:
            s = (status or "").lower()
            e = (error_type or "").lower()
            if s in {"invalid", "not validated"}:
                if e == "both" or count >= 3:
                    return "High"
                if e in {"medical error", "technical error"} or count == 2:
                    return "Medium"
                return "Low"
            if s in {"valid", "validated"}:
                if e in {"", "none", "no error", None} and count == 0:
                    return "None"
                return "Low"
            return "Medium"

        sev = _severity(claim.status, claim.error_type, error_count)

        headline = []
        headline.append(f"Claim {claim_id} — {claim.encounter_type or 'N/A'} encounter")
        if claim.service_date:
            headline.append(f"Service date: {claim.service_date.isoformat()}")
        if claim.service_code:
            headline.append(f"Service code: {claim.service_code}")
        if claim.paid_amount_aed is not None:
            try:
                amt = float(claim.paid_amount_aed)
                headline.append(f"Paid amount: AED {amt:,.2f}")
            except Exception:  # noqa: BLE001
                pass

        analysis_text = (
            f"Status: {claim.status or 'Unknown'} | Error type: {claim.error_type or 'None'} | "
            f"Issues found: {error_count} | Severity: {sev}. "
            f"{' '.join(headline)}"
        )

        reasoning_lines = []
        if errors_list:
            reasoning_lines.append("Top issues:")
            for idx, err in enumerate(errors_list[:5], start=1):
                reasoning_lines.append(f"{idx}. {err}")
        else:
            reasoning_lines.append("No rule violations detected.")

        if recs_list:
            reasoning_lines.append("\nRecommended next actions:")
            for idx, r in enumerate(recs_list[:5], start=1):
                reasoning_lines.append(f"{idx}. {r}")
        else:
            if (claim.status or '').lower() in {"invalid", "not validated"}:
                reasoning_lines.append("\nRecommended next actions: 1) Review coding and documentation, 2) Fix discrepancies, 3) Re-validate.")

        analysis = {
            "claim_id": claim_id,
            "query": query,
            "claim_details": {
                "encounter_type": claim.encounter_type,
                "service_date": claim.service_date.isoformat() if claim.service_date else None,
                "national_id": claim.national_id,
                "member_id": claim.member_id,
                "facility_id": claim.facility_id,
                "unique_id": claim.unique_id,
                "diagnosis_codes": claim.diagnosis_codes,
                "service_code": claim.service_code,
                "paid_amount_aed": float(claim.paid_amount_aed) if claim.paid_amount_aed is not None else None,
                "approval_number": claim.approval_number,
                "status": claim.status,
                "error_type": claim.error_type,
                "error_explanation": errors_list,
                "recommended_action": recs_list
            },
            "agent_response": {
                "status": "Processed",
                "analysis": analysis_text,
                "current_status": claim.status,
                "error_type": claim.error_type,
                "errors": errors_list,
                "recommendations": recs_list,
                "reasoning": "\n".join(reasoning_lines)
            }
        }
        
        return jsonify(analysis), 200
        
    except Exception as e:
        return jsonify({"message": f"Agent query failed: {str(e)}"}), 500


def _get_chart_data(tenant_id: str) -> dict:
    """Get chart data from Metrics table"""
    try:
        # Get claim counts by error type
        claim_counts = db.session.query(
            Metrics.error_category,
            func.sum(Metrics.claim_count)
        ).filter(
            Metrics.tenant_id == tenant_id
        ).group_by(Metrics.error_category).all()
        
        # Get paid amounts by error type
        paid_amounts = db.session.query(
            Metrics.error_category,
            func.sum(Metrics.paid_sum)
        ).filter(
            Metrics.tenant_id == tenant_id
        ).group_by(Metrics.error_category).all()
        
        # Convert to dictionaries
        claim_counts_by_error = {error_type: int(count) for error_type, count in claim_counts}
        paid_amount_by_error = {error_type: float(amount) for error_type, amount in paid_amounts}
        
        return {
            "claim_counts_by_error": claim_counts_by_error,
            "paid_amount_by_error": paid_amount_by_error
        }
        
    except Exception as e:
        return {
            "claim_counts_by_error": {},
            "paid_amount_by_error": {}
        }

