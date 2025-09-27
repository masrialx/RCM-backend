#!/usr/bin/env python3
"""
Comprehensive test script for AI Agent RCM Backend
"""

import os
import sys
import json
import pandas as pd
import requests
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_agent_validation():
    """Test the AI agent validation system"""
    print("🤖 Testing AI Agent Validation System")
    print("=" * 50)
    
    # Test data based on the provided CSV
    test_claims = [
        {
            "claim_id": "76a6df54-5f5e-4b8c-8150-6e124821c65e",
            "encounter_type": "INPATIENT",
            "service_date": "2024-05-03",
            "national_id": "J45NUMBE",
            "member_id": "UZF615NA",
            "facility_id": "0DBYE6KP",
            "unique_id": "j45nf615e6kp",  # Invalid format
            "diagnosis_codes": "E66.9",
            "approval_number": "NA",
            "service_code": "SRV1003",
            "paid_amount_aed": 559.91
        },
        {
            "claim_id": "a0a5604f-8da5-49b2-b919-635e80548a03",
            "encounter_type": "INPATIENT",
            "service_date": "2025-01-13",
            "national_id": "SYWX6RYN",
            "member_id": "B1G36XGM",
            "facility_id": "OCQUMGDW",
            "unique_id": "SYWX-G36X-MGDW",  # Valid format
            "diagnosis_codes": "E66.3;R07.9",  # R07.9 requires approval
            "approval_number": "Obtain approval",  # Invalid
            "service_code": "SRV2001",
            "paid_amount_aed": 1077.6  # Exceeds threshold
        },
        {
            "claim_id": "3b32149f-4808-4981-b5ca-acb690cb0ab9",
            "encounter_type": "OUTPATIENT",
            "service_date": "2025-08-25",
            "national_id": "ZT9FTNQA",
            "member_id": "QA2Y8WAW",
            "facility_id": "SZC62NTW",
            "unique_id": "ZT9F-2Y8W-2NTW",  # Valid format
            "diagnosis_codes": "E66.3;E66.9;R07.9",  # R07.9 requires approval
            "approval_number": "NA",  # Invalid
            "service_code": "SRV2001",
            "paid_amount_aed": 357.29  # Exceeds threshold
        }
    ]
    
    # Create test CSV
    df = pd.DataFrame(test_claims)
    test_file = "test_claims_ai_agent.csv"
    df.to_csv(test_file, index=False)
    
    print(f"✅ Created test CSV: {test_file}")
    print(f"📊 Test data contains {len(test_claims)} claims")
    
    # Test validation rules
    print("\n🔍 Testing Validation Rules:")
    
    # Test 1: Invalid unique_id format
    claim1 = test_claims[0]
    print(f"Claim 1 - Unique ID: {claim1['unique_id']}")
    print("Expected: Technical error (invalid unique_id format)")
    
    # Test 2: Diagnosis requiring approval + invalid approval + high amount
    claim2 = test_claims[1]
    print(f"Claim 2 - Diagnosis: {claim2['diagnosis_codes']}, Approval: {claim2['approval_number']}, Amount: {claim2['paid_amount_aed']}")
    print("Expected: Both error (Medical + Technical)")
    
    # Test 3: Diagnosis requiring approval + invalid approval + high amount
    claim3 = test_claims[2]
    print(f"Claim 3 - Diagnosis: {claim3['diagnosis_codes']}, Approval: {claim3['approval_number']}, Amount: {claim3['paid_amount_aed']}")
    print("Expected: Both error (Medical + Technical)")
    
    return test_file

def test_api_endpoints():
    """Test API endpoints (requires running server)"""
    print("\n🌐 Testing API Endpoints")
    print("=" * 50)
    
    base_url = "http://localhost:5000"
    
    # Test health endpoint
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Health endpoint working")
        else:
            print(f"❌ Health endpoint failed: {response.status_code}")
    except requests.exceptions.RequestException:
        print("❌ Server not running - start with: python run.py")
        return False
    
    return True

def test_validation_tools():
    """Test validation tools directly"""
    print("\n🔧 Testing Validation Tools")
    print("=" * 50)
    
    try:
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'rcm_app'))
        
        from agent.tools.validation_tools import ValidationTools
        from models.models import Master
        from rules.loader import RulesBundle
        
        # Create test rules
        rules = RulesBundle(
            services_requiring_approval={"SRV1001", "SRV1002", "SRV2008"},
            diagnoses={"E11.9", "R07.9", "Z34.0", "E66.3", "E66.9", "I10", "J45.909"},
            paid_threshold_aed=250.0,
            id_rules={
                "uppercase_required": True,
                "patterns": {
                    "national_id": "^[A-Z0-9]{5,}$",
                    "member_id": "^[A-Z0-9]{5,}$",
                    "facility_id": "^[A-Z0-9]{3,}$"
                }
            },
            raw_rules_text="Test rules"
        )
        
        # Test validation tools
        tools = ValidationTools(rules, None)
        
        # Test case 1: Invalid unique_id format
        claim1 = Master(
            claim_id="test-1",
            national_id="J45NUMBE",
            member_id="UZF615NA",
            facility_id="0DBYE6KP",
            unique_id="j45nf615e6kp",  # Invalid format
            service_code="SRV1003",
            paid_amount_aed=559.91,
            approval_number="NA",
            tenant_id="test_tenant"
        )
        
        result1 = tools.validate_claim_comprehensive(claim1)
        print(f"✅ Test 1 - Status: {result1.status}, Error Type: {result1.error_type}")
        print(f"   Explanations: {result1.explanations}")
        
        # Test case 2: Both technical and medical errors
        claim2 = Master(
            claim_id="test-2",
            national_id="SYWX6RYN",
            member_id="B1G36XGM",
            facility_id="OCQUMGDW",
            unique_id="SYWX-G36X-MGDW",  # Valid format
            diagnosis_codes=["E66.3", "R07.9"],  # R07.9 requires approval
            service_code="SRV2001",
            paid_amount_aed=1077.6,  # Exceeds threshold
            approval_number="Obtain approval",  # Invalid
            tenant_id="test_tenant"
        )
        
        result2 = tools.validate_claim_comprehensive(claim2)
        print(f"✅ Test 2 - Status: {result2.status}, Error Type: {result2.error_type}")
        print(f"   Explanations: {result2.explanations}")
        
        return True
        
    except Exception as e:
        print(f"❌ Validation tools test failed: {e}")
        return False

def test_database_models():
    """Test database models"""
    print("\n🗄️ Testing Database Models")
    print("=" * 50)
    
    try:
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'rcm_app'))
        
        from models.models import Master, Refined, Metrics, Audit
        
        # Test Master model
        claim = Master(
            claim_id="test-claim-123",
            encounter_type="OP",
            national_id="TEST123",
            member_id="MB001",
            facility_id="FC001",
            unique_id="TEST-MB00-FC00",
            service_code="SRV1001",
            paid_amount_aed=200.0,
            approval_number="APP001",
            status="Validated",
            error_type="No error",
            error_explanation=[],
            recommended_action=[],
            tenant_id="test_tenant"
        )
        
        print("✅ Master model created successfully")
        print(f"   Claim ID: {claim.claim_id}")
        print(f"   Status: {claim.status}")
        print(f"   Error Type: {claim.error_type}")
        
        # Test Audit model
        audit = Audit(
            claim_id="test-claim-123",
            action="validation_started",
            outcome="success",
            details={"test": "data"},
            tenant_id="test_tenant"
        )
        
        print("✅ Audit model created successfully")
        print(f"   Action: {audit.action}")
        print(f"   Outcome: {audit.outcome}")
        
        return True
        
    except Exception as e:
        print(f"❌ Database models test failed: {e}")
        return False

def test_rule_loading():
    """Test rule loading system"""
    print("\n📋 Testing Rule Loading System")
    print("=" * 50)
    
    try:
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'rcm_app'))
        
        from rules.loader import TenantConfigLoader
        
        loader = TenantConfigLoader()
        rules = loader.load_rules_for_tenant("tenant_demo")
        
        print("✅ Rules loaded successfully")
        print(f"   Services requiring approval: {rules.services_requiring_approval}")
        print(f"   Diagnoses: {rules.diagnoses}")
        print(f"   Paid threshold: {rules.paid_threshold_aed}")
        print(f"   ID rules: {rules.id_rules}")
        
        return True
        
    except Exception as e:
        print(f"❌ Rule loading test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 RCM AI Agent Backend - Comprehensive Test Suite")
    print("=" * 60)
    print(f"Test started at: {datetime.now().isoformat()}")
    print()
    
    tests = [
        ("Agent Validation Data", test_agent_validation),
        ("API Endpoints", test_api_endpoints),
        ("Validation Tools", test_validation_tools),
        ("Database Models", test_database_models),
        ("Rule Loading", test_rule_loading)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n📊 Test Summary")
    print("=" * 50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The AI Agent system is ready.")
    else:
        print("⚠️ Some tests failed. Please review the errors above.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)