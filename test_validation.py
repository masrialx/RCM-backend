#!/usr/bin/env python3
"""
Test script to validate the 8 claims and generate output.json
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
    app = create_app()
    
    with app.app_context():
        # Clear existing data
        Master.query.delete()
        db.session.commit()
        
        # Load test data
        df = pd.read_csv('test_8_claims.csv')
        
        # Add claim_id column if not present
        if 'claim_id' not in df.columns:
            df['claim_id'] = range(1, len(df) + 1)
        
        # Load rules
        tenant_loader = TenantConfigLoader()
        rules_bundle = tenant_loader.load_rules_for_tenant('tenant_demo')
        
        # Create validation engine
        engine = ValidationEngine(db.session, 'tenant_demo', rules_bundle)
        
        # Process claims
        print("Processing claims...")
        summary = engine.ingest_and_validate_dataframe(df)
        print(f"Summary: {summary}")
        
        # Get all claims
        claims = Master.query.filter_by(tenant_id='tenant_demo').order_by(Master.claim_id).all()
        
        # Generate output
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
        
        for claim in claims:
            error_type = claim.error_type or "No error"
            amount = float(claim.paid_amount_aed) if claim.paid_amount_aed else 0.0
            
            error_counts[error_type] = error_counts.get(error_type, 0) + 1
            error_amounts[error_type] = error_amounts.get(error_type, 0.0) + amount
            
            # Format claim data
            claim_data = {
                "claim_id": int(claim.claim_id),
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
        
        print("Output saved to output.json")
        print(f"Chart data: {output['chart_data']}")
        
        # Print summary
        for claim in output["claims"]:
            print(f"Claim {claim['claim_id']}: {claim['error_type']} - {claim['error_explanation']}")

if __name__ == "__main__":
    main()