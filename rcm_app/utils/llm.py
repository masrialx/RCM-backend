import os
import json
from typing import Any

try:
    import google.generativeai as genai
except Exception:  # noqa: BLE001
    genai = None


PROMPT_TEMPLATE = (
    "Analyze this claim: {claim}. Rules: {rules}. "
    "Identify errors, classify type, explain each in bullets why per rules, provide succinct corrective actions. "
    "Output JSON: {'error_type': '', 'explanations': [], 'recommended_actions': []}."
)


class GeminiClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
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

