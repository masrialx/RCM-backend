import os
import json
from typing import Any, Optional

try:
    import google.generativeai as genai
except Exception:  # noqa: BLE001
    genai = None


PROMPT_TEMPLATE = (
    "Analyze this claim: {claim}. Rules: {rules}. "
    "Identify errors, classify type, explain each in bullets why per rules, provide succinct corrective actions. "
    "Output JSON: {{'error_type': '', 'explanations': [], 'recommended_actions': [], 'confidence': 0.95}}."
)

ENHANCED_PROMPT_TEMPLATE = """
As an expert RCM validation agent, analyze this claim step-by-step:

Claim Data: {claim}
Rules Context: {rules}
Specific Query: {query}

Provide a detailed analysis with:
1. Error identification and classification
2. Step-by-step reasoning
3. Confidence score (0.0-1.0)
4. Specific recommendations

Output JSON format:
{{
    "analysis": "detailed step-by-step analysis",
    "error_type": "No error|Technical|Medical|Both",
    "explanations": ["bullet point explanations"],
    "recommended_actions": ["actionable recommendations"],
    "confidence": 0.95
}}
"""


class GeminiClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.enabled = bool(self.api_key)
        if self.enabled and genai:
            genai.configure(api_key=self.api_key)

    def evaluate_claim(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        if not self.enabled or not genai:
            return None
        try:
            prompt = PROMPT_TEMPLATE.format(
                claim=json.dumps(payload.get("claim"), ensure_ascii=False),
                rules=payload.get("rules_text", ""),
            )
            model = genai.GenerativeModel(self.model_name)
            resp = model.generate_content(prompt)
            text = resp.text or "{}"
            data = json.loads(text)
            if not isinstance(data, dict):
                return None
            # validate expected keys
            _ = data.get("error_type"), data.get("explanations"), data.get("recommended_actions")
            return data
        except Exception:  # noqa: BLE001
            return None
    
    def _generate_content(self, prompt: str) -> Optional[str]:
        """Generate content using Gemini with enhanced error handling"""
        if not self.enabled or not genai:
            return None
        try:
            model = genai.GenerativeModel(self.model_name)
            resp = model.generate_content(prompt)
            return resp.text
        except Exception as e:
            print(f"Gemini API error: {e}")
            return None
    
    def enhanced_analysis(self, claim_data: dict[str, Any], rules_text: str, query: str) -> dict[str, Any] | None:
        """Enhanced analysis with specific query support"""
        if not self.enabled or not genai:
            return None
        try:
            prompt = ENHANCED_PROMPT_TEMPLATE.format(
                claim=json.dumps(claim_data, ensure_ascii=False),
                rules=rules_text,
                query=query
            )
            
            response = self._generate_content(prompt)
            if not response:
                return None
            
            # Try to extract JSON from response
            if "{" in response and "}" in response:
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                json_str = response[json_start:json_end]
                
                try:
                    data = json.loads(json_str)
                    return data
                except json.JSONDecodeError:
                    pass
            
            # Fallback: return text response
            return {
                "analysis": response,
                "error_type": "Technical",
                "explanations": [response],
                "recommended_actions": ["Review manually"],
                "confidence": 0.5
            }
            
        except Exception as e:
            print(f"Enhanced analysis error: {e}")
            return None

