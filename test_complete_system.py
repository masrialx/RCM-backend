#!/usr/bin/env python3
"""
Complete system test for RCM validation engine
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

def main():
    print("🚀 Starting RCM Validation Engine Test")
    print("=" * 50)
    
    app = create_app()
    
    with app.app_context():
        # Clear existing data
        print("📋 Clearing existing data...")
        Master.query.delete()
        db.session.commit()
        
        # Load test data
        print("📊 Loading test data...")
        df = pd.read_csv('test_8_claims.csv')
        print(f"   Loaded {len(df)} claims")
        
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
        with open('output.json', 'w') as f:
            json.dump(output, f, indent=2)
        
        print("✅ Output saved to output.json")
        print(f"📊 Chart data: {output['chart_data']}")
        
        # Print summary
        print("\n📋 Validation Results:")
        print("-" * 30)
        for claim in output["claims"]:
            status_icon = "✅" if claim['error_type'] == "No error" else "❌"
            print(f"{status_icon} Claim {claim['claim_id']}: {claim['error_type']} - {len(claim['error_explanation'])} errors")
        
        # Check against expected output
        print("\n🔍 Comparing with expected output...")
        try:
            with open('expected_output.json', 'r') as f:
                expected = json.load(f)
            
            # Compare chart data
            if output['chart_data'] == expected['chart_data']:
                print("✅ Chart data matches expected output")
            else:
                print("❌ Chart data does not match expected output")
                print(f"   Expected: {expected['chart_data']}")
                print(f"   Got: {output['chart_data']}")
            
            # Compare error types
            matches = 0
            for i, (exp, cur) in enumerate(zip(expected['claims'], output['claims'])):
                if exp['error_type'] == cur['error_type']:
                    matches += 1
                else:
                    print(f"❌ Claim {i+1}: Expected {exp['error_type']}, Got {cur['error_type']}")
            
            print(f"✅ Error types match: {matches}/8 claims")
            
            if matches == 8 and output['chart_data'] == expected['chart_data']:
                print("\n🎉 SUCCESS: All validations match expected output!")
            else:
                print("\n⚠️  WARNING: Some validations do not match expected output")
                
        except FileNotFoundError:
            print("⚠️  Expected output file not found, skipping comparison")
        
        print("\n🏁 Test completed successfully!")

if __name__ == "__main__":
    main()