#!/usr/bin/env python3
"""
Test script for comprehensive medical claims adjudication system.
This script demonstrates the enhanced validation and correction capabilities.
"""

import os
import sys
import json
import pandas as pd
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from rcm_app import create_app
from rcm_app.extensions import db
from rcm_app.pipeline.engine import ValidationEngine
from rcm_app.rules.loader import TenantConfigLoader

def test_comprehensive_adjudication():
    """Test the comprehensive adjudication system with sample data"""
    
    # Create Flask app and database context
    app = create_app()
    
    with app.app_context():
        # Initialize database
        db.create_all()
        
        # Load tenant configuration
        tenant_id = "tenant_demo"
        tenant_loader = TenantConfigLoader()
        rules_bundle = tenant_loader.load_rules_for_tenant(tenant_id)
        
        # Create validation engine
        engine = ValidationEngine(db.session, tenant_id, rules_bundle)
        
        # Load test data
        test_file = project_root / "tmp_claims.csv"
        if not test_file.exists():
            print(f"Test file not found: {test_file}")
            return
        
        df = pd.read_csv(test_file)
        print(f"Loaded {len(df)} claims for processing...")
        
        # Process claims with comprehensive adjudication
        try:
            result = engine.comprehensive_adjudication(df)
            
            print("\n" + "="*80)
            print("COMPREHENSIVE MEDICAL CLAIMS ADJUDICATION RESULTS")
            print("="*80)
            
            # Display summary
            summary = result["summary"]
            print(f"\nSUMMARY:")
            print(f"  Total Processed: {summary['total_processed']}")
            print(f"  Validated: {summary['validated']}")
            print(f"  Not Validated: {summary['not_validated']}")
            print(f"  Corrections Applied: {summary['corrections_applied']}")
            print(f"\nError Types:")
            for error_type, count in summary['error_types'].items():
                print(f"    {error_type}: {count}")
            
            # Display chart data
            chart_data = result["chart_data"]
            print(f"\nCHART DATA:")
            print(f"  Claim Counts by Error Type: {chart_data['claim_counts_by_error']}")
            print(f"  Paid Amounts by Error Type: {chart_data['paid_amount_by_error']}")
            
            # Display detailed results for first 5 claims
            print(f"\nDETAILED CLAIM RESULTS (First 5):")
            print("-" * 80)
            
            for i, claim in enumerate(result["claims"][:5]):
                print(f"\nClaim {i+1}: {claim['claim_id']}")
                print(f"  Service Code: {claim['service_code']}")
                print(f"  Encounter Type: {claim['encounter_type']}")
                print(f"  Diagnosis Codes: {claim['diagnosis_codes']}")
                print(f"  Paid Amount: AED {claim['paid_amount_aed']}")
                print(f"  Approval Number: {claim['approval_number']}")
                print(f"  Unique ID: {claim['unique_id']}")
                print(f"  Status: {claim['status']}")
                print(f"  Error Type: {claim['error_type']}")
                
                if claim['corrections_applied']:
                    print(f"  Corrections Applied: {claim['corrections_applied']}")
                
                if claim['error_explanation']:
                    print(f"  Error Explanations:")
                    for exp in claim['error_explanation']:
                        print(f"    - {exp}")
                
                if claim['recommended_action']:
                    print(f"  Recommended Actions:")
                    for action in claim['recommended_action']:
                        print(f"    - {action}")
                
                print(f"  Summary: {claim['summary']}")
            
            # Save detailed results to JSON file
            output_file = project_root / "adjudication_results.json"
            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2, default=str)
            print(f"\nDetailed results saved to: {output_file}")
            
            print(f"\n" + "="*80)
            print("ADJUDICATION COMPLETE")
            print("="*80)
            
        except Exception as e:
            print(f"Error during adjudication: {e}")
            import traceback
            traceback.print_exc()

def test_specific_validation_rules():
    """Test specific validation rules mentioned in requirements"""
    
    app = create_app()
    
    with app.app_context():
        db.create_all()
        
        tenant_id = "tenant_demo"
        tenant_loader = TenantConfigLoader()
        rules_bundle = tenant_loader.load_rules_for_tenant(tenant_id)
        engine = ValidationEngine(db.session, tenant_id, rules_bundle)
        
        # Test cases for specific rules
        test_cases = [
            {
                "name": "Missing Approval for High Amount",
                "data": {
                    "encounter_type": "OUTPATIENT",
                    "service_date": "2024-01-15",
                    "national_id": "TEST001",
                    "member_id": "MB001",
                    "facility_id": "FC001",
                    "unique_id": "TEST-001-MB001-FC001",
                    "diagnosis_codes": "E11.9",
                    "service_code": "SRV2007",
                    "paid_amount_aed": 300.0,  # Above threshold
                    "approval_number": "NA"
                }
            },
            {
                "name": "Wrong Encounter Type for Inpatient Service",
                "data": {
                    "encounter_type": "OUTPATIENT",  # Should be INPATIENT
                    "service_date": "2024-01-15",
                    "national_id": "TEST002",
                    "member_id": "MB002",
                    "facility_id": "FC002",
                    "unique_id": "TEST-002-MB002-FC002",
                    "diagnosis_codes": "E11.9",
                    "service_code": "SRV1001",  # Inpatient-only service
                    "paid_amount_aed": 150.0,
                    "approval_number": "APP001"
                }
            },
            {
                "name": "Mutually Exclusive Diagnoses",
                "data": {
                    "encounter_type": "OUTPATIENT",
                    "service_date": "2024-01-15",
                    "national_id": "TEST003",
                    "member_id": "MB003",
                    "facility_id": "FC003",
                    "unique_id": "TEST-003-MB003-FC003",
                    "diagnosis_codes": "R73.03;E11.9",  # Mutually exclusive
                    "service_code": "SRV2007",
                    "paid_amount_aed": 200.0,
                    "approval_number": "APP002"
                }
            },
            {
                "name": "Missing Required Diagnosis for Service",
                "data": {
                    "encounter_type": "OUTPATIENT",
                    "service_date": "2024-01-15",
                    "national_id": "TEST004",
                    "member_id": "MB004",
                    "facility_id": "FC004",
                    "unique_id": "TEST-004-MB004-FC004",
                    "diagnosis_codes": "E11.9",  # Wrong diagnosis for SRV2008
                    "service_code": "SRV2008",  # Requires Z34.0
                    "paid_amount_aed": 180.0,
                    "approval_number": "APP003"
                }
            }
        ]
        
        print("\n" + "="*80)
        print("TESTING SPECIFIC VALIDATION RULES")
        print("="*80)
        
        for test_case in test_cases:
            print(f"\nTest Case: {test_case['name']}")
            print("-" * 50)
            
            # Create DataFrame for single claim
            df = pd.DataFrame([test_case['data']])
            
            try:
                result = engine.comprehensive_adjudication(df)
                claim = result['claims'][0]
                
                print(f"  Original Data: {test_case['data']}")
                print(f"  Status: {claim['status']}")
                print(f"  Error Type: {claim['error_type']}")
                print(f"  Corrections: {claim['corrections_applied']}")
                print(f"  Summary: {claim['summary']}")
                
                if claim['error_explanation']:
                    print(f"  Issues Found:")
                    for exp in claim['error_explanation']:
                        print(f"    - {exp}")
                
            except Exception as e:
                print(f"  Error: {e}")

if __name__ == "__main__":
    print("Starting Comprehensive Medical Claims Adjudication Test...")
    test_comprehensive_adjudication()
    test_specific_validation_rules()
    print("\nTest completed!")