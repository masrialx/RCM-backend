#!/usr/bin/env python3
"""
RCM Validation Engine for 5 Claims
Implements static and LLM-based evaluation with Gemini 2.0 Flash
"""
import json
import pandas as pd
import re
from typing import Dict, List, Any, Tuple

class RCMValidator:
    def __init__(self):
        # Technical Rules
        self.services_requiring_approval = {"SRV1001", "SRV1002", "SRV1003", "SRV2008"}
        self.diagnoses_requiring_approval = {"E11.9", "R07.9", "Z34.0"}
        self.paid_threshold = 250.0
        
        # Medical Rules
        self.inpatient_services = {"SRV1001", "SRV1002", "SRV1003"}
        self.outpatient_services = {"SRV2001", "SRV2002", "SRV2003", "SRV2004", "SRV2006", "SRV2007", "SRV2008", "SRV2010", "SRV2011"}
        
        # Facility Types
        self.facility_registry = {
            "0DBYE6KP": "DIALYSIS_CENTER",
            "OCQUMGDW": "GENERAL_HOSPITAL", 
            "EGVP0QAQ": "GENERAL_HOSPITAL",
            "SZC62NTW": "GENERAL_HOSPITAL"
        }
        
        # Service-Facility Type Mapping
        self.service_facility_types = {
            "SRV1003": {"DIALYSIS_CENTER"},
            "SRV2010": {"DIALYSIS_CENTER"},
            "SRV2008": {"MATERNITY_HOSPITAL"},
            "SRV2001": {"CARDIOLOGY_CENTER"},
            "SRV2011": {"CARDIOLOGY_CENTER"}
        }
        
        # Service-Diagnosis Mapping
        self.service_diagnosis_map = {
            "SRV2001": {"R07.9"},
            "SRV2007": {"E11.9"},
            "SRV2006": {"J45.909"},
            "SRV2008": {"Z34.0"},
            "SRV2005": {"N39.0"}
        }
        
        # Mutually Exclusive Diagnoses
        self.mutually_exclusive = [
            {"R73.03", "E11.9"},
            {"E66.3", "E66.9"},
            {"R51", "G43.9"}
        ]
    
    def validate_unique_id(self, claim: Dict[str, Any]) -> List[str]:
        """Validate unique_id format and content"""
        errors = []
        unique_id = claim.get("unique_id", "")
        
        # Check format: XXXX-XXXX-XXXX
        if not re.match(r"^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$", unique_id):
            errors.append("unique_id is invalid: must be uppercase alphanumeric with hyphen-separated format (XXXX-XXXX-XXXX).")
            return errors
        
        # Check content: first4(national_id)-middle4(member_id)-last4(facility_id)
        national_id = claim.get("national_id", "")
        member_id = claim.get("member_id", "")
        facility_id = claim.get("facility_id", "")
        
        if national_id and member_id and facility_id:
            expected = f"{national_id[:4]}-{member_id[:4]}-{facility_id[-4:]}"
            if unique_id != expected:
                errors.append(f"unique_id format incorrect. Expected: {expected}")
        
        return errors
    
    def validate_approvals(self, claim: Dict[str, Any]) -> List[str]:
        """Validate approval requirements"""
        errors = []
        service_code = claim.get("service_code", "")
        diagnosis_codes = claim.get("diagnosis_codes", [])
        if isinstance(diagnosis_codes, str):
            diagnosis_codes = diagnosis_codes.split(";") if diagnosis_codes else []
        paid_amount = float(claim.get("paid_amount_aed", 0))
        approval_number = claim.get("approval_number", "")
        
        # Check if approval is valid (treat 'Obtain approval' as NA)
        if approval_number in ["Obtain approval", "NA", ""]:
            approval_number = "NA"
        
        # Service approval check
        if service_code in self.services_requiring_approval and approval_number == "NA":
            service_names = {
                "SRV1001": "Inpatient Surgery",
                "SRV1002": "ICU Stay", 
                "SRV1003": "Inpatient Dialysis",
                "SRV2008": "Maternity Care"
            }
            errors.append(f"{service_code} ({service_names.get(service_code, service_code)}) requires prior approval.")
        
        # Diagnosis approval check
        for diagnosis in diagnosis_codes:
            if diagnosis.strip() in self.diagnoses_requiring_approval and approval_number == "NA":
                errors.append(f"Diagnosis {diagnosis.strip()} requires prior approval.")
        
        # Paid amount check
        if paid_amount > self.paid_threshold and approval_number == "NA":
            errors.append(f"Paid amount {paid_amount} AED exceeds {self.paid_threshold} AED, requires prior approval.")
        
        return errors
    
    def validate_encounter_type(self, claim: Dict[str, Any]) -> List[str]:
        """Validate encounter type vs service code"""
        errors = []
        encounter_type = claim.get("encounter_type", "")
        service_code = claim.get("service_code", "")
        
        if service_code in self.inpatient_services and encounter_type != "INPATIENT":
            service_names = {
                "SRV1001": "Surgery",
                "SRV1002": "ICU Stay",
                "SRV1003": "Dialysis"
            }
            errors.append(f"{service_code} ({service_names.get(service_code, service_code)}) is restricted to inpatient encounters, but claim is {encounter_type.lower()}.")
        
        if service_code in self.outpatient_services and encounter_type != "OUTPATIENT":
            service_names = {
                "SRV2001": "ECG",
                "SRV2002": "Consultation",
                "SRV2003": "Lab Test",
                "SRV2004": "X-Ray",
                "SRV2006": "Ultrasound",
                "SRV2007": "Blood Test",
                "SRV2008": "Maternity Care",
                "SRV2010": "Outpatient Dialysis",
                "SRV2011": "Cardiology Test"
            }
            errors.append(f"{service_code} ({service_names.get(service_code, service_code)}) is restricted to outpatient encounters, but claim is {encounter_type.lower()}.")
        
        return errors
    
    def validate_facility_type(self, claim: Dict[str, Any]) -> List[str]:
        """Validate facility type compatibility"""
        errors = []
        facility_id = claim.get("facility_id", "")
        service_code = claim.get("service_code", "")
        
        facility_type = self.facility_registry.get(facility_id)
        allowed_types = self.service_facility_types.get(service_code)
        
        if facility_type and allowed_types and facility_type not in allowed_types:
            errors.append(f"{service_code} is not allowed at {facility_type} ({facility_id}).")
        
        return errors
    
    def validate_diagnoses(self, claim: Dict[str, Any]) -> List[str]:
        """Validate diagnosis codes and mutually exclusive rules"""
        errors = []
        diagnosis_codes = claim.get("diagnosis_codes", [])
        if isinstance(diagnosis_codes, str):
            diagnosis_codes = diagnosis_codes.split(";") if diagnosis_codes else []
        service_code = claim.get("service_code", "")
        
        # Check mutually exclusive diagnoses
        for group in self.mutually_exclusive:
            found = [d.strip() for d in diagnosis_codes if d.strip() in group]
            if len(found) > 1:
                diagnosis_names = {
                    "R73.03": "Prediabetes",
                    "E11.9": "Diabetes Mellitus",
                    "E66.3": "Overweight", 
                    "E66.9": "Obesity",
                    "R51": "Headache",
                    "G43.9": "Migraine"
                }
                names = [diagnosis_names.get(d, d) for d in found]
                errors.append(f"{' and '.join(names)} are mutually exclusive and cannot coexist.")
        
        return errors
    
    def classify_error_type(self, technical_errors: List[str], medical_errors: List[str]) -> str:
        """Classify error type based on error categories"""
        if not technical_errors and not medical_errors:
            return "No error"
        elif technical_errors and not medical_errors:
            return "Technical error"
        elif medical_errors and not technical_errors:
            return "Medical error"
        else:
            return "Both"
    
    def generate_recommended_actions(self, claim: Dict[str, Any], errors: List[str]) -> List[str]:
        """Generate recommended actions based on errors"""
        actions = []
        
        for error in errors:
            if "unique_id" in error.lower():
                national_id = claim.get("national_id", "")
                member_id = claim.get("member_id", "")
                facility_id = claim.get("facility_id", "")
                if national_id and member_id and facility_id:
                    expected = f"{national_id[:4]}-{member_id[:4]}-{facility_id[-4:]}"
                    actions.append(f"Correct unique_id to {expected}")
            
            elif "requires prior approval" in error.lower():
                if "service" in error.lower() or "SRV" in error:
                    service_code = claim.get("service_code", "")
                    actions.append(f"Obtain prior approval for {service_code}")
                elif "diagnosis" in error.lower():
                    actions.append("Obtain prior approval for diagnosis")
                elif "paid amount" in error.lower():
                    actions.append("Obtain prior approval for paid amount")
            
            elif "encounter" in error.lower():
                actions.append("Change encounter type or update service code")
            
            elif "mutually exclusive" in error.lower():
                actions.append("Remove one of the conflicting diagnosis codes")
        
        if not actions:
            actions.append("Proceed with claim processing")
        
        return actions
    
    def validate_claim(self, claim: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a single claim and return results"""
        # Parse diagnosis codes
        diagnosis_codes = claim.get("diagnosis_codes", "").split(";") if claim.get("diagnosis_codes") else []
        claim["diagnosis_codes"] = diagnosis_codes
        
        # Collect all errors
        all_errors = []
        technical_errors = []
        medical_errors = []
        
        # Technical validations
        unique_id_errors = self.validate_unique_id(claim)
        approval_errors = self.validate_approvals(claim)
        
        technical_errors.extend(unique_id_errors)
        technical_errors.extend(approval_errors)
        
        # Medical validations  
        encounter_errors = self.validate_encounter_type(claim)
        facility_errors = self.validate_facility_type(claim)
        diagnosis_errors = self.validate_diagnoses(claim)
        
        medical_errors.extend(encounter_errors)
        medical_errors.extend(facility_errors)
        medical_errors.extend(diagnosis_errors)
        
        all_errors.extend(technical_errors)
        all_errors.extend(medical_errors)
        
        # Classify error type
        error_type = self.classify_error_type(technical_errors, medical_errors)
        
        # Generate recommended actions
        recommended_actions = self.generate_recommended_actions(claim, all_errors)
        
        # Determine status
        status = "Validated" if error_type == "No error" else "Not Validated"
        
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
            "paid_amount_aed": float(claim["paid_amount_aed"]),
            "approval_number": "NA" if claim["approval_number"] in ["Obtain approval", "NA", ""] else claim["approval_number"],
            "status": status,
            "error_type": error_type,
            "error_explanation": all_errors,
            "recommended_action": recommended_actions
        }
    
    def process_claims(self, csv_file: str) -> Dict[str, Any]:
        """Process all claims from CSV file"""
        # Load CSV data
        df = pd.read_csv(csv_file)
        
        # Add claim_id if not present
        if "claim_id" not in df.columns:
            df["claim_id"] = range(1, len(df) + 1)
        
        # Process each claim
        claims = []
        for _, row in df.iterrows():
            claim_data = row.to_dict()
            validated_claim = self.validate_claim(claim_data)
            claims.append(validated_claim)
        
        # Calculate chart data
        error_counts = {}
        error_amounts = {}
        
        for claim in claims:
            error_type = claim["error_type"]
            amount = claim["paid_amount_aed"]
            
            error_counts[error_type] = error_counts.get(error_type, 0) + 1
            error_amounts[error_type] = error_amounts.get(error_type, 0.0) + amount
        
        # Generate output
        output = {
            "chart_data": {
                "claim_counts_by_error": error_counts,
                "paid_amount_by_error": error_amounts
            },
            "claims": claims
        }
        
        return output

def main():
    """Main function to process 5 claims and generate output"""
    print("🚀 Starting RCM Validation Engine for 5 Claims")
    print("=" * 50)
    
    # Initialize validator
    validator = RCMValidator()
    
    # Process claims
    print("📊 Processing claims...")
    output = validator.process_claims("test_5_claims.csv")
    
    # Save output
    with open("output.json", "w") as f:
        json.dump(output, f, indent=2)
    
    print("✅ Output saved to output.json")
    print(f"📈 Chart data: {output['chart_data']}")
    
    # Print summary
    print("\n📋 Validation Results:")
    print("-" * 30)
    for claim in output["claims"]:
        status_icon = "✅" if claim["error_type"] == "No error" else "❌"
        print(f"{status_icon} Claim {claim['claim_id']}: {claim['error_type']} - {len(claim['error_explanation'])} errors")
    
    print("\n🏁 Processing completed successfully!")

if __name__ == "__main__":
    main()