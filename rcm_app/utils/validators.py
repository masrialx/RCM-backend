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

        # Debug logging
        from flask import current_app
        current_app.logger.debug(f"Validating claim {claim.claim_id}: service={claim.service_code}, paid={claim.paid_amount_aed}, approval={claim.approval_number}")

        # Structural checks
        if self.uppercase_required:
            for fld in ["national_id", "member_id", "facility_id", "service_code"]:
                val = getattr(claim, fld)
                if val and val != val.upper():
                    errors.append(f"{fld} must be uppercase")
                    types.add("Technical")
                    current_app.logger.debug(f"  Uppercase error: {fld}={val}")

        for fld, pat in self.id_patterns.items():
            val = getattr(claim, fld, None)
            if val and not pat.fullmatch(val):
                errors.append(f"{fld} does not match required pattern")
                types.add("Technical")
                current_app.logger.debug(f"  Pattern error: {fld}={val}")

        # Static business rules
        if claim.service_code and claim.service_code in self.rules.services_requiring_approval:
            # Check if approval_number is missing or empty
            approval = claim.approval_number
            if not approval or (isinstance(approval, str) and approval.strip() == ""):
                errors.append("approval_number required for this service_code")
                types.add("Technical")
                current_app.logger.debug(f"  Approval error: service={claim.service_code}, approval={approval}")
            else:
                current_app.logger.debug(f"  Approval OK: service={claim.service_code}, approval={approval}")
        else:
            current_app.logger.debug(f"  Service {claim.service_code} does not require approval")

        if claim.diagnosis_codes:
            invalid = [d for d in claim.diagnosis_codes if d not in self.rules.diagnoses]
            if invalid:
                errors.append(f"invalid diagnosis codes: {', '.join(invalid)}")
                types.add("Medical")
                current_app.logger.debug(f"  Diagnosis error: {invalid}")

        try:
            paid = float(claim.paid_amount_aed) if claim.paid_amount_aed is not None else 0.0
        except Exception:
            paid = 0.0
        
        threshold = float(self.rules.paid_threshold_aed)
        if paid > threshold:
            errors.append("paid_amount_aed exceeds threshold")
            types.add("Technical")
            current_app.logger.debug(f"  Threshold error: paid={paid} > threshold={threshold}")
        else:
            current_app.logger.debug(f"  Threshold OK: paid={paid} <= threshold={threshold}")

        if not errors:
            current_app.logger.debug(f"  Claim {claim.claim_id} is VALID")
            return {
                "error_type": "No error",
                "explanations": [],
                "recommended_actions": []
            }

        etype = self._classify(types)
        actions.extend(self._default_actions(etype))
        current_app.logger.debug(f"  Claim {claim.claim_id} has errors: {errors}")
        return {
            "error_type": etype,
            "explanations": errors,
            "recommended_actions": actions,
        }

    def _classify(self, types: set[str]) -> str:
        if not types:
            return "No error"
        if types == {"Technical"}:
            return "Technical"
        if types == {"Medical"}:
            return "Medical"
        return "Both"

    def _default_actions(self, etype: str) -> list[str]:
        if etype == "No error":
            return ["accept claim"]
        if etype == "Technical":
            return ["request missing approvals", "correct identifiers", "recalculate payment"]
        if etype == "Medical":
            return ["review diagnosis coding", "escalate to clinical auditor"]
        return ["reject or escalate based on policy"]

