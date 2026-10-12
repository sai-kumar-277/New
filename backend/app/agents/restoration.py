import os
import re
from pathlib import Path
from typing import List, Dict, Tuple

from app.models.enums import RootCauseCategory, ActionCategory, ActionStatus
from app.models.incident import RCAHypothesis, RestorationAction, ServiceImpact

class RestorationAgent:
    """Agent 7 - Service Restoration & Action Planning Agent
    Generates safe, evidence-based restoration recommendations from approved procedures (SOPs).
    """
    
    # Map root causes to primary SOPs
    SOP_MAP = {
        RootCauseCategory.PHYSICAL_LINK_FAILURE: ["SOP-001", "SOP-002"],
        RootCauseCategory.DEVICE_HARDWARE_FAILURE: ["SOP-004"],
        RootCauseCategory.INTERFACE_HARDWARE_FAILURE: ["SOP-001"],
        RootCauseCategory.CONFIGURATION_ISSUE: ["SOP-001", "SOP-004"],
        RootCauseCategory.ROUTING_ISSUE: ["SOP-001"],
        RootCauseCategory.NETWORK_CONGESTION: ["SOP-003"],
        RootCauseCategory.POWER_FAILURE: ["SOP-004", "SOP-002"],
        RootCauseCategory.SOFTWARE_PROCESS_FAILURE: ["SOP-004"],
        RootCauseCategory.EXTERNAL_CONNECTIVITY_FAILURE: ["SOP-001"],
        RootCauseCategory.TELEMETRY_SENSOR_ISSUE: ["SOP-005"],
        RootCauseCategory.UNKNOWN: []
    }
    
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.sops = self._load_sops()
        
    def _load_sops(self) -> Dict[str, str]:
        sops = {}
        sop_dir = self.data_dir / "sops"
        if sop_dir.exists():
            for file in sop_dir.glob("*.md"):
                # e.g. SOP-001_interface_down.md -> SOP-001
                sop_id = file.name.split("_")[0]
                sops[sop_id] = file.read_text()
        return sops

    def _parse_actions_from_sop(self, sop_id: str, sop_content: str, incident_id: str) -> List[RestorationAction]:
        actions = []
        action_count = 1
        
        # Regex to match list items with tags, e.g. "- [DIAGNOSTIC] Check stuff" or "1. [ESCALATE] Do something"
        # Groups: (1) Tag content e.g. "DIAGNOSTIC", (2) Description e.g. "Check stuff"
        pattern = re.compile(r"^[-*0-9.]+\s*\[(.*?)\]\s*(.*)", re.IGNORECASE)
        
        for line in sop_content.splitlines():
            line = line.strip()
            match = pattern.match(line)
            if match:
                tag = match.group(1).upper()
                desc = match.group(2)
                
                cat = ActionCategory.NON_DISRUPTIVE
                requires_approval = True
                
                if "DIAGNOSTIC" in tag:
                    cat = ActionCategory.DIAGNOSTIC
                    requires_approval = False # Diagnostics are usually read-only
                elif "DISRUPTIVE" in tag and "NON" not in tag:
                    cat = ActionCategory.POTENTIALLY_DISRUPTIVE
                elif "ESCALATE" in tag:
                    cat = ActionCategory.ESCALATION_REQUIRED
                    
                actions.append(RestorationAction(
                    action_id=f"ACT-{incident_id}-{sop_id}-{action_count}",
                    incident_id=incident_id,
                    description=desc,
                    category=cat,
                    rationale=f"Recommended per {sop_id} based on diagnosed fault.",
                    sop_reference=sop_id,
                    status=ActionStatus.PROPOSED,
                    requires_approval=requires_approval
                ))
                action_count += 1
                
        return actions

    def plan(self, incident_id: str, hypotheses: List[RCAHypothesis], impact: ServiceImpact) -> List[RestorationAction]:
        if not hypotheses:
            return []
            
        # Target the top hypothesis
        top_h = hypotheses[0]
        sop_ids = self.SOP_MAP.get(top_h.category, [])
        
        actions = []
        for sop_id in sop_ids:
            if sop_id in self.sops:
                sop_actions = self._parse_actions_from_sop(sop_id, self.sops[sop_id], incident_id)
                actions.extend(sop_actions)
                
        # Deduplicate and sort actions by risk (Diagnostic -> Non-disruptive -> Disruptive -> Escalate)
        # But we want to preserve the logical order from the SOPs.
        # So we can group them by category while preserving relative order
        diagnostics = [a for a in actions if a.category == ActionCategory.DIAGNOSTIC]
        non_disr = [a for a in actions if a.category == ActionCategory.NON_DISRUPTIVE]
        disruptive = [a for a in actions if a.category == ActionCategory.POTENTIALLY_DISRUPTIVE]
        escalate = [a for a in actions if a.category == ActionCategory.ESCALATION_REQUIRED]
        
        final_actions = diagnostics + non_disr + disruptive + escalate
        
        # Deduplicate descriptions
        seen_descs = set()
        unique_actions = []
        for a in final_actions:
            if a.description not in seen_descs:
                seen_descs.add(a.description)
                unique_actions.append(a)
                
        # Reset IDs to be clean 1..N
        for i, a in enumerate(unique_actions):
            a.action_id = f"ACT-{incident_id}-{i+1}"
            
        return unique_actions
