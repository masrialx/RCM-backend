import os
import json
from typing import Any, Optional

# Prefer the new official google-genai client: `from google import genai`
GENAI_MODE = None  # 'client' | 'generativeai' | None
genai_client_lib = None
genai_legacy_lib = None

try:
    # New client style: from google import genai
    from google import genai as genai_client_lib  # type: ignore
    GENAI_MODE = "client"
except Exception:  # noqa: BLE001
    try:
        # Legacy library: google.generativeai
        import google.generativeai as genai_legacy_lib  # type: ignore
        GENAI_MODE = "generativeai"
    except Exception:  # noqa: BLE001
        GENAI_MODE = None


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
        # Prefer environment key; fallback to provided hardcoded key if missing
        self.api_key = os.getenv("GOOGLE_API_KEY") 
        # Default to the latest flash per user's sample; allow override via env
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.enabled = bool(self.api_key) and GENAI_MODE is not None

        self._client = None
        if not self.enabled:
            return

        try:
            if GENAI_MODE == "client":
                # New official client
                self._client = genai_client_lib.Client(api_key=self.api_key)
            elif GENAI_MODE == "generativeai":
                # Legacy client configuration
                genai_legacy_lib.configure(api_key=self.api_key)
            else:
                pass
        except Exception:  # noqa: BLE001
            self._client = None
            self.enabled = False

    def evaluate_claim(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        try:
            prompt = PROMPT_TEMPLATE.format(
                claim=json.dumps(payload.get("claim"), ensure_ascii=False),
                rules=payload.get("rules_text", ""),
            )
            text = self._generate_text(prompt)
            if not text:
                return None
            data = json.loads(text)
            if not isinstance(data, dict):
                return None
            # validate expected keys
            _ = data.get("error_type"), data.get("explanations"), data.get("recommended_actions")
            return data
        except Exception:  # noqa: BLE001
            return None
    
    def _generate_text(self, prompt: str) -> Optional[str]:
        """Generate text using the preferred Google GenAI client."""
        if not self.enabled:
            return None
        try:
            if GENAI_MODE == "client" and self._client is not None:
                # New client usage
                resp = self._client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                )
                return getattr(resp, "text", None)
            elif GENAI_MODE == "generativeai":
                # Legacy client usage
                model = genai_legacy_lib.GenerativeModel(self.model_name)
                resp = model.generate_content(prompt)
                return getattr(resp, "text", None)
            return None
        except Exception as e:
            print(f"Gemini API error: {e}")
            return None
    
    def enhanced_analysis(self, claim_data: dict[str, Any], rules_text: str, query: str) -> dict[str, Any] | None:
        """Enhanced analysis with specific query support"""
        if not self.enabled:
            return None
        try:
            prompt = ENHANCED_PROMPT_TEMPLATE.format(
                claim=json.dumps(claim_data, ensure_ascii=False),
                rules=rules_text,
                query=query
            )
            
            response = self._generate_text(prompt)
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

