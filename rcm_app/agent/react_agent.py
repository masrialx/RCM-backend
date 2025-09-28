"""
ReAct AI Agent for RCM Validation
"""

import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from langchain.agents import AgentExecutor, create_react_agent
from langchain.tools import Tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from rcm_app.models.models import Master
from rcm_app.rules.loader import RulesBundle
from .tools.validation_tools import ValidationTools
from .tools.static_rules import StaticRulesTool
from .tools.llm_queries import LLMQueryTool
from .tools.database_queries import DatabaseQueryTool
from .tools.external_api import ExternalAPITool


@dataclass
class AgentResult:
    """Result from AI agent validation"""
    claim_id: str
    status: str  # "Validated" or "Not Validated"
    error_type: str  # "No error", "Technical", "Medical", "Both"
    error_explanation: List[str]
    recommended_action: List[str]
    confidence: float
    agent_reasoning: str


class RCMValidationAgent:
    """ReAct AI Agent for RCM claim validation"""
    
    def __init__(self, session, tenant_id: str, rules: RulesBundle):
        self.session = session
        self.tenant_id = tenant_id
        self.rules = rules
        self.validation_tools = ValidationTools(rules, session)
        
        # Initialize LLM
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            temperature=0.1,
            max_tokens=1000
        )
        
        # Create tools
        self.tools = self._create_tools()
        
        # Create agent
        self.agent = self._create_agent()
    
    def _create_tools(self) -> List[Tool]:
        """Create tools for the agent"""
        tools = []
        
        # Static rules tool
        static_rules_tool = StaticRulesTool()
        tools.append(Tool(
            name="static_rules",
            description="Apply static business rules for service codes, diagnosis codes, and paid amounts",
            func=lambda claim_data, rules: static_rules_tool._run(claim_data, rules)
        ))
        
        # LLM query tool
        llm_query_tool = LLMQueryTool()
        tools.append(Tool(
            name="llm_query",
            description="Query LLM for nuanced error explanations and recommendations",
            func=lambda claim_data, rules_text, query: llm_query_tool._run(claim_data, rules_text, query)
        ))
        
        # Database query tool
        db_query_tool = DatabaseQueryTool(self.session)
        tools.append(Tool(
            name="database_query",
            description="Query database for historical claim data and context",
            func=lambda claim_id, tenant_id, query_type: db_query_tool._run(claim_id, tenant_id, query_type)
        ))
        
        # External API tool
        external_api_tool = ExternalAPITool()
        tools.append(Tool(
            name="external_api",
            description="Make mock external API calls for verification",
            func=lambda approval_number, api_type: external_api_tool._run(approval_number, api_type)
        ))
        
        return tools
    
    def _create_agent(self) -> AgentExecutor:
        """Create the ReAct agent"""
        prompt = PromptTemplate.from_template("""
You are an expert RCM validation agent. Your task is to validate healthcare claims step-by-step using available tools.

Available tools:
{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Rules for validation:
1. Check ID formats (national_id, member_id, facility_id, unique_id) - must be uppercase alphanumeric
2. Validate unique_id format: first4(national_id)-middle4(member_id)-last4(facility_id) with hyphens
3. Check service codes requiring approval: SRV1001, SRV1002, SRV2008
4. Check diagnosis codes requiring approval: E11.9, R07.9, Z34.0
5. Check paid amount threshold: > AED 250 requires approval
6. Validate approval_number format: e.g., APP001 (invalid: NA, "Obtain approval")
7. Use database queries for historical context when uncertain
8. Use external API calls for approval verification
9. Use LLM queries for nuanced explanations when needed

For each claim, provide:
- status: "Validated" or "Not Validated"
- error_type: "No error", "Technical", "Medical", or "Both"
- error_explanation: list of specific error descriptions
- recommended_action: list of actionable recommendations
- confidence: float between 0.0 and 1.0

Question: {input}

{agent_scratchpad}
""")
        
        agent = create_react_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=prompt
        )
        
        return AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=True,
            max_iterations=10,
            handle_parsing_errors=True
        )
    
    def validate_claim(self, claim: Master) -> AgentResult:
        """Validate a single claim using the AI agent"""
        try:
            # Prepare claim data
            claim_data = self._claim_to_dict(claim)
            
            # Create input for agent
            agent_input = f"""
Validate this claim step-by-step:

Claim ID: {claim.claim_id}
Encounter Type: {claim.encounter_type}
Service Date: {claim.service_date}
National ID: {claim.national_id}
Member ID: {claim.member_id}
Facility ID: {claim.facility_id}
Unique ID: {claim.unique_id}
Diagnosis Codes: {claim.diagnosis_codes}
Service Code: {claim.service_code}
Paid Amount AED: {claim.paid_amount_aed}
Approval Number: {claim.approval_number}

Rules Context:
{self.rules.raw_rules_text}

Please validate this claim using the available tools and provide a comprehensive analysis.
"""
            
            # Run agent
            result = self.agent.invoke({"input": agent_input})
            
            # Parse result
            return self._parse_agent_result(claim.claim_id, result)
            
        except Exception as e:
            # Fallback to basic validation
            return self._fallback_validation(claim, str(e))
    
    def _claim_to_dict(self, claim: Master) -> Dict[str, Any]:
        """Convert claim model to dictionary"""
        return {
            "claim_id": claim.claim_id,
            "encounter_type": claim.encounter_type,
            "service_date": claim.service_date.isoformat() if claim.service_date else None,
            "national_id": claim.national_id,
            "member_id": claim.member_id,
            "facility_id": claim.facility_id,
            "unique_id": claim.unique_id,
            "diagnosis_codes": claim.diagnosis_codes,
            "service_code": claim.service_code,
            "paid_amount_aed": float(claim.paid_amount_aed) if claim.paid_amount_aed else None,
            "approval_number": claim.approval_number,
            "tenant_id": claim.tenant_id
        }
    
    def _parse_agent_result(self, claim_id: str, result: Dict[str, Any]) -> AgentResult:
        """Parse agent result into structured format"""
        try:
            # Extract final answer
            final_answer = result.get("output", "")
            
            # Try to parse JSON from final answer
            if "{" in final_answer and "}" in final_answer:
                json_start = final_answer.find("{")
                json_end = final_answer.rfind("}") + 1
                json_str = final_answer[json_start:json_end]
                
                try:
                    parsed = json.loads(json_str)
                    return AgentResult(
                        claim_id=claim_id,
                        status=parsed.get("status", "Not Validated"),
                        error_type=parsed.get("error_type", "Technical"),
                        error_explanation=parsed.get("error_explanation", []),
                        recommended_action=parsed.get("recommended_action", []),
                        confidence=parsed.get("confidence", 0.5),
                        agent_reasoning=final_answer
                    )
                except json.JSONDecodeError:
                    pass
            
            # Fallback parsing
            return self._parse_text_result(claim_id, final_answer)
            
        except Exception as e:
            return AgentResult(
                claim_id=claim_id,
                status="Not Validated",
                error_type="Technical",
                error_explanation=[f"Agent parsing error: {str(e)}"],
                recommended_action=["Review claim manually"],
                confidence=0.0,
                agent_reasoning=str(e)
            )
    
    def _parse_text_result(self, claim_id: str, text: str) -> AgentResult:
        """Parse text result when JSON parsing fails"""
        # Simple text parsing logic
        status = "Not Validated" if any(word in text.lower() for word in ["error", "invalid", "failed"]) else "Validated"
        error_type = "Technical"  # Default
        
        if "medical" in text.lower():
            error_type = "Medical"
        elif "both" in text.lower() or ("technical" in text.lower() and "medical" in text.lower()):
            error_type = "Both"
        elif status == "Validated":
            error_type = "No error"
        
        return AgentResult(
            claim_id=claim_id,
            status=status,
            error_type=error_type,
            error_explanation=[text],
            recommended_action=["Review agent reasoning"],
            confidence=0.7,
            agent_reasoning=text
        )
    
    def _fallback_validation(self, claim: Master, error: str) -> AgentResult:
        """Fallback validation when agent fails"""
        try:
            # Use validation tools directly
            result = self.validation_tools.validate_claim_comprehensive(claim)
            
            return AgentResult(
                claim_id=claim.claim_id,
                status="Validated" if result.is_valid else "Not Validated",
                error_type=result.error_type,
                error_explanation=result.explanations,
                recommended_action=result.recommended_actions,
                confidence=result.confidence,
                agent_reasoning=f"Fallback validation due to agent error: {error}"
            )
        except Exception as e:
            return AgentResult(
                claim_id=claim.claim_id,
                status="Not Validated",
                error_type="Technical",
                error_explanation=[f"Validation failed: {str(e)}"],
                recommended_action=["Manual review required"],
                confidence=0.0,
                agent_reasoning=f"Complete validation failure: {str(e)}"
            )
    
    def validate_claims_batch(self, claims: List[Master]) -> List[AgentResult]:
        """Validate multiple claims in batch"""
        results = []
        for claim in claims:
            result = self.validate_claim(claim)
            results.append(result)
        return results