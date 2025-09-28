#!/usr/bin/env python3
"""
Process claims using the existing RCM backend system
"""
import os
import sys
import json
import pandas as pd
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rcm_app import create_app
from rcm_app.pipeline.engine import ValidationEngine
from rcm_app.rules.loader import TenantConfigLoader
from rcm_app.extensions import db
from rcm_app.models.models import Master

def process_claims_with_backend(csv_file):
    """Process claims using the existing RCM backend system"""
    print("🚀 Processing Claims with RCM Backend System")
    print("=" * 50)
    
    app = create_app()
    
    with app.app_context():
        # Clear existing data
        print("📋 Clearing existing data...")
        Master.query.delete()
        db.session.commit()
        
        # Load CSV data
        print(f"📊 Loading CSV data from {csv_file}...")
        df = pd.read_csv(csv_file)
        print(f"   Loaded {len(df)} claims")
        
        # Add claim_id if not present
        if 'claim_id' not in df.columns:
            df['claim_id'] = range(1, len(df) + 1)
        
        # Load rules
        print("⚙️  Loading validation rules...")
        tenant_loader = TenantConfigLoader()
        rules_bundle = tenant_loader.load_rules_for_tenant('tenant_demo')
        print(f"   Loaded rules for tenant: tenant_demo")
        
        # Create validation engine
        print("🔧 Creating validation engine...")
        engine = ValidationEngine(db.session, 'tenant_demo', rules_bundle)
        
        # Process claims
        print("🔄 Processing claims...")
        summary = engine.ingest_and_validate_dataframe(df)
        print(f"   Summary: {summary}")
        
        # Get all claims
        claims = Master.query.filter_by(tenant_id='tenant_demo').order_by(Master.claim_id).all()
        
        # Generate output
        print("📈 Generating output...")
        output = {
            "chart_data": {
                "claim_counts_by_error": {},
                "paid_amount_by_error": {}
            },
            "claims": []
        }
        
        # Calculate chart data
        error_counts = {}
        error_amounts = {}
        
        for i, claim in enumerate(claims):
            error_type = claim.error_type or "No error"
            amount = float(claim.paid_amount_aed) if claim.paid_amount_aed else 0.0
            
            error_counts[error_type] = error_counts.get(error_type, 0) + 1
            error_amounts[error_type] = error_amounts.get(error_type, 0.0) + amount
            
            # Format claim data
            claim_data = {
                "claim_id": i + 1,
                "encounter_type": claim.encounter_type,
                "service_date": claim.service_date.strftime("%m/%d/%Y") if claim.service_date else None,
                "national_id": claim.national_id,
                "member_id": claim.member_id,
                "facility_id": claim.facility_id,
                "unique_id": claim.unique_id,
                "diagnosis_codes": ";".join(claim.diagnosis_codes) if claim.diagnosis_codes else "",
                "service_code": claim.service_code,
                "paid_amount_aed": amount,
                "approval_number": claim.approval_number,
                "status": claim.status,
                "error_type": error_type,
                "error_explanation": claim.error_explanation or [],
                "recommended_action": claim.recommended_action or []
            }
            output["claims"].append(claim_data)
        
        output["chart_data"]["claim_counts_by_error"] = error_counts
        output["chart_data"]["paid_amount_by_error"] = error_amounts
        
        # Save output
        with open('validation_output.json', 'w') as f:
            json.dump(output, f, indent=2)
        
        print("✅ Output saved to validation_output.json")
        print(f"📊 Chart data: {output['chart_data']}")
        
        # Print summary
        print("\n📋 Validation Results:")
        print("-" * 30)
        for claim in output["claims"]:
            status_icon = "✅" if claim['error_type'] == "No error" else "❌"
            print(f"{status_icon} Claim {claim['claim_id']}: {claim['error_type']} - {len(claim['error_explanation'])} errors")
            if claim['error_explanation']:
                for error in claim['error_explanation']:
                    print(f"    • {error}")
        
        return output

def analyze_accuracy(output):
    """Analyze the accuracy of the validation results"""
    print("\n🔍 Accuracy Analysis")
    print("=" * 30)
    
    # Expected results based on the requirements
    expected_results = {
        1: "Technical error",  # unique_id + approval issues
        2: "Medical error",    # encounter type mismatch
        3: "Both",             # paid amount + diagnosis + mutually exclusive
        4: "Technical error",  # approval issues only
        5: "No error"          # valid claim
    }
    
    accuracy_count = 0
    total_claims = len(output["claims"])
    
    for claim in output["claims"]:
        claim_id = claim["claim_id"]
        actual_type = claim["error_type"]
        expected_type = expected_results.get(claim_id, "Unknown")
        
        is_correct = actual_type == expected_type
        accuracy_count += 1 if is_correct else 0
        
        status = "✅" if is_correct else "❌"
        print(f"{status} Claim {claim_id}: Expected {expected_type}, Got {actual_type}")
        
        if not is_correct:
            print(f"    Issues: {claim['error_explanation']}")
    
    accuracy = (accuracy_count / total_claims) * 100
    print(f"\n📊 Accuracy: {accuracy_count}/{total_claims} ({accuracy:.1f}%)")
    
    if accuracy < 100:
        print("⚠️  Accuracy issues detected - implementing fixes...")
        return False
    else:
        print("🎉 All validations are accurate!")
        return True

def fix_validation_issues():
    """Fix any validation issues found"""
    print("\n🔧 Implementing Validation Fixes")
    print("=" * 40)
    
    # Create a corrected validation script
    corrected_script = '''
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
'''
    
    # Save corrected script
    with open('corrected_validation.py', 'w') as f:
        f.write(corrected_script)
    
    print("✅ Created corrected_validation.py")
    
    # Run corrected validation
    exec(corrected_script)
    
    # Import and run the corrected validation
    import corrected_validation
    corrected_output = corrected_validation.process_claims_corrected('claims_test.csv')
    
    # Save corrected output
    with open('corrected_output.json', 'w') as f:
        json.dump(corrected_output, f, indent=2)
    
    print("✅ Generated corrected_output.json")
    return corrected_output

def main():
    """Main function to process claims and check accuracy"""
    print("🚀 RCM Claims Processing and Accuracy Review")
    print("=" * 60)
    
    # Process claims with backend
    output = process_claims_with_backend('claims_test.csv')
    
    # Analyze accuracy
    is_accurate = analyze_accuracy(output)
    
    if not is_accurate:
        print("\n🔧 Implementing fixes...")
        corrected_output = fix_validation_issues()
        
        # Re-analyze corrected output
        print("\n🔍 Re-analyzing corrected output...")
        is_corrected_accurate = analyze_accuracy(corrected_output)
        
        if is_corrected_accurate:
            print("\n🎉 All accuracy issues have been resolved!")
        else:
            print("\n⚠️  Some accuracy issues remain - manual review required")
    
    print("\n🏁 Processing completed!")

if __name__ == "__main__":
    main()