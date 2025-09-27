"""
Main validation tools orchestrator for the AI agent
"""

import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from rcm_app.models.models import Master
from rcm_app.rules.loader import RulesBundle


@dataclass
class ValidationResult:
    """Result of validation with confidence score"""
    is_valid: bool
    error_type: str
    explanations: List[str]
    recommended_actions: List[str]
    confidence: float


class ValidationTools:
    """Main validation tools class that orchestrates all validation checks"""
    
    def __init__(self, rules: RulesBundle, session):
        self.rules = rules
        self.session = session
        self.id_patterns = {
            k: re.compile(v) for k, v in (rules.id_rules.get("patterns", {}) or {}).items()
        }
        self.uppercase_required = bool(rules.id_rules.get("uppercase_required", True))
    
    def check_id_format(self, claim: Master) -> ValidationResult:
        """Validate ID formats according to rules"""
        errors = []
        actions = []
        confidence = 0.95
        
        # Check uppercase requirement
        if self.uppercase_required:
            for field in ["national_id", "member_id", "facility_id", "service_code"]:
                val = getattr(claim, field)
                if val and val != val.upper():
                    errors.append(f"{field} '{val}' must be uppercase")
                    actions.append(f"Convert {field} to uppercase: {val.upper()}")
        
        # Check pattern matching
        for field, pattern in self.id_patterns.items():
            val = getattr(claim, field, None)
            if val and not pattern.fullmatch(val):
                errors.append(f"{field} '{val}' does not match required pattern")
                actions.append(f"Correct {field} format according to rules")
        
        # Check unique_id format specifically
        if claim.unique_id:
            unique_id_error = self._validate_unique_id_format(claim)
            if unique_id_error:
                errors.append(unique_id_error)
                actions.append("Format unique_id as first4(national_id)-middle4(member_id)-last4(facility_id)")
                confidence = 0.99  # High confidence for format violations
        
        if errors:
            return ValidationResult(
                is_valid=False,
                error_type="Technical",
                explanations=errors,
                recommended_actions=actions,
                confidence=confidence
            )
        
        return ValidationResult(
            is_valid=True,
            error_type="No error",
            explanations=[],
            recommended_actions=[],
            confidence=1.0
        )
    
    def _validate_unique_id_format(self, claim: Master) -> Optional[str]:
        """Validate unique_id format: first4(national_id)-middle4(member_id)-last4(facility_id)"""
        if not all([claim.national_id, claim.member_id, claim.facility_id]):
            return "unique_id cannot be validated without national_id, member_id, and facility_id"
        
        expected = f"{claim.national_id[:4]}-{claim.member_id[:4]}-{claim.facility_id[:4]}"
        if claim.unique_id != expected:
            return f"unique_id '{claim.unique_id}' violates formatting rules: Expected '{expected}'"
        return None
    
    def apply_static_rules(self, claim: Master) -> ValidationResult:
        """Apply static business rules for service codes, diagnosis codes, and paid amounts"""
        errors = []
        actions = []
        error_types = set()
        confidence = 0.95
        
        # Check service code approval requirement
        if claim.service_code and claim.service_code in self.rules.services_requiring_approval:
            if not claim.approval_number or claim.approval_number in ["NA", "Obtain approval", ""]:
                errors.append(f"Service code {claim.service_code} requires approval, but approval_number is '{claim.approval_number}'")
                actions.append(f"Obtain valid approval for service code {claim.service_code}")
                error_types.add("Technical")
        
        # Check diagnosis code approval requirement
        if claim.diagnosis_codes:
            for diagnosis in claim.diagnosis_codes:
                if diagnosis in ["E11.9", "R07.9", "Z34.0"]:  # Diagnosis codes requiring approval
                    if not claim.approval_number or claim.approval_number in ["NA", "Obtain approval", ""]:
                        errors.append(f"Diagnosis code {diagnosis} requires approval, but approval_number is '{claim.approval_number}'")
                        actions.append(f"Obtain valid approval for diagnosis code {diagnosis}")
                        error_types.add("Medical")
        
        # Check paid amount threshold
        try:
            paid_amount = float(claim.paid_amount_aed) if claim.paid_amount_aed is not None else 0.0
            threshold = float(self.rules.paid_threshold_aed)
            
            if paid_amount > threshold:
                if not claim.approval_number or claim.approval_number in ["NA", "Obtain approval", ""]:
                    errors.append(f"Paid amount {paid_amount} exceeds threshold {threshold}, requiring approval")
                    actions.append(f"Obtain approval for high paid amount {paid_amount}")
                    error_types.add("Technical")
        except (ValueError, TypeError):
            errors.append("Invalid paid_amount_aed value")
            actions.append("Correct paid_amount_aed format")
            error_types.add("Technical")
        
        # Check approval number validity
        if claim.approval_number and claim.approval_number not in ["NA", "Obtain approval", ""]:
            if not self._is_valid_approval_number(claim.approval_number):
                errors.append(f"Invalid approval_number format: '{claim.approval_number}'")
                actions.append("Provide valid approval number (e.g., APP001)")
                error_types.add("Technical")
        
        if not errors:
            return ValidationResult(
                is_valid=True,
                error_type="No error",
                explanations=[],
                recommended_actions=[],
                confidence=1.0
            )
        
        # Determine error type
        if "Technical" in error_types and "Medical" in error_types:
            error_type = "Both"
        elif "Medical" in error_types:
            error_type = "Medical"
        else:
            error_type = "Technical"
        
        return ValidationResult(
            is_valid=False,
            error_type=error_type,
            explanations=errors,
            recommended_actions=actions,
            confidence=confidence
        )
    
    def _is_valid_approval_number(self, approval_number: str) -> bool:
        """Check if approval number follows valid format (e.g., APP001)"""
        if not approval_number:
            return False
        # Valid format: starts with letters, followed by numbers
        pattern = re.compile(r'^[A-Z]{2,}[0-9]{3,}$')
        return bool(pattern.match(approval_number.upper()))
    
    def query_database(self, claim_id: str, tenant_id: str) -> Dict[str, Any]:
        """Query database for historical context"""
        try:
            # Query for similar claims
            similar_claims = self.session.query(Master).filter(
                Master.tenant_id == tenant_id,
                Master.claim_id != claim_id
            ).limit(5).all()
            
            # Query for claims with same service code
            service_claims = self.session.query(Master).filter(
                Master.tenant_id == tenant_id,
                Master.service_code == self.session.query(Master).filter(
                    Master.claim_id == claim_id
                ).first().service_code
            ).limit(3).all()
            
            return {
                "similar_claims_count": len(similar_claims),
                "service_code_claims_count": len(service_claims),
                "historical_data": [
                    {
                        "claim_id": c.claim_id,
                        "service_code": c.service_code,
                        "error_type": c.error_type,
                        "status": c.status
                    } for c in similar_claims[:3]
                ]
            }
        except Exception as e:
            return {"error": str(e), "historical_data": []}
    
    def mock_external_api(self, approval_number: str) -> Dict[str, Any]:
        """Mock external API call for approval verification"""
        if not approval_number or approval_number in ["NA", "Obtain approval", ""]:
            return {"valid": False, "reason": "No approval number provided"}
        
        # Mock validation logic
        if self._is_valid_approval_number(approval_number):
            return {"valid": True, "reason": "Approval number format is valid"}
        else:
            return {"valid": False, "reason": "Invalid approval number format"}
    
    def validate_claim_comprehensive(self, claim: Master) -> ValidationResult:
        """Comprehensive validation combining all checks"""
        # Step 1: Check ID formats
        id_result = self.check_id_format(claim)
        
        # Step 2: Apply static rules
        rules_result = self.apply_static_rules(claim)
        
        # Combine results
        all_errors = id_result.explanations + rules_result.explanations
        all_actions = id_result.recommended_actions + rules_result.recommended_actions
        
        # Determine overall error type
        error_types = set()
        if not id_result.is_valid:
            error_types.add(id_result.error_type)
        if not rules_result.is_valid:
            error_types.add(rules_result.error_type)
        
        if not error_types:
            final_error_type = "No error"
            is_valid = True
        elif "Both" in error_types or (len(error_types) > 1):
            final_error_type = "Both"
            is_valid = False
        else:
            final_error_type = list(error_types)[0]
            is_valid = False
        
        # Calculate overall confidence
        confidence = min(id_result.confidence, rules_result.confidence) if all_errors else 1.0
        
        return ValidationResult(
            is_valid=is_valid,
            error_type=final_error_type,
            explanations=all_errors,
            recommended_actions=all_actions,
            confidence=confidence
        )