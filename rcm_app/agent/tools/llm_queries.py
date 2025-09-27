"""
LLM query tool for nuanced error explanations
"""

from typing import Dict, Any
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from rcm_app.utils.llm import GeminiClient


class LLMQueryInput(BaseModel):
    """Input for LLM query"""
    claim_data: Dict[str, Any] = Field(description="Claim data to analyze")
    rules_text: str = Field(description="Rules text for context")
    query: str = Field(description="Specific query for the LLM")


class LLMQueryTool(BaseTool):
    """Tool for querying LLM for nuanced explanations"""
    
    name: str = "query_llm"
    description: str = "Query LLM for nuanced error explanations and recommendations"
    args_schema: type = LLMQueryInput
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Initialize LLM client as a private attribute
        self._llm_client = GeminiClient()
    
    def _run(self, claim_data: Dict[str, Any], rules_text: str, query: str) -> str:
        """Query LLM for analysis"""
        try:
            # Use enhanced analysis method
            result = self._llm_client.enhanced_analysis(claim_data, rules_text, query)
            
            if result:
                return f"LLM Analysis: {result.get('analysis', 'No analysis available')}"
            else:
                return "LLM query failed - using fallback analysis"
                
        except Exception as e:
            return f"LLM query error: {str(e)}"