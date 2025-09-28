
#!/usr/bin/env python3
"""
Corrected RCM Validation Engine
"""
import json
import pandas as pd
import re
from typing import Dict, List, Any

class CorrectedRCMValidator:
    def __init__(self):
        # Technical Rules
        self.services_requiring_approval = {"SRV1001", "SRV1002", "SRV1003", "SRV2008"}
        self.diagnoses_requiring_approval = {"E11.9", "R07.9", "Z34.0"}
        self.paid_threshold = 250.0
        
        # Medical Rules
        self.inpatient_services = {"SRV1001", "SRV1002", "SRV1003"}
        self.outpatient_services = {"SRV2001", "SRV2002", "SRV2003", "SRV2004", "SRV2006", "SRV2007", "SRV2008", "SRV2010", "SRV2011"}
        
        # Mutually Exclusive Diagnoses
        self.mutually_exclusive = [
            {"R73.03", "E11.9"},
            {"E66.3", "E66.9"},
            {"R51", "G43.9"}
        ]
    
    def validate_claim(self, claim: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a single claim with corrected logic"""
        errors = []
        technical_errors = []
        medical_errors = []
        
        # Parse diagnosis codes
        diagnosis_codes = claim.get("diagnosis_codes", "").split(";") if claim.get("diagnosis_codes") else []
        
        # Technical validations
        unique_id = claim.get("unique_id", "")
        if not re.match(r"^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$", unique_id):
            technical_errors.append("unique_id is invalid: must be uppercase alphanumeric with hyphen-separated format (XXXX-XXXX-XXXX).")
        
        # Approval checks
        service_code = claim.get("service_code", "")
        paid_amount = float(claim.get("paid_amount_aed", 0))
        approval_number = claim.get("approval_number", "")
        
        if approval_number in ["Obtain approval", "NA", ""]:
            approval_number = "NA"
        
        if service_code in self.services_requiring_approval and approval_number == "NA":
            technical_errors.append(f"{service_code} requires prior approval.")
        
        for diagnosis in diagnosis_codes:
            if diagnosis.strip() in self.diagnoses_requiring_approval and approval_number == "NA":
                technical_errors.append(f"Diagnosis {diagnosis.strip()} requires prior approval.")
        
        if paid_amount > self.paid_threshold and approval_number == "NA":
            technical_errors.append(f"Paid amount {paid_amount} AED exceeds {self.paid_threshold} AED, requires prior approval.")
        
        # Medical validations
        encounter_type = claim.get("encounter_type", "")
        
        if service_code in self.inpatient_services and encounter_type != "INPATIENT":
            medical_errors.append(f"{service_code} is restricted to inpatient encounters, but claim is {encounter_type.lower()}.")
        
        if service_code in self.outpatient_services and encounter_type != "OUTPATIENT":
            medical_errors.append(f"{service_code} is restricted to outpatient encounters, but claim is {encounter_type.lower()}.")
        
        # Check mutually exclusive diagnoses
        for group in self.mutually_exclusive:
            found = [d.strip() for d in diagnosis_codes if d.strip() in group]
            if len(found) > 1:
                medical_errors.append(f"{' and '.join(found)} are mutually exclusive and cannot coexist.")
        
        # Combine errors
        all_errors = technical_errors + medical_errors
        
        # Classify error type
        if not technical_errors and not medical_errors:
            error_type = "No error"
        elif technical_errors and not medical_errors:
            error_type = "Technical error"
        elif medical_errors and not technical_errors:
            error_type = "Medical error"
        else:
            error_type = "Both"
        
        # Generate recommended actions
        actions = []
        if "unique_id" in str(all_errors).lower():
            national_id = claim.get("national_id", "")
            member_id = claim.get("member_id", "")
            facility_id = claim.get("facility_id", "")
            if national_id and member_id and facility_id:
                expected = f"{national_id[:4]}-{member_id[:4]}-{facility_id[-4:]}"
                actions.append(f"Correct unique_id to {expected}")
        
        if "approval" in str(all_errors).lower():
            if service_code in self.services_requiring_approval:
                actions.append(f"Obtain prior approval for {service_code}")
            if any(d in self.diagnoses_requiring_approval for d in diagnosis_codes):
                actions.append("Obtain prior approval for diagnosis")
            if paid_amount > self.paid_threshold:
                actions.append("Obtain prior approval for paid amount")
        
        if "encounter" in str(all_errors).lower():
            actions.append("Change encounter type or update service code")
        
        if "mutually exclusive" in str(all_errors).lower():
            actions.append("Remove one of the conflicting diagnosis codes")
        
        if not actions:
            actions.append("Proceed with claim processing")
        
        return {
            "claim_id": claim["claim_id"],
            "encounter_type": claim["encounter_type"],
            "service_date": claim["service_date"],
            "national_id": claim["national_id"],
            "member_id": claim["member_id"],
            "facility_id": claim["facility_id"],
            "unique_id": claim["unique_id"],
            "diagnosis_codes": ";".join(diagnosis_codes),
            "service_code": claim["service_code"],
            "paid_amount_aed": paid_amount,
            "approval_number": "NA" if approval_number == "NA" else claim["approval_number"],
            "status": "Validated" if error_type == "No error" else "Not Validated",
            "error_type": error_type,
            "error_explanation": all_errors,
            "recommended_action": actions
        }

def process_claims_corrected(csv_file):
    """Process claims with corrected validation logic"""
    df = pd.read_csv(csv_file)
    if "claim_id" not in df.columns:
        df["claim_id"] = range(1, len(df) + 1)
    
    validator = CorrectedRCMValidator()
    claims = []
    
    for _, row in df.iterrows():
        claim_data = row.to_dict()
        validated_claim = validator.validate_claim(claim_data)
        claims.append(validated_claim)
    
    # Calculate chart data
    error_counts = {}
    error_amounts = {}
    
    for claim in claims:
        error_type = claim["error_type"]
        amount = claim["paid_amount_aed"]
        
        error_counts[error_type] = error_counts.get(error_type, 0) + 1
        error_amounts[error_type] = error_amounts.get(error_type, 0.0) + amount
    
    return {
        "chart_data": {
            "claim_counts_by_error": error_counts,
            "paid_amount_by_error": error_amounts
        },
        "claims": claims
    }
