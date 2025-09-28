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
        # Optional config-driven maps for encounter/service and service-diagnosis constraints
        self.inpatient_only_services = set(rules.id_rules.get("inpatient_only_services", []) or [])
        self.outpatient_only_services = set(rules.id_rules.get("outpatient_only_services", []) or [])
        # Map of service_code -> set of allowed/required diagnosis codes (exact or prefix match)
        self.service_diagnosis_map: dict[str, set[str]] = {
            k: set(v) for k, v in (rules.id_rules.get("service_diagnosis_map", {}) or {}).items()
        }
        # Mutually exclusive diagnosis pairs or groups
        self.mutually_exclusive_diagnoses: list[set[str]] = [
            set(group) for group in (rules.id_rules.get("mutually_exclusive_diagnoses", []) or [])
        ]
        # Provide default mutually exclusive rule per requirements if none specified
        if not self.mutually_exclusive_diagnoses:
            self.mutually_exclusive_diagnoses = [
                {"R73.03", "E11.9"}
            ]
        # Facility registry and allowed mappings
        self.facility_registry: dict[str, str] = rules.facility_registry or {}
        self.service_allowed_facility_types: dict[str, set[str]] = {
            k: set(v) for k, v in (rules.service_allowed_facility_types or {}).items()
        }

    def run_all(self, claim: Master) -> dict[str, Any] | None:
        errors: list[str] = []
        actions: list[str] = []
        types: set[str] = set()
        corrections: dict[str, Any] = {}

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
        
        # Unique ID validation and normalization
        expected_unique: str | None = None
        if claim.national_id and claim.member_id and claim.facility_id:
            mid_start = max((len(claim.member_id) - 4) // 2, 0)
            expected_mid = claim.member_id[mid_start:mid_start + 4]
            expected_unique = f"{(claim.national_id or '')[:4]}-{expected_mid}-{(claim.facility_id or '')[-4:]}".upper()

        if claim.unique_id:
            if claim.unique_id != claim.unique_id.upper():
                errors.append(f"unique_id '{claim.unique_id}' must be uppercase alphanumeric with hyphens")
                types.add("Technical")
                current_app.logger.debug(f"  Unique ID case error: {claim.unique_id}")
            if expected_unique and claim.unique_id.upper() != expected_unique.upper():
                errors.append(f"unique_id format incorrect. Expected: {expected_unique}")
                types.add("Technical")
                current_app.logger.debug(f"  Unique ID format error: got={claim.unique_id}, expected={expected_unique}")
            if not re.fullmatch(r"^[A-Z0-9]+-[A-Z0-9]+-[A-Z0-9]+$", claim.unique_id or ""):
                errors.append("unique_id must be uppercase alphanumeric with hyphen-separated segments")
                types.add("Technical")
        # If unique_id missing or invalid and we can compute expected, auto-correct
        if expected_unique and (not claim.unique_id or not re.fullmatch(r"^[A-Z0-9]+-[A-Z0-9]+-[A-Z0-9]+$", (claim.unique_id or "").upper()) or (claim.unique_id or "").upper() != expected_unique.upper()):
            corrections["unique_id"] = expected_unique
            actions.append("Normalize unique_id to required uppercase hyphenated format")
            current_app.logger.debug(f"  Auto-correct unique_id => {expected_unique}")

        for fld, pat in self.id_patterns.items():
            val = getattr(claim, fld, None)
            if val and not pat.fullmatch(val):
                errors.append(f"{fld} does not match required pattern")
                types.add("Technical")
                current_app.logger.debug(f"  Pattern error: {fld}={val}")

        # Static business rules
        if claim.service_code and claim.service_code in self.rules.services_requiring_approval:
            approval = claim.approval_number
            if not self._is_valid_approval(approval):
                errors.append("Service requires valid approval_number (e.g., APPROVED, APP###)")
                actions.append("Obtain prior approval for this service code")
                types.add("Technical")
                # Auto-generate approval when required
                gen = self._generate_approval_number(seed=f"{claim.claim_id}:{claim.service_code}")
                corrections["approval_number"] = gen
                current_app.logger.debug(f"  Approval error: service={claim.service_code}, approval={approval}; auto-generate => {gen}")
            else:
                current_app.logger.debug(f"  Approval OK: service={claim.service_code}, approval={approval}")
        else:
            current_app.logger.debug(f"  Service {claim.service_code} does not require approval")

        try:
            paid = float(claim.paid_amount_aed) if claim.paid_amount_aed is not None else 0.0
        except Exception:
            paid = 0.0

        # Get threshold early
        threshold = float(self.rules.paid_threshold_aed)

        if claim.diagnosis_codes:
            invalid = [d for d in claim.diagnosis_codes if d not in self.rules.diagnoses]
            if invalid:
                errors.append(f"invalid diagnosis codes: {', '.join(invalid)}")
                types.add("Medical")
                current_app.logger.debug(f"  Diagnosis error: {invalid}")
            # Mutually exclusive diagnosis rules
            for group in self.mutually_exclusive_diagnoses:
                overlap = group.intersection(set(claim.diagnosis_codes))
                if len(overlap) > 1:
                    errors.append(f"mutually exclusive diagnoses present together: {', '.join(sorted(overlap))}")
                    types.add("Medical")
                    current_app.logger.debug(f"  Mutually exclusive diagnoses: {overlap}")
            
            # Diagnosis codes that require prior approval regardless of amount
            for diagnosis in claim.diagnosis_codes:
                if diagnosis in self.rules.diagnoses_requiring_approval:
                    if not self._is_valid_approval(claim.approval_number):
                        errors.append(f"Diagnosis {diagnosis} requires prior approval; invalid approval_number")
                        actions.append("Obtain prior approval for diagnosis-driven services")
                        types.add("Medical")
                        # Auto-generate approval as per requirement
                        gen = self._generate_approval_number(seed=f"{claim.claim_id}:{diagnosis}")
                        corrections.setdefault("approval_number", gen)
                        current_app.logger.debug(f"  Diagnosis approval error: {diagnosis}; auto-generate => {gen}")
            
            # Service-diagnosis compatibility checks (if configured)
            if claim.service_code and self.service_diagnosis_map.get(claim.service_code):
                required_set = self.service_diagnosis_map[claim.service_code]
                provided_set = set(claim.diagnosis_codes)
                # Match either exact code or prefix (e.g., E11 matches E11.9)
                def matches(code: str) -> bool:
                    return code in provided_set or any(d.startswith(code) for d in provided_set)
                if not any(matches(req) for req in required_set):
                    errors.append(f"service_code {claim.service_code} requires specific diagnoses: {', '.join(sorted(required_set))}")
                    actions.append("Add the required diagnosis or change service code")
                    types.add("Medical")
                    current_app.logger.debug(f"  Service-diagnosis mismatch: service={claim.service_code}, required={required_set}, provided={provided_set}")
        
        # Check paid amount threshold
        if paid > threshold:
            approval = claim.approval_number
            if not self._is_valid_approval(approval):
                errors.append(f"Paid amount {paid} > AED {threshold} requires valid approval_number")
                actions.append("Obtain approval for paid amount above threshold")
                types.add("Technical")
                # Auto-generate approval per requirement
                gen = self._generate_approval_number(seed=f"{claim.claim_id}:PAID:{paid}")
                corrections.setdefault("approval_number", gen)
                current_app.logger.debug(f"  Threshold error: paid={paid} > threshold={threshold}, approval={approval}; auto-generate => {gen}")
            else:
                current_app.logger.debug(f"  Threshold OK: paid={paid} > threshold={threshold}, but has valid approval={approval}")
        else:
            current_app.logger.debug(f"  Threshold OK: paid={paid} <= threshold={threshold}")

        # Encounter type validation (if provided)
        if claim.service_code:
            et = (claim.encounter_type or "").strip().upper() if claim.encounter_type else ""
            if claim.service_code in self.inpatient_only_services and et != "INPATIENT":
                errors.append(f"Service {claim.service_code} is INPATIENT-only but claim has {claim.encounter_type}")
                actions.append("Change encounter type to INPATIENT or correct service code")
                types.add("Technical")
                corrections["encounter_type"] = "INPATIENT"
            if claim.service_code in self.outpatient_only_services and et != "OUTPATIENT":
                errors.append(f"Service {claim.service_code} is OUTPATIENT-only but claim has {claim.encounter_type}")
                actions.append("Change encounter type to OUTPATIENT or correct service code")
                types.add("Technical")
                corrections["encounter_type"] = "OUTPATIENT"

        # Facility type eligibility checks (if configured)
        if claim.facility_id and claim.service_code:
            fac_type = self.facility_registry.get(claim.facility_id)
            allowed = self.service_allowed_facility_types.get(claim.service_code)
            if fac_type and allowed and fac_type not in allowed:
                errors.append(f"Service {claim.service_code} not allowed for facility type {fac_type}")
                actions.append("Route to an allowed facility type or adjust service code")
                types.add("Medical")

        # Deduplicate and clean actions
        if actions:
            dedup_actions = list(dict.fromkeys(a.strip() for a in actions if a and a.strip()))
        else:
            dedup_actions = []

        # If we applied corrections, add explanatory notes
        explanations_with_corrections = list(errors)
        if "approval_number" in corrections:
            explanations_with_corrections.append(f"Generated approval_number '{corrections['approval_number']}' due to rule requirements")
        if "unique_id" in corrections:
            explanations_with_corrections.append("Normalized unique_id to uppercase hyphenated format")
        if "encounter_type" in corrections:
            explanations_with_corrections.append(f"Corrected encounter_type to {corrections['encounter_type']}")

        if not explanations_with_corrections:
            current_app.logger.debug(f"  Claim {claim.claim_id} is VALID")
            return {
                "error_type": "No error",
                "explanations": [],
                "recommended_actions": [],
                "corrections": corrections,
            }

        etype = self._classify(types)
        dedup_actions.extend(self._default_actions(etype))
        current_app.logger.debug(f"  Claim {claim.claim_id} has errors: {errors}")
        return {
            "error_type": etype,
            "explanations": explanations_with_corrections,
            "recommended_actions": list(dict.fromkeys(dedup_actions)),
            "corrections": corrections,
        }

    def _is_valid_approval(self, approval: Any) -> bool:
        if not approval:
            return False
        if not isinstance(approval, str):
            return False
        appr = approval.strip().upper()
        if appr in {"NA", "NAN", "OBTAIN APPROVAL", ""}:
            return False
        # Accept explicit APPROVED text or common codes like APP001, APR123
        if appr == "APPROVED":
            return True
        if re.fullmatch(r"^APP\d{3,}$", appr):
            return True
        return False

    def _generate_approval_number(self, seed: str) -> str:
        """Generate a deterministic valid approval number 'APP###' based on a seed"""
        try:
            import hashlib
            h = hashlib.md5(seed.encode("utf-8")).hexdigest()
            n = int(h[:6], 16) % 900 + 100  # 100-999
            return f"APP{n}"
        except Exception:
            return "APPROVED"

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
        # Both: combine key actions from technical and medical plus final disposition
        return [
            "request missing approvals",
            "correct identifiers",
            "review diagnosis coding",
            "recalculate payment",
            "reject or escalate based on policy"
        ]

