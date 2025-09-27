"""
AI Agent-driven validation engine
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import uuid4
from typing import Any, List, Dict
from flask import current_app
from rcm_app.extensions import db
from rcm_app.models.models import Master, Refined, Metrics, Audit
from rcm_app.rules.loader import RulesBundle
from rcm_app.agent import RCMValidationAgent, AgentResult


@dataclass
class ValidationSummary:
    inserted: int
    validated: int
    not_validated: int
    agent_errors: int


class AgentValidationEngine:
    """AI Agent-driven validation engine"""
    
    def __init__(self, session, tenant_id: str, rules: RulesBundle) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.rules = rules
        self.agent = RCMValidationAgent(session, tenant_id, rules)
    
    def ingest_and_validate_dataframe(self, df) -> dict[str, Any]:
        """Ingest CSV data and validate using AI agent"""
        required_cols = [
            "encounter_type", "service_date", "national_id", "member_id", 
            "facility_id", "unique_id", "diagnosis_codes", "service_code", 
            "paid_amount_aed", "approval_number"
        ]
        
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"missing required column: {col}")

        inserted = 0
        claims = []
        
        # Insert claims into Master table
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
            claims.append(claim)
            inserted += 1
        
        self.session.commit()
        
        # Validate claims using AI agent
        stats = self._validate_claims_with_agent(claims)
        return {"inserted": inserted, **stats}
    
    def validate_specific_claims(self, claim_ids: List[str]) -> dict[str, Any]:
        """Validate specific claims using AI agent"""
        claims = Master.query.filter(
            Master.tenant_id == self.tenant_id, 
            Master.claim_id.in_(claim_ids)
        ).all()
        return self._validate_claims_with_agent(claims)
    
    def _validate_claims_with_agent(self, claims: List[Master]) -> dict[str, Any]:
        """Validate claims using AI agent"""
        validated = 0
        not_validated = 0
        agent_errors = 0
        
        for claim in claims:
            try:
                # Log validation start
                self._log_audit(claim.claim_id, "validation_started", "success", {
                    "claim_data": self._claim_to_dict(claim)
                })
                
                # Use AI agent for validation
                agent_result = self.agent.validate_claim(claim)
                
                # Update claim with agent results
                claim.status = agent_result.status
                claim.error_type = agent_result.error_type
                claim.error_explanation = agent_result.error_explanation
                claim.recommended_action = agent_result.recommended_action
                
                # Log validation completion
                self._log_audit(claim.claim_id, "validation_completed", "success", {
                    "status": agent_result.status,
                    "error_type": agent_result.error_type,
                    "confidence": agent_result.confidence,
                    "agent_reasoning": agent_result.agent_reasoning
                })
                
                # Update counters
                if agent_result.status == "Validated":
                    validated += 1
                else:
                    not_validated += 1
                
                # Create Refined record
                self._create_refined_record(claim, agent_result)
                
            except Exception as e:
                agent_errors += 1
                current_app.logger.exception(f"Agent validation failed for claim {claim.claim_id}")
                
                # Fallback to basic validation
                claim.status = "Not Validated"
                claim.error_type = "Technical"
                claim.error_explanation = [f"Agent validation failed: {str(e)}"]
                claim.recommended_action = ["Manual review required"]
                
                self._log_audit(claim.claim_id, "validation_failed", "error", {
                    "error": str(e)
                })
                
                not_validated += 1
            
            self.session.add(claim)
        
        self.session.commit()
        self._update_metrics()
        
        return {
            "validated": validated,
            "not_validated": not_validated,
            "agent_errors": agent_errors
        }
    
    def _create_refined_record(self, claim: Master, agent_result: AgentResult) -> None:
        """Create Refined record from agent result"""
        refined = Refined(
            claim_id=claim.claim_id,
            normalized_national_id=claim.national_id,
            normalized_member_id=claim.member_id,
            normalized_facility_id=claim.facility_id,
            status=claim.status,
            error_type=claim.error_type,
            final_action=self._derive_final_action(agent_result),
            tenant_id=self.tenant_id,
        )
        self.session.add(refined)
    
    def _derive_final_action(self, agent_result: AgentResult) -> str:
        """Derive final action from agent result"""
        if agent_result.status == "Validated":
            return "accept"
        elif agent_result.error_type == "Both":
            return "reject"
        elif agent_result.error_type == "Medical":
            return "escalate"
        else:
            return "reject"
    
    def _log_audit(self, claim_id: str, action: str, outcome: str, details: Dict[str, Any] = None) -> None:
        """Log audit entry"""
        try:
            audit = Audit(
                claim_id=claim_id,
                action=action,
                outcome=outcome,
                details=details or {},
                tenant_id=self.tenant_id
            )
            self.session.add(audit)
        except Exception as e:
            current_app.logger.error(f"Failed to log audit: {e}")
    
    def _update_metrics(self) -> None:
        """Update metrics table"""
        try:
            from sqlalchemy import func
            
            # Clear existing metrics for this tenant
            Metrics.query.filter_by(tenant_id=self.tenant_id).delete()
            
            # Calculate new metrics
            rows = db.session.query(
                Master.error_type, 
                func.count(Master.id), 
                func.coalesce(func.sum(Master.paid_amount_aed), 0)
            ).filter(
                Master.tenant_id == self.tenant_id
            ).group_by(Master.error_type).all()
            
            for error_type, count, paid_sum in rows:
                metrics = Metrics(
                    tenant_id=self.tenant_id,
                    error_category=error_type,
                    claim_count=int(count),
                    paid_sum=paid_sum,
                    time_bucket=None,
                )
                self.session.add(metrics)
            
            self.session.commit()
        except Exception as e:
            current_app.logger.error(f"Failed to update metrics: {e}")
    
    def _claim_to_dict(self, claim: Master) -> Dict[str, Any]:
        """Convert claim to dictionary"""
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
            "paid_amount_aed": float(claim.paid_amount_aed) if claim.paid_amount_aed else None,
            "approval_number": claim.approval_number,
            "status": claim.status,
            "error_type": claim.error_type,
            "tenant_id": claim.tenant_id
        }


# Utility functions (same as original engine)
def pd_to_date(val):
    try:
        import pandas as pd
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