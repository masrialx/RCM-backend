from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import uuid4
from typing import Any
from flask import current_app
from ..extensions import db
from ..models.models import Master, Refined, Metrics
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
            errors = self.validator.run_all(claim)
            current_app.logger.debug(f"Validator result for {claim.claim_id}: {errors}")
            if errors and errors.get("error_type") != "No error":
                claim.status = "Not Validated"
                claim.error_type = errors["error_type"]
                claim.error_explanation = errors.get("explanations", [])
                claim.recommended_action = errors.get("recommended_actions", [])
                failed += 1
            else:
                claim.status = "Validated"
                claim.error_type = "No error"
                validated += 1
            self.session.add(claim)

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
                except Exception:  # noqa: BLE001
                    current_app.logger.exception("LLM evaluation failed; continuing with static results")

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
    parts = [p.strip().upper() for p in s.split(",") if p.strip()]
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

