from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import uuid4
from typing import Any
from flask import current_app
from ..extensions import db
from ..models.models import Master, Refined, Metrics, Audit
from ..rules.loader import RulesBundle
from ..utils.llm import GeminiClient
from ..utils.validators import Validator


@dataclass
class ValidationSummary:
    inserted: int
    validated: int
    failed: int


class ValidationEngine:
    def __init__(self, session, tenant_id: str, rules: RulesBundle) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.rules = rules
        self.llm = GeminiClient()
        self.validator = Validator(self.rules)

    def ingest_and_validate_dataframe(self, df) -> dict[str, Any]:  # pandas DF
        required_cols = [
            # claim_id can be auto-generated when missing
            "encounter_type","service_date","national_id","member_id","facility_id",
            "unique_id","diagnosis_codes","service_code","paid_amount_aed","approval_number",
        ]
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"missing required column: {col}")

        inserted = 0
        for _, row in df.iterrows():
            auto_claim_id = str(row.get("claim_id")) if "claim_id" in df.columns else None
            claim = Master(
                claim_id=auto_claim_id or str(uuid4()),
                encounter_type=str(row.get("encounter_type")) if row.get("encounter_type") is not None else None,
                service_date=pd_to_date(row.get("service_date")),
                national_id=upper_or_none(row.get("national_id")),
                member_id=upper_or_none(row.get("member_id")),
                facility_id=upper_or_none(row.get("facility_id")),
                unique_id=str(row.get("unique_id")) if row.get("unique_id") is not None else None,
                diagnosis_codes=split_codes(row.get("diagnosis_codes")),
                service_code=upper_or_none(row.get("service_code")),
                paid_amount_aed=to_decimal(row.get("paid_amount_aed")),
                approval_number=upper_or_none(row.get("approval_number")),
                tenant_id=self.tenant_id,
            )
            self.session.add(claim)
            inserted += 1
        self.session.commit()

        stats = self._validate_new_claims()
        return {"inserted": inserted, **stats}

    def validate_specific_claims(self, claim_ids: list[str]) -> dict[str, Any]:
        claims = Master.query.filter(Master.tenant_id == self.tenant_id, Master.claim_id.in_(claim_ids)).all()
        return self._validate_claims_list(claims)

    def _validate_new_claims(self) -> dict[str, Any]:
        claims = Master.query.filter_by(tenant_id=self.tenant_id, status="pending").all()
        return self._validate_claims_list(claims)

    def _validate_claims_list(self, claims: list[Master]) -> dict[str, Any]:
        validated = 0
        failed = 0
        for claim in claims:
            # Create audit record for validation start
            audit_start = Audit(
                claim_id=claim.claim_id,
                action="validation_started",
                outcome="in_progress",
                details={"previous_status": claim.status, "previous_error_type": claim.error_type},
                tenant_id=self.tenant_id,
            )
            self.session.add(audit_start)
            
            result = self.validator.run_all(claim)
            current_app.logger.debug(f"Validator result for {claim.claim_id}: {result}")

            # Apply any auto-corrections suggested by validator
            corrections = (result or {}).get("corrections", {}) if result else {}
            if corrections:
                if "approval_number" in corrections:
                    claim.approval_number = corrections["approval_number"]
                if "unique_id" in corrections:
                    claim.unique_id = corrections["unique_id"]
                if "encounter_type" in corrections:
                    claim.encounter_type = corrections["encounter_type"]
                self.session.add(claim)

            # Map error types to requested categories
            def _map_error_type(val: str | None) -> str:
                v = (val or "No error").strip()
                if v == "Technical error":
                    return "Technical error"
                if v == "Medical error":
                    return "Medical error"
                if v == "Both":
                    return "Both"
                return v

            if result and result.get("error_type") != "No error":
                claim.status = "Not Validated"
                claim.error_type = _map_error_type(result["error_type"])  # map Technical->Administrative
                claim.error_explanation = result.get("explanations", [])
                claim.recommended_action = result.get("recommended_actions", [])
                failed += 1
            else:
                claim.status = "Validated"
                claim.error_type = "No error"
                # If only corrections occurred, persist brief explanation and actions
                if result and (result.get("explanations") or result.get("recommended_actions")):
                    claim.error_explanation = result.get("explanations", [])
                    claim.recommended_action = result.get("recommended_actions", [])
                validated += 1
            self.session.add(claim)
            
            # Create audit record for validation completion
            audit_complete = Audit(
                claim_id=claim.claim_id,
                action="validation_completed",
                outcome="success" if claim.status == "Validated" else "failed",
                details={
                    "final_status": claim.status,
                    "final_error_type": claim.error_type,
                    "error_count": len(result.get("explanations", [])) if result else 0,
                    "validation_method": "static_rules"
                },
                tenant_id=self.tenant_id,
            )
            self.session.add(audit_complete)

            # generate refined
            refined = Refined(
                claim_id=claim.claim_id,
                normalized_national_id=claim.national_id,
                normalized_member_id=claim.member_id,
                normalized_facility_id=claim.facility_id,
                status=claim.status,
                error_type=claim.error_type,
                final_action=self._derive_final_action(claim),
                tenant_id=self.tenant_id,
            )
            self.session.add(refined)

            # LLM augmentation when failed or as configured
            if claim.status == "Not Validated":
                try:
                    # Create audit record for LLM usage
                    audit_llm_start = Audit(
                        claim_id=claim.claim_id,
                        action="llm_evaluation_started",
                        outcome="in_progress",
                        details={"llm_model": "gemini-2.0-flash", "reason": "claim_validation_failed"},
                        tenant_id=self.tenant_id,
                    )
                    self.session.add(audit_llm_start)
                    
                    llm_payload = {
                        "claim": model_to_dict(claim),
                        "rules_text": self.rules.raw_rules_text,
                    }
                    llm_resp = self.llm.evaluate_claim(llm_payload)
                    if llm_resp and isinstance(llm_resp, dict):
                        # merge explanations and actions
                        exps = claim.error_explanation or []
                        acts = claim.recommended_action or []
                        exps.extend(llm_resp.get("explanations", []) or [])
                        acts.extend(llm_resp.get("recommended_actions", []) or [])
                        claim.error_explanation = exps
                        claim.recommended_action = acts
                        # reconcile type: prefer more severe
                        claim.error_type = reconcile_error_type(claim.error_type, llm_resp.get("error_type"))
                        self.session.add(claim)
                        
                        # Create audit record for LLM completion
                        audit_llm_complete = Audit(
                            claim_id=claim.claim_id,
                            action="llm_evaluation_completed",
                            outcome="success",
                            details={
                                "llm_model": "gemini-2.0-flash",
                                "additional_explanations": len(llm_resp.get("explanations", [])),
                                "additional_actions": len(llm_resp.get("recommended_actions", [])),
                                "final_error_type": claim.error_type
                            },
                            tenant_id=self.tenant_id,
                        )
                        self.session.add(audit_llm_complete)
                    else:
                        # Create audit record for LLM failure
                        audit_llm_fail = Audit(
                            claim_id=claim.claim_id,
                            action="llm_evaluation_failed",
                            outcome="error",
                            details={"llm_model": "gemini-2.0-flash", "error": "no_response"},
                            tenant_id=self.tenant_id,
                        )
                        self.session.add(audit_llm_fail)
                except Exception as e:  # noqa: BLE001
                    current_app.logger.exception("LLM evaluation failed; continuing with static results")
                    # Create audit record for LLM exception
                    audit_llm_exception = Audit(
                        claim_id=claim.claim_id,
                        action="llm_evaluation_exception",
                        outcome="error",
                        details={"llm_model": "gemini-2.0-flash", "error": str(e)},
                        tenant_id=self.tenant_id,
                    )
                    self.session.add(audit_llm_exception)

        self.session.commit()
        self._update_metrics()
        return {"validated": validated, "failed": failed}

    def _derive_final_action(self, claim: Master) -> str:
        if claim.error_type == "No error":
            return "accept"
        if claim.error_type == "Both":
            return "reject"
        if claim.error_type == "Medical":
            return "escalate"
        return "reject"

    def comprehensive_adjudication(self, df) -> dict[str, Any]:
        """Comprehensive medical claims adjudication with detailed validation and corrections"""
        required_cols = [
            "encounter_type","service_date","national_id","member_id","facility_id",
            "unique_id","diagnosis_codes","service_code","paid_amount_aed","approval_number",
        ]
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"missing required column: {col}")

        processed_claims = []
        inserted = 0
        
        # Process each claim with comprehensive validation
        for _, row in df.iterrows():
            auto_claim_id = str(row.get("claim_id")) if "claim_id" in df.columns else None
            claim = Master(
                claim_id=auto_claim_id or str(uuid4()),
                encounter_type=str(row.get("encounter_type")) if row.get("encounter_type") is not None else None,
                service_date=pd_to_date(row.get("service_date")),
                national_id=upper_or_none(row.get("national_id")),
                member_id=upper_or_none(row.get("member_id")),
                facility_id=upper_or_none(row.get("facility_id")),
                unique_id=str(row.get("unique_id")) if row.get("unique_id") is not None else None,
                diagnosis_codes=split_codes(row.get("diagnosis_codes")),
                service_code=upper_or_none(row.get("service_code")),
                paid_amount_aed=to_decimal(row.get("paid_amount_aed")),
                approval_number=upper_or_none(row.get("approval_number")),
                tenant_id=self.tenant_id,
            )
            self.session.add(claim)
            inserted += 1
            
            # Comprehensive validation with detailed output
            result = self.validator.run_all(claim)
            
            # Apply corrections (only approval_number, not encounter_type or unique_id)
            corrections = (result or {}).get("corrections", {}) if result else {}
            if corrections:
                if "approval_number" in corrections:
                    claim.approval_number = corrections["approval_number"]
                # Note: Not auto-correcting unique_id or encounter_type per requirements
                self.session.add(claim)
            
            # Map error types
            def _map_error_type(val: str | None) -> str:
                v = (val or "No error").strip()
                if v == "Technical":
                    return "Administrative"
                if v == "Both":
                    return "Medical"
                return v
            
            # Set claim status and error information
            if result and result.get("error_type") != "No error":
                claim.status = "Not Validated"
                claim.error_type = _map_error_type(result["error_type"])
                claim.error_explanation = result.get("explanations", [])
                claim.recommended_action = result.get("recommended_actions", [])
            else:
                claim.status = "Validated"
                claim.error_type = "No error"
                if result and (result.get("explanations") or result.get("recommended_actions")):
                    claim.error_explanation = result.get("explanations", [])
                    claim.recommended_action = result.get("recommended_actions", [])
            
            self.session.add(claim)
            
            # Create detailed claim output
            claim_output = {
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
                "corrections_applied": corrections,
                "summary": self._generate_claim_summary(claim, result, corrections),
                "tenant_id": self.tenant_id,
                "created_at": claim.created_at.isoformat() if claim.created_at else None,
                "updated_at": claim.updated_at.isoformat() if claim.updated_at else None
            }
            processed_claims.append(claim_output)
        
        self.session.commit()
        
        # Generate chart data
        chart_data = self._generate_chart_data(processed_claims)
        
        # Generate pagination info
        total_claims = len(processed_claims)
        pagination = {
            "page": 1,
            "page_size": total_claims,
            "total_claims": total_claims,
            "total_pages": 1
        }
        
        return {
            "claims": processed_claims,
            "chart_data": chart_data,
            "pagination": pagination,
            "summary": {
                "total_processed": total_claims,
                "validated": len([c for c in processed_claims if c["status"] == "Validated"]),
                "not_validated": len([c for c in processed_claims if c["status"] == "Not Validated"]),
                "corrections_applied": len([c for c in processed_claims if c["corrections_applied"]]),
                "error_types": {
                    "No error": len([c for c in processed_claims if c["error_type"] == "No error"]),
                    "Administrative": len([c for c in processed_claims if c["error_type"] == "Administrative"]),
                    "Medical": len([c for c in processed_claims if c["error_type"] == "Medical"])
                }
            }
        }

    def _generate_claim_summary(self, claim: Master, result: dict | None, corrections: dict) -> str:
        """Generate a short explanation per claim summarizing corrections made"""
        summary_parts = []
        
        if corrections:
            if "approval_number" in corrections:
                summary_parts.append(f"Generated approval number '{corrections['approval_number']}'")
        
        if result and result.get("explanations"):
            # Filter out correction messages from explanations
            filtered_explanations = [exp for exp in result["explanations"] if not exp.startswith("Generated approval_number") and not exp.startswith("Normalized unique_id") and not exp.startswith("Corrected encounter_type")]
            summary_parts.extend([f"Issue: {exp}" for exp in filtered_explanations[:2]])  # Limit to first 2 issues
        
        if not summary_parts:
            summary_parts.append("No issues found - claim validated successfully")
        
        return "; ".join(summary_parts)

    def _generate_chart_data(self, claims: list[dict]) -> dict:
        """Generate chart data with claim counts and paid amounts by error type"""
        claim_counts_by_error = {}
        paid_amount_by_error = {}
        
        for claim in claims:
            error_type = claim["error_type"]
            paid_amount = claim["paid_amount_aed"] or 0
            
            claim_counts_by_error[error_type] = claim_counts_by_error.get(error_type, 0) + 1
            paid_amount_by_error[error_type] = paid_amount_by_error.get(error_type, 0) + paid_amount
        
        return {
            "claim_counts_by_error": claim_counts_by_error,
            "paid_amount_by_error": paid_amount_by_error
        }

    def _update_metrics(self) -> None:
        # Simple aggregation per tenant
        from sqlalchemy import func
        rows = db.session.query(
            Master.error_type, func.count(Master.id), func.coalesce(func.sum(Master.paid_amount_aed), 0)
        ).filter(Master.tenant_id == self.tenant_id).group_by(Master.error_type).all()
        for etype, cnt, psum in rows:
            m = Metrics(
                tenant_id=self.tenant_id,
                error_category=etype,
                claim_count=int(cnt),
                paid_sum=psum,
                time_bucket=None,
            )
            db.session.add(m)
        db.session.commit()


def pd_to_date(val):
    try:
        import pandas as pd  # local import to avoid hard dep here
        if pd.isna(val):
            return None
        return pd.to_datetime(val).date()
    except Exception:
        return None


def upper_or_none(val):
    if val is None:
        return None
    s = str(val)
    return s.upper()


def split_codes(val):
    if val is None:
        return []
    if isinstance(val, list):
        return [str(x).strip().upper() for x in val]
    s = str(val)
    # Support both semicolon and comma separated diagnosis codes
    # Normalize by replacing semicolons with commas then splitting
    normalized = s.replace(";", ",")
    parts = [p.strip().upper() for p in normalized.split(",") if p.strip()]
    return parts


def to_decimal(val):
    if val is None:
        return None
    try:
        return round(float(val), 2)
    except Exception:
        return None


def model_to_dict(claim: Master) -> dict[str, Any]:
    return {
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
    }


def reconcile_error_type(static_type: str, llm_type: str | None) -> str:
    order = {"No error": 0, "Technical": 1, "Medical": 2, "Both": 3}
    candidate = llm_type or static_type
    if order.get(candidate, 0) >= order.get(static_type, 0):
        return candidate
    return static_type

