# """
# Integration tests for AI agent system
# """

# import pytest
# import unittest
# from unittest.mock import Mock, patch, MagicMock
# import pandas as pd
# from rcm_app.pipeline.agent_engine import AgentValidationEngine
# from rcm_app.agent import RCMValidationAgent
# from rcm_app.models.models import Master
# from rcm_app.rules.loader import RulesBundle


# class TestAgentIntegration(unittest.TestCase):
#     """Test AI agent integration functionality"""
    
#     def setUp(self):
#         """Set up test fixtures"""
#         self.session = Mock()
#         self.tenant_id = "test_tenant"
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
    
#     @patch('rcm_app.agent.react_agent.ChatGoogleGenerativeAI')
#     def test_agent_validation_engine_initialization(self, mock_llm):
#         """Test agent validation engine initialization"""
#         engine = AgentValidationEngine(self.session, self.tenant_id, self.rules)
        
#         self.assertEqual(engine.tenant_id, self.tenant_id)
#         self.assertEqual(engine.rules, self.rules)
#         self.assertIsNotNone(engine.agent)
    
#     def test_create_test_dataframe(self):
#         """Test creating test data for validation"""
#         test_data = {
#             "claim_id": ["TEST-001", "TEST-002"],
#             "encounter_type": ["OP", "IP"],
#             "service_date": ["2024-01-15", "2024-01-16"],
#             "national_id": ["ABC123", "DEF456"],
#             "member_id": ["MB001", "MB002"],
#             "facility_id": ["FC001", "FC002"],
#             "unique_id": ["ABC1-MB00-FC00", "DEF4-MB00-FC00"],
#             "diagnosis_codes": ["E11.9", "I10"],
#             "service_code": ["SRV1001", "SRV2001"],
#             "paid_amount_aed": [200.0, 150.0],
#             "approval_number": ["APP001", ""]
#         }
        
#         df = pd.DataFrame(test_data)
        
#         self.assertEqual(len(df), 2)
#         self.assertIn("claim_id", df.columns)
#         self.assertIn("service_code", df.columns)
    
#     @patch('rcm_app.agent.react_agent.ChatGoogleGenerativeAI')
#     def test_agent_validation_with_mock_llm(self, mock_llm_class):
#         """Test agent validation with mocked LLM"""
#         # Mock the LLM response
#         mock_llm_instance = Mock()
#         mock_llm_class.return_value = mock_llm_instance
        
#         # Mock agent result
#         mock_agent_result = Mock()
#         mock_agent_result.status = "Not Validated"
#         mock_agent_result.error_type = "Technical"
#         mock_agent_result.error_explanation = ["Test error"]
#         mock_agent_result.recommended_action = ["Test action"]
#         mock_agent_result.confidence = 0.95
#         mock_agent_result.agent_reasoning = "Test reasoning"
        
#         # Mock the agent
#         with patch('rcm_app.pipeline.agent_engine.RCMValidationAgent') as mock_agent_class:
#             mock_agent_instance = Mock()
#             mock_agent_instance.validate_claim.return_value = mock_agent_result
#             mock_agent_class.return_value = mock_agent_instance
            
#             engine = AgentValidationEngine(self.session, self.tenant_id, self.rules)
            
#             # Create test claim
#             claim = Master(
#                 claim_id="test-123",
#                 national_id="ABC123",
#                 member_id="DEF456",
#                 facility_id="GHI789",
#                 unique_id="ABC1-DEF4-GHI7",
#                 service_code="SRV1001",
#                 diagnosis_codes=["E11.9"],
#                 paid_amount_aed=300.0,
#                 approval_number="NA",
#                 tenant_id=self.tenant_id
#             )
            
#             result = engine._validate_claims_with_agent([claim])
            
#             self.assertIn("validated", result)
#             self.assertIn("not_validated", result)
#             self.assertIn("agent_errors", result)
    
#     def test_derive_final_action(self):
#         """Test final action derivation"""
#         engine = AgentValidationEngine(self.session, self.tenant_id, self.rules)
        
#         # Test cases
#         test_cases = [
#             ("Validated", "No error", "accept"),
#             ("Not Validated", "Technical", "reject"),
#             ("Not Validated", "Medical", "escalate"),
#             ("Not Validated", "Both", "reject")
#         ]
        
#         for status, error_type, expected_action in test_cases:
#             mock_result = Mock()
#             mock_result.status = status
#             mock_result.error_type = error_type
            
#             action = engine._derive_final_action(mock_result)
#             self.assertEqual(action, expected_action)
    
#     def test_claim_to_dict_conversion(self):
#         """Test claim to dictionary conversion"""
#         engine = AgentValidationEngine(self.session, self.tenant_id, self.rules)
        
#         claim = Master(
#             claim_id="test-123",
#             encounter_type="OP",
#             service_date=pd.to_datetime("2024-01-15").date(),
#             national_id="ABC123",
#             member_id="DEF456",
#             facility_id="GHI789",
#             unique_id="ABC1-DEF4-GHI7",
#             diagnosis_codes=["E11.9"],
#             service_code="SRV1001",
#             paid_amount_aed=200.0,
#             approval_number="APP001",
#             tenant_id=self.tenant_id
#         )
        
#         claim_dict = engine._claim_to_dict(claim)
        
#         self.assertEqual(claim_dict["claim_id"], "test-123")
#         self.assertEqual(claim_dict["encounter_type"], "OP")
#         self.assertEqual(claim_dict["national_id"], "ABC123")
#         self.assertEqual(claim_dict["diagnosis_codes"], ["E11.9"])
#         self.assertEqual(claim_dict["paid_amount_aed"], 200.0)


# class TestAgentToolsIntegration(unittest.TestCase):
#     """Test integration between agent tools"""
    
#     def setUp(self):
#         """Set up test fixtures"""
#         self.session = Mock()
#         self.tenant_id = "test_tenant"
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
    
#     def test_database_query_tool(self):
#         """Test database query tool functionality"""
#         from rcm_app.agent.tools.database_queries import DatabaseQueryTool
        
#         tool = DatabaseQueryTool(self.session)
        
#         # Mock database response
#         mock_claims = [
#             Mock(claim_id="test-1", service_code="SRV1001", error_type="Technical", status="Not Validated", paid_amount_aed=200.0),
#             Mock(claim_id="test-2", service_code="SRV1001", error_type="None", status="Validated", paid_amount_aed=150.0)
#         ]
        
#         self.session.query.return_value.filter.return_value.limit.return_value.all.return_value = mock_claims
        
#         result = tool._run("test-claim", "test_tenant", "similar_claims")
        
#         self.assertIn("Similar claims found", result)
    
#     def test_external_api_tool(self):
#         """Test external API tool functionality"""
#         from rcm_app.agent.tools.external_api import ExternalAPITool
        
#         tool = ExternalAPITool()
        
#         # Test approval verification
#         result = tool._run("APP001", "approval_verification")
#         self.assertIn("API Response", result)
        
#         # Test invalid approval
#         result = tool._run("NA", "approval_verification")
#         self.assertIn("failed", result)
    
#     def test_static_rules_tool(self):
#         """Test static rules tool functionality"""
#         from rcm_app.agent.tools.static_rules import StaticRulesTool
        
#         tool = StaticRulesTool()
        
#         claim_data = {
#             "service_code": "SRV1001",
#             "approval_number": "NA",
#             "paid_amount_aed": 300.0,
#             "diagnosis_codes": ["E11.9"]
#         }
        
#         rules = {
#             "services_requiring_approval": ["SRV1001"],
#             "paid_threshold_aed": 250.0
#         }
        
#         result = tool._run(claim_data, rules)
        
#         self.assertIn("Static rules validation", result)
#         self.assertIn("SRV1001", result)


# if __name__ == "__main__":
#     unittest.main()
