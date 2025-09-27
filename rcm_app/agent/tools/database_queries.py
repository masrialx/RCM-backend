"""
Database query tool for historical context
"""

from typing import Dict, Any, List
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from rcm_app.models.models import Master


class DatabaseQueryInput(BaseModel):
    """Input for database query"""
    claim_id: str = Field(description="Claim ID to query context for")
    tenant_id: str = Field(description="Tenant ID for filtering")
    query_type: str = Field(description="Type of query: similar_claims, service_code_history, diagnosis_history")


class DatabaseQueryTool(BaseTool):
    """Tool for querying database for historical context"""
    
    name: str = "query_database"
    description: str = "Query database for historical claim data and context"
    args_schema: type = DatabaseQueryInput
    
    def __init__(self, session, **kwargs):
        super().__init__(**kwargs)
        # Store session as private attribute
        self._session = session
    
    def _run(self, claim_id: str, tenant_id: str, query_type: str) -> str:
        """Query database for historical context"""
        try:
            if query_type == "similar_claims":
                return self._get_similar_claims(claim_id, tenant_id)
            elif query_type == "service_code_history":
                return self._get_service_code_history(claim_id, tenant_id)
            elif query_type == "diagnosis_history":
                return self._get_diagnosis_history(claim_id, tenant_id)
            else:
                return f"Unknown query type: {query_type}"
                
        except Exception as e:
            return f"Database query error: {str(e)}"
    
    def _get_similar_claims(self, claim_id: str, tenant_id: str) -> str:
        """Get similar claims for context"""
        try:
            # Get the current claim
            current_claim = self._session.query(Master).filter(
                Master.claim_id == claim_id,
                Master.tenant_id == tenant_id
            ).first()
            
            if not current_claim:
                return "Claim not found"
            
            # Get similar claims (same service code or diagnosis)
            similar_claims = self._session.query(Master).filter(
                Master.tenant_id == tenant_id,
                Master.claim_id != claim_id,
                Master.service_code == current_claim.service_code
            ).limit(5).all()
            
            result = {
                "similar_claims_count": len(similar_claims),
                "claims": [
                    {
                        "claim_id": c.claim_id,
                        "service_code": c.service_code,
                        "error_type": c.error_type,
                        "status": c.status,
                        "paid_amount": float(c.paid_amount_aed) if c.paid_amount_aed else 0
                    } for c in similar_claims
                ]
            }
            
            return f"Similar claims found: {result['similar_claims_count']} claims with same service code"
            
        except Exception as e:
            return f"Error getting similar claims: {str(e)}"
    
    def _get_service_code_history(self, claim_id: str, tenant_id: str) -> str:
        """Get service code history"""
        try:
            current_claim = self._session.query(Master).filter(
                Master.claim_id == claim_id,
                Master.tenant_id == tenant_id
            ).first()
            
            if not current_claim:
                return "Claim not found"
            
            # Get all claims with same service code
            service_claims = self._session.query(Master).filter(
                Master.tenant_id == tenant_id,
                Master.service_code == current_claim.service_code
            ).all()
            
            # Calculate statistics
            total_claims = len(service_claims)
            error_counts = {}
            for claim in service_claims:
                error_type = claim.error_type or "No error"
                error_counts[error_type] = error_counts.get(error_type, 0) + 1
            
            return f"Service code {current_claim.service_code} history: {total_claims} total claims, errors: {error_counts}"
            
        except Exception as e:
            return f"Error getting service code history: {str(e)}"
    
    def _get_diagnosis_history(self, claim_id: str, tenant_id: str) -> str:
        """Get diagnosis code history"""
        try:
            current_claim = self._session.query(Master).filter(
                Master.claim_id == claim_id,
                Master.tenant_id == tenant_id
            ).first()
            
            if not current_claim:
                return "Claim not found"
            
            # Get claims with similar diagnosis codes
            diagnosis_claims = []
            if current_claim.diagnosis_codes:
                for diagnosis in current_claim.diagnosis_codes:
                    claims = self._session.query(Master).filter(
                        Master.tenant_id == tenant_id,
                        Master.diagnosis_codes.contains([diagnosis])
                    ).all()
                    diagnosis_claims.extend(claims)
            
            # Remove duplicates
            unique_claims = list({c.claim_id: c for c in diagnosis_claims}.values())
            
            return f"Diagnosis history: {len(unique_claims)} claims with similar diagnosis codes"
            
        except Exception as e:
            return f"Error getting diagnosis history: {str(e)}"