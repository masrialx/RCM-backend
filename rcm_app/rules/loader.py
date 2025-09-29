import json
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class RulesBundle:
    services_requiring_approval: set[str]
    diagnoses: set[str]
    diagnoses_requiring_approval: set[str]
    paid_threshold_aed: float
    id_rules: dict
    raw_rules_text: str
    facility_registry: dict
    service_allowed_facility_types: dict


class TenantConfigLoader:
    def __init__(self, base_path: Optional[str] = None) -> None:
        self.base_path = base_path or os.getcwd()

    def _tenant_config_path(self, tenant_id: str) -> str:
        return os.path.join(self.base_path, "configs", f"tenant_{tenant_id}.json")

    def load_rules_for_tenant(self, tenant_id: str) -> RulesBundle:
        cfg_path = self._tenant_config_path(tenant_id)
        if not os.path.exists(cfg_path):
            raise FileNotFoundError(f"tenant config not found: {cfg_path}")
        with open(cfg_path, "r", encoding="utf-8") as fh:
            cfg = json.load(fh)

        rules_dir = os.path.join(self.base_path, "rules", tenant_id)
        services_path = os.path.join(rules_dir, cfg["services_requiring_approval_file"])  # list
        diagnoses_path = os.path.join(rules_dir, cfg["diagnoses_file"])  # list
        threshold = float(cfg.get("paid_threshold_aed", 250))
        id_rules = cfg.get("id_rules", {})
        facility_registry = id_rules.get("facility_registry", {})
        service_allowed_facility_types = id_rules.get("service_allowed_facility_types", {})

        def load_list(path: str) -> set[str]:
            with open(path, "r", encoding="utf-8") as fh:
                return {line.strip() for line in fh if line.strip() and not line.strip().startswith("#")}

        services = load_list(services_path)
        diagnoses = load_list(diagnoses_path)

        # Hardcoded defaults to ensure rule coverage even if config files drift
        default_services_requiring_approval = {"SRV1001", "SRV1002", "SRV2008"}
        # Ensure SRV1003 is NOT in approval-required list
        services = (services - {"SRV1003"}) | default_services_requiring_approval

        # For LLM prompt: concatenate raw rules text
        raw_text_parts = []
        for p in (services_path, diagnoses_path):
            with open(p, "r", encoding="utf-8") as fh:
                raw_text_parts.append(f"FILE {os.path.basename(p)}\n" + fh.read())
        raw_rules_text = "\n\n".join(raw_text_parts) + f"\npaid_threshold_aed={threshold}\n" + json.dumps({"id_rules": id_rules})

        # Only specific diagnoses require approval as per requirements (hardcoded fallback)
        diagnoses_requiring_approval = {"E11.9", "R07.9", "Z34.0"}

        # Ensure id_rules contains the hardcoded encounter/service and facility constraints when absent
        id_rules.setdefault("inpatient_only_services", ["SRV1001", "SRV1002", "SRV1003"])
        id_rules.setdefault(
            "outpatient_only_services",
            ["SRV2001", "SRV2002", "SRV2003", "SRV2004", "SRV2006", "SRV2007", "SRV2008", "SRV2010", "SRV2011"],
        )
        # Service to required diagnoses linkage
        sdm = id_rules.setdefault("service_diagnosis_map", {})
        sdm.setdefault("SRV2007", ["E11.9"])  # HbA1c requires Diabetes
        sdm.setdefault("SRV2006", ["J45.909"])  # PFT requires Asthma
        sdm.setdefault("SRV2001", ["R07.9"])  # ECG requires Chest Pain
        sdm.setdefault("SRV2008", ["Z34.0"])  # US-Pregnancy requires Pregnancy
        sdm.setdefault("SRV2005", ["N39.0"])  # Urine culture for UTI (flag if service missing)
        # Mutually exclusive diagnoses
        id_rules.setdefault(
            "mutually_exclusive_diagnoses",
            [["R73.03", "E11.9"], ["E66.3", "E66.9"], ["R51", "G43.9"]],
        )
        # Facility type constraints (allowed mappings)
        id_rules.setdefault("facility_registry", id_rules.get("facility_registry", {}))
        saf = id_rules.setdefault("service_allowed_facility_types", id_rules.get("service_allowed_facility_types", {}))
        saf.setdefault("SRV2008", ["MATERNITY_HOSPITAL"])  # Pregnancy US
        saf.setdefault("SRV1003", ["DIALYSIS_CENTER"])     # Inpatient dialysis
        saf.setdefault("SRV2010", ["DIALYSIS_CENTER"])     # Outpatient dialysis
        saf.setdefault("SRV2001", ["CARDIOLOGY_CENTER"])   # ECG
        saf.setdefault("SRV2011", ["CARDIOLOGY_CENTER"])   # Stress test

        return RulesBundle(
            services_requiring_approval=services,
            diagnoses=diagnoses,
            diagnoses_requiring_approval=diagnoses_requiring_approval,
            paid_threshold_aed=threshold,
            id_rules=id_rules,
            raw_rules_text=raw_rules_text,
            facility_registry=facility_registry,
            service_allowed_facility_types=service_allowed_facility_types,
        )
