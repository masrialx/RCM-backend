import json
import os
from dataclasses import dataclass


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
    def __init__(self, base_path: str | None = None) -> None:
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

        # For LLM prompt: concatenate raw rules text
        raw_text_parts = []
        for p in (services_path, diagnoses_path):
            with open(p, "r", encoding="utf-8") as fh:
                raw_text_parts.append(f"FILE {os.path.basename(p)}\n" + fh.read())
        raw_rules_text = "\n\n".join(raw_text_parts) + f"\npaid_threshold_aed={threshold}\n" + json.dumps({"id_rules": id_rules})

        # Only specific diagnoses require approval as per requirements
        diagnoses_requiring_approval = {"E11.9", "R07.9", "Z34.0"}
        
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

