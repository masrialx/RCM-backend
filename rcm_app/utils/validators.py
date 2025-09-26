import re
from typing import Any
from ..models.models import Master
from ..rules.loader import RulesBundle


class Validator:
    def __init__(self, rules: RulesBundle) -> None:
        self.rules = rules
        self.id_patterns = {
            k: re.compile(v) for k, v in (rules.id_rules.get("patterns", {}) or {}).items()
        }
        self.uppercase_required = bool(rules.id_rules.get("uppercase_required", True))

    def run_all(self, claim: Master) -> dict[str, Any] | None:
        errors: list[str] = []
        actions: list[str] = []
        types: set[str] = set()

        # Structural checks
        if self.uppercase_required:
            for fld in ["national_id", "member_id", "facility_id", "service_code"]:
                val = getattr(claim, fld)
                if val and val != val.upper():
                    errors.append(f"{fld} must be uppercase")
                    types.add("Technical")

        for fld, pat in self.id_patterns.items():
            val = getattr(claim, fld, None)
            if val and not pat.fullmatch(val):
                errors.append(f"{fld} does not match required pattern")
                types.add("Technical")

        # Static business rules
        if claim.service_code and claim.service_code in self.rules.services_requiring_approval and not claim.approval_number:
            errors.append("approval_number required for this service_code")
            types.add("Technical")

        if claim.diagnosis_codes:
            invalid = [d for d in claim.diagnosis_codes if d not in self.rules.diagnoses]
            if invalid:
                errors.append(f"invalid diagnosis codes: {', '.join(invalid)}")
                types.add("Medical")

        try:
            paid = float(claim.paid_amount_aed) if claim.paid_amount_aed is not None else 0.0
        except Exception:
            paid = 0.0
        if paid > float(self.rules.paid_threshold_aed):
            errors.append("paid_amount_aed exceeds threshold")
            types.add("Technical")

        if not errors:
            return None

        etype = self._classify(types)
        actions.extend(self._default_actions(etype))
        return {
            "error_type": etype,
            "explanations": errors,
            "recommended_actions": actions,
        }

    @staticmethod
    def _classify(types: set[str]) -> str:
        if not types:
            return "None"
        if types == {"Technical"}:
            return "Technical"
        if types == {"Medical"}:
            return "Medical"
        return "Both"

    @staticmethod
    def _default_actions(etype: str) -> list[str]:
        if etype == "None":
            return ["accept claim"]
        if etype == "Technical":
            return ["request missing approvals", "correct identifiers", "recalculate payment"]
        if etype == "Medical":
            return ["review diagnosis coding", "escalate to clinical auditor"]
        return ["reject or escalate based on policy"]

