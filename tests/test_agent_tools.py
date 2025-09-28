# """
# Unit tests for AI agent validation tools
# """

# import pytest
# import unittest
# from unittest.mock import Mock, patch
# from rcm_app.agent.tools.validation_tools import ValidationTools, ValidationResult
# from rcm_app.models.models import Master
# from rcm_app.rules.loader import RulesBundle


# class TestValidationTools(unittest.TestCase):
#     """Test validation tools functionality"""
    
#     def setUp(self):
#         """Set up test fixtures"""
#         self.rules = RulesBundle(
#             services_requiring_approval={"SRV1001", "SRV1002", "SRV2008"},
#             diagnoses={"E11.9", "R07.9", "Z34.0", "E66.3", "E66.9", "I10", "J45.909"},
#             paid_threshold_aed=250.0,
#             id_rules={
#                 "uppercase_required": True,
#                 "patterns": {
#                     "national_id": "^[A-Z0-9]{5,}$",
#                     "member_id": "^[A-Z0-9]{5,}$",
#                     "facility_id": "^[A-Z0-9]{3,}$"
#                 }
#             },
#             raw_rules_text="Test rules"
#         )
#         self.session = Mock()
#         self.tools = ValidationTools(self.rules, self.session)
    
#     def test_check_id_format_valid(self):
#         """Test ID format validation with valid data"""
#         claim = Master(
#             claim_id="test-123",
#             national_id="ABC123",
#             member_id="DEF456",
#             facility_id="GHI789",
#             unique_id="ABC1-DEF4-GHI7",
#             tenant_id="test_tenant"
#         )
        
#         result = self.tools.check_id_format(claim)
        
#         self.assertTrue(result.is_valid)
#         self.assertEqual(result.error_type, "None")
#         self.assertEqual(len(result.explanations), 0)
    
#     def test_check_id_format_invalid_uppercase(self):
#         """Test ID format validation with invalid uppercase"""
#         claim = Master(
#             claim_id="test-123",
#             national_id="abc123",  # lowercase
#             member_id="DEF456",
#             facility_id="GHI789",
#             unique_id="ABC1-DEF4-GHI7",
#             tenant_id="test_tenant"
#         )
        
#         result = self.tools.check_id_format(claim)
        
#         self.assertFalse(result.is_valid)
#         self.assertEqual(result.error_type, "Technical")
#         self.assertIn("national_id", result.explanations[0])
    
#     def test_check_id_format_invalid_unique_id(self):
#         """Test unique_id format validation"""
#         claim = Master(
#             claim_id="test-123",
#             national_id="ABC123",
#             member_id="DEF456",
#             facility_id="GHI789",
#             unique_id="invalid-format",  # wrong format
#             tenant_id="test_tenant"
#         )
        
#         result = self.tools.check_id_format(claim)
        
#         self.assertFalse(result.is_valid)
#         self.assertEqual(result.error_type, "Technical")
#         self.assertIn("unique_id", result.explanations[0])
    
#     def test_apply_static_rules_service_approval(self):
#         """Test service code approval requirement"""
#         claim = Master(
#             claim_id="test-123",
#             service_code="SRV1001",  # requires approval
#             approval_number="NA",  # invalid
#             paid_amount_aed=100.0,
#             tenant_id="test_tenant"
#         )
        
#         result = self.tools.apply_static_rules(claim)
        
#         self.assertFalse(result.is_valid)
#         self.assertEqual(result.error_type, "Technical")
#         self.assertIn("SRV1001", result.explanations[0])
    
#     def test_apply_static_rules_diagnosis_approval(self):
#         """Test diagnosis code approval requirement"""
#         claim = Master(
#             claim_id="test-123",
#             diagnosis_codes=["E11.9"],  # requires approval
#             approval_number="NA",  # invalid
#             paid_amount_aed=100.0,
#             tenant_id="test_tenant"
#         )
        
#         result = self.tools.apply_static_rules(claim)
        
#         self.assertFalse(result.is_valid)
#         self.assertEqual(result.error_type, "Medical")
#         self.assertIn("E11.9", result.explanations[0])
    
#     def test_apply_static_rules_paid_amount_threshold(self):
#         """Test paid amount threshold validation"""
#         claim = Master(
#             claim_id="test-123",
#             paid_amount_aed=300.0,  # exceeds threshold
#             approval_number="NA",  # invalid
#             tenant_id="test_tenant"
#         )
        
#         result = self.tools.apply_static_rules(claim)
        
#         self.assertFalse(result.is_valid)
#         self.assertEqual(result.error_type, "Technical")
#         self.assertIn("300", result.explanations[0])
    
#     def test_apply_static_rules_both_errors(self):
#         """Test both technical and medical errors"""
#         claim = Master(
#             claim_id="test-123",
#             service_code="SRV1001",  # requires approval
#             diagnosis_codes=["E11.9"],  # requires approval
#             approval_number="NA",  # invalid
#             paid_amount_aed=300.0,  # exceeds threshold
#             tenant_id="test_tenant"
#         )
        
#         result = self.tools.apply_static_rules(claim)
        
#         self.assertFalse(result.is_valid)
#         self.assertEqual(result.error_type, "Both")
#         self.assertGreater(len(result.explanations), 1)
    
#     def test_is_valid_approval_number(self):
#         """Test approval number validation"""
#         # Valid formats
#         self.assertTrue(self.tools._is_valid_approval_number("APP001"))
#         self.assertTrue(self.tools._is_valid_approval_number("APR123"))
        
#         # Invalid formats
#         self.assertFalse(self.tools._is_valid_approval_number("NA"))
#         self.assertFalse(self.tools._is_valid_approval_number("Obtain approval"))
#         self.assertFalse(self.tools._is_valid_approval_number(""))
#         self.assertFalse(self.tools._is_valid_approval_number("123"))
    
#     def test_validate_claim_comprehensive_valid(self):
#         """Test comprehensive validation with valid claim"""
#         claim = Master(
#             claim_id="test-123",
#             national_id="ABC123",
#             member_id="DEF456",
#             facility_id="GHI789",
#             unique_id="ABC1-DEF4-GHI7",
#             service_code="SRV2001",  # doesn't require approval
#             diagnosis_codes=["I10"],  # doesn't require approval
#             paid_amount_aed=100.0,  # below threshold
#             approval_number="APP001",  # valid
#             tenant_id="test_tenant"
#         )
        
#         result = self.tools.validate_claim_comprehensive(claim)
        
#         self.assertTrue(result.is_valid)
#         self.assertEqual(result.error_type, "None")
    
#     def test_validate_claim_comprehensive_invalid(self):
#         """Test comprehensive validation with invalid claim"""
#         claim = Master(
#             claim_id="test-123",
#             national_id="abc123",  # invalid case
#             member_id="DEF456",
#             facility_id="GHI789",
#             unique_id="invalid-format",  # invalid format
#             service_code="SRV1001",  # requires approval
#             diagnosis_codes=["E11.9"],  # requires approval
#             paid_amount_aed=300.0,  # exceeds threshold
#             approval_number="NA",  # invalid
#             tenant_id="test_tenant"
#         )
        
#         result = self.tools.validate_claim_comprehensive(claim)
        
#         self.assertFalse(result.is_valid)
#         self.assertEqual(result.error_type, "Both")
#         self.assertGreater(len(result.explanations), 0)
#         self.assertGreater(len(result.recommended_actions), 0)
#     def setUp(self):
#         """Set up test fixtures"""
#         self.rules = RulesBundle(
#             diagnoses_requiring_approval={"E11.9", "R07.9"},
#             facility_registry={"FAC001": "Hospital A", "FAC002": "Clinic B"},
#             service_allowed_facility_types=["Hospital", "Clinic"],
#             services_requiring_approval={"SRV1001", "SRV1002", "SRV2008"},
#             diagnoses={"E11.9", "R07.9", "Z34.0", "E66.3", "E66.9", "I10", "J45.909"},
#             paid_threshold_aed=250.0,
#             id_rules={
#                 "uppercase_required": True,
#                 "patterns": {
#                     "national_id": "^[A-Z0-9]{5,}$",
#                     "member_id": "^[A-Z0-9]{5,}$",
#                     "facility_id": "^[A-Z0-9]{3,}$"
#                 }
#             },
#             raw_rules_text="Test rules"
#         )
#         self.session = Mock()
#         self.tools = ValidationTools(self.rules, self.session)


# if __name__ == "__main__":
#     unittest.main()
