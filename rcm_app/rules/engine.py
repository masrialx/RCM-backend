from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any, Callable, Tuple

from ..models.models import Master
from .loader import RulesBundle


@dataclass
class RuleIssue:
    category: str  # "Technical" | "Medical"
    message: str
    action: str


class BaseRule:
    category: str = "Technical"
    name: str = "base_rule"

    def apply(self, claim: Master, rules: RulesBundle) -> List[RuleIssue]:
        raise NotImplementedError


# ---------------------- Technical Rules ----------------------

class UppercaseIdRule(BaseRule):
    category = "Technical"
    name = "uppercase_ids"

    def apply(self, claim: Master, rules: RulesBundle) -> List[RuleIssue]:
        issues: List[RuleIssue] = []
        if rules.id_rules.get("uppercase_required", True):
            for field in ["national_id", "member_id", "facility_id", "service_code"]:
                val = getattr(claim, field)
                if val and val != val.upper():
                    issues.append(RuleIssue(
                        category=self.category,
                        message=f"{field} must be uppercase",
                        action=f"Convert {field} to uppercase"
                    ))
        return issues


class UniqueIdFormatRule(BaseRule):
    category = "Technical"
    name = "unique_id_format"

    def apply(self, claim: Master, rules: RulesBundle) -> List[RuleIssue]:
        issues: List[RuleIssue] = []
        uid = (claim.unique_id or "").strip().upper()
        if not uid:
            return issues
        import re
        if not re.fullmatch(r"^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$", uid):
            issues.append(RuleIssue(
                category=self.category,
                message="unique_id is invalid: must be uppercase alphanumeric with hyphen-separated format (XXXX-XXXX-XXXX)",
                action="Format unique_id as first4(national_id)-middle4(member_id)-last4(facility_id)",
            ))
            return issues

        ni = (claim.national_id or "").strip().upper()
        mi = (claim.member_id or "").strip().upper()
        fi = (claim.facility_id or "").strip().upper()
        if ni and mi and fi:
            expected = f"{ni[:4].ljust(4,'X')}-{mi[:4].ljust(4,'X')}-{fi[-4:].rjust(4,'X')}"
            if uid != expected:
                issues.append(RuleIssue(
                    category=self.category,
                    message=f"unique_id format is invalid (should be {expected}).",
                    action="Format unique_id as first4(national_id)-middle4(member_id)-last4(facility_id)",
                ))
        return issues


class ServiceApprovalRule(BaseRule):
    category = "Technical"
    name = "service_requires_approval"

    def apply(self, claim: Master, rules: RulesBundle) -> List[RuleIssue]:
        issues: List[RuleIssue] = []
        if claim.service_code and claim.service_code in rules.services_requiring_approval:
            appr = (claim.approval_number or "").strip().upper()
            if appr in {"", "NA", "OBTAIN APPROVAL"}:
                issues.append(RuleIssue(
                    category=self.category,
                    message=f"Service code {claim.service_code} requires approval",
                    action=f"Obtain prior approval for service code {claim.service_code}",
                ))
        return issues


class DiagnosisApprovalRule(BaseRule):
    category = "Technical"  # mixed, but classify as Technical for prior-auth admin
    name = "diagnosis_requires_approval"

    def apply(self, claim: Master, rules: RulesBundle) -> List[RuleIssue]:
        issues: List[RuleIssue] = []
        if not claim.diagnosis_codes:
            return issues
        appr = (claim.approval_number or "").strip().upper()
        for dx in claim.diagnosis_codes:
            if dx in rules.diagnoses_requiring_approval:
                if appr in {"", "NA", "OBTAIN APPROVAL"}:
                    issues.append(RuleIssue(
                        category="Medical",
                        message=f"Diagnosis {dx} requires prior approval",
                        action="Obtain prior approval for diagnosis-driven care",
                    ))
        return issues


class PaidThresholdApprovalRule(BaseRule):
    category = "Technical"
    name = "paid_threshold_requires_approval"

    def apply(self, claim: Master, rules: RulesBundle) -> List[RuleIssue]:
        issues: List[RuleIssue] = []
        try:
            paid = float(claim.paid_amount_aed) if claim.paid_amount_aed is not None else 0.0
        except Exception:
            paid = 0.0
        threshold = float(rules.paid_threshold_aed)
        if paid > threshold:
            appr = (claim.approval_number or "").strip().upper()
            if appr in {"", "NA", "OBTAIN APPROVAL"}:
                issues.append(RuleIssue(
                    category=self.category,
                    message=f"Paid amount {paid} exceeds threshold {threshold}",
                    action="Obtain approval for amount exceeding threshold",
                ))
        return issues


# ---------------------- Medical Rules ----------------------

class EncounterTypeRule(BaseRule):
    category = "Medical"
    name = "encounter_type_consistency"

    def apply(self, claim: Master, rules: RulesBundle) -> List[RuleIssue]:
        issues: List[RuleIssue] = []
        svc = claim.service_code or ""
        et = (claim.encounter_type or "").strip().upper()
        if svc:
            if svc in set(rules.id_rules.get("inpatient_only_services", []) or []) and et != "INPATIENT":
                issues.append(RuleIssue(
                    category=self.category,
                    message=f"Service {svc} is INPATIENT-only but encounter is {claim.encounter_type}",
                    action="Change encounter type to INPATIENT or correct service code",
                ))
            if svc in set(rules.id_rules.get("outpatient_only_services", []) or []) and et != "OUTPATIENT":
                issues.append(RuleIssue(
                    category=self.category,
                    message=f"Service {svc} is OUTPATIENT-only but encounter is {claim.encounter_type}",
                    action="Change encounter type to OUTPATIENT or correct service code",
                ))
        return issues


class FacilityTypeRule(BaseRule):
    category = "Medical"
    name = "facility_type_constraint"

    def apply(self, claim: Master, rules: RulesBundle) -> List[RuleIssue]:
        issues: List[RuleIssue] = []
        if not (claim.facility_id and claim.service_code):
            return issues
        fac_type = (rules.facility_registry or {}).get((claim.facility_id or "").strip().upper())
        allowed = (rules.service_allowed_facility_types or {}).get(claim.service_code)
        # GENERAL_HOSPITAL allows all services per specification
        if fac_type == "GENERAL_HOSPITAL":
            return issues
        if fac_type and allowed and fac_type not in set(allowed):
            issues.append(RuleIssue(
                category=self.category,
                message=f"Service {claim.service_code} not allowed for facility type {fac_type}",
                action="Route to an allowed facility type or adjust service",
            ))
        return issues


class ServiceDiagnosisDependencyRule(BaseRule):
    category = "Medical"
    name = "service_diagnosis_dependencies"

    def apply(self, claim: Master, rules: RulesBundle) -> List[RuleIssue]:
        issues: List[RuleIssue] = []
        svc = claim.service_code or ""
        provided = set((claim.diagnosis_codes or []))
        mapping: Dict[str, List[str]] = rules.id_rules.get("service_diagnosis_map", {}) or {}

        # Diagnostic requirements
        req = set(mapping.get(svc, []))
        if req:
            def matches(code: str) -> bool:
                return code in provided or any(d.startswith(code) for d in provided)
            if not any(matches(code) for code in req):
                issues.append(RuleIssue(
                    category=self.category,
                    message=f"service_code {svc} requires diagnoses: {', '.join(sorted(req))}",
                    action="Add required diagnosis or adjust service",
                ))

        # Special case: N39.0 requires SRV2005 (not in allowed list -> always flag)
        if "N39.0" in provided and svc != "SRV2005":
            issues.append(RuleIssue(
                category=self.category,
                message="Diagnosis N39.0 (UTI) requires SRV2005 Urine Culture",
                action="Order SRV2005 Urine Culture or update coding",
            ))
        return issues


class MutuallyExclusiveDiagnosesRule(BaseRule):
    category = "Medical"
    name = "mutually_exclusive_diagnoses"

    def apply(self, claim: Master, rules: RulesBundle) -> List[RuleIssue]:
        issues: List[RuleIssue] = []
        provided = set((claim.diagnosis_codes or []))
        for group in (rules.id_rules.get("mutually_exclusive_diagnoses", []) or []):
            gset = set(group)
            overlap = provided.intersection(gset)
            if len(overlap) > 1:
                issues.append(RuleIssue(
                    category=self.category,
                    message=f"mutually exclusive diagnoses present: {', '.join(sorted(overlap))}",
                    action="Review diagnosis coding; pick the most specific condition",
                ))
        return issues


class ModularRuleEngine:
    """Deterministic modular rule engine applying technical then medical rules."""

    def __init__(self, rules: RulesBundle) -> None:
        self.rules = rules
        # Deterministic order per requirements
        self.technical_rules: List[BaseRule] = [
            UppercaseIdRule(),
            UniqueIdFormatRule(),
            ServiceApprovalRule(),
            DiagnosisApprovalRule(),
            PaidThresholdApprovalRule(),
        ]
        self.medical_rules: List[BaseRule] = [
            EncounterTypeRule(),
            FacilityTypeRule(),
            ServiceDiagnosisDependencyRule(),
            MutuallyExclusiveDiagnosesRule(),
        ]

    def adjudicate(self, claim: Master) -> Dict[str, Any]:
        issues: List[RuleIssue] = []
        for rule in self.technical_rules:
            issues.extend(rule.apply(claim, self.rules))
        for rule in self.medical_rules:
            issues.extend(rule.apply(claim, self.rules))

        if not issues:
            return {
                "status": "Validated",
                "error_type": "No error",
                "explanations": [],
                "recommended_actions": [],
            }

        # classify
        cats = {i.category for i in issues}
        if cats == {"Technical"}:
            etype = "Technical"
        elif cats == {"Medical"}:
            etype = "Medical"
        else:
            etype = "Both"

        return {
            "status": "Not Validated",
            "error_type": etype,
            "explanations": [i.message for i in issues],
            "recommended_actions": [i.action for i in issues],
        }

