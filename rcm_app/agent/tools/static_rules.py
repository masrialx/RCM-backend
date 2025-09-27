"""
Static rules validation tool
"""

from typing import Dict, Any
from langchain.tools import BaseTool
from pydantic import BaseModel, Field


class StaticRulesInput(BaseModel):
    """Input for static rules validation"""
    claim_data: Dict[str, Any] = Field(description="Claim data to validate")
    rules: Dict[str, Any] = Field(description="Rules to apply")


class StaticRulesTool(BaseTool):
    """Tool for applying static business rules"""
    
    name: str = "apply_static_rules"
    description: str = "Apply static business rules for service codes, diagnosis codes, and paid amounts"
    args_schema: type = StaticRulesInput
    
    def _run(self, claim_data: Dict[str, Any], rules: Dict[str, Any]) -> str:
        """Apply static rules to claim data"""
        errors = []
        error_types = set()
        
        # Check service code approval
        service_code = claim_data.get("service_code")
        approval_number = claim_data.get("approval_number")
        services_requiring_approval = rules.get("services_requiring_approval", [])
        
        if service_code in services_requiring_approval:
            if not approval_number or approval_number in ["NA", "Obtain approval", ""]:
                errors.append(f"Service code {service_code} requires approval")
                error_types.add("Technical")
        
        # Check diagnosis code approval
        diagnosis_codes = claim_data.get("diagnosis_codes", [])
        diagnoses_requiring_approval = ["E11.9", "R07.9", "Z34.0"]
        
        for diagnosis in diagnosis_codes:
            if diagnosis in diagnoses_requiring_approval:
                if not approval_number or approval_number in ["NA", "Obtain approval", ""]:
                    errors.append(f"Diagnosis code {diagnosis} requires approval")
                    error_types.add("Medical")
        
        # Check paid amount threshold
        paid_amount = claim_data.get("paid_amount_aed", 0)
        threshold = rules.get("paid_threshold_aed", 250)
        
        if paid_amount > threshold:
            if not approval_number or approval_number in ["NA", "Obtain approval", ""]:
                errors.append(f"Paid amount {paid_amount} exceeds threshold {threshold}")
                error_types.add("Technical")
        
        # Determine error type
        if not error_types:
            error_type = "No error"
        elif "Technical" in error_types and "Medical" in error_types:
            error_type = "Both"
        elif "Medical" in error_types:
            error_type = "Medical"
        else:
            error_type = "Technical"
        
        return f"Static rules validation: {error_type} - {', '.join(errors) if errors else 'No errors'}"