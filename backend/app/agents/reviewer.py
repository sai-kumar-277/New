from typing import List

from app.models.enums import ActionCategory, Confidence
from app.models.incident import IncidentState, ReviewerFinding

class ReviewerAgent:
    """Agent 8 (Optional) - Network Operations Reviewer / Critic Agent
    Reviews the end-to-end diagnosis and restoration plan for validity, policy compliance,
    and hallucination/evidence alignment before human presentation.
    """

    def review(self, state: IncidentState) -> List[ReviewerFinding]:
        findings: List[ReviewerFinding] = []

        # 1. Verify Alarm Correlation
        if state.correlation:
            unassigned = [e.event_id for e in state.events if e.event_id not in state.correlation.roles]
            if unassigned:
                findings.append(ReviewerFinding(
                    check="alarm_correlation_completeness",
                    passed=False,
                    message=f"Alarms left without correlation role: {unassigned}",
                    request_reassessment=True
                ))
            else:
                findings.append(ReviewerFinding(
                    check="alarm_correlation_completeness",
                    passed=True,
                    message="All events accounted for in correlation."
                ))

            if not state.correlation.primary_event_ids:
                findings.append(ReviewerFinding(
                    check="primary_event_identified",
                    passed=False,
                    message="No primary event identified by correlation agent.",
                    request_reassessment=True
                ))
            else:
                findings.append(ReviewerFinding(
                    check="primary_event_identified",
                    passed=True,
                    message=f"Primary events confirmed: {state.correlation.primary_event_ids}"
                ))

        # 2. Validate Fault Localization Evidence
        for h in state.fault_hypotheses:
            if h.confidence == Confidence.HIGH:
                if not (h.supporting_alarm_ids and h.topology_evidence):
                    findings.append(ReviewerFinding(
                        check=f"fault_localization_evidence_rank_{h.rank}",
                        passed=False,
                        message=f"Hypothesis {h.suspect_id} has HIGH confidence but lacks both alarm and topology evidence.",
                        request_reassessment=True
                    ))
                else:
                    findings.append(ReviewerFinding(
                        check=f"fault_localization_evidence_rank_{h.rank}",
                        passed=True,
                        message=f"Hypothesis {h.suspect_id} adequately corroborated by topology and alarms."
                    ))

        # 3. Check Service Impact Rigor (No invented customer counts)
        if state.service_impact:
            if state.service_impact.customer_count is not None and not state.service_impact.customer_count_source:
                findings.append(ReviewerFinding(
                    check="service_impact_customer_counts",
                    passed=False,
                    message="Customer count provided without verifiable data source.",
                    request_reassessment=True
                ))
            else:
                findings.append(ReviewerFinding(
                    check="service_impact_customer_counts",
                    passed=True,
                    message="Customer count policy respected (no unsupported estimates)."
                ))

        # 4. Check Root Cause Evidence Rigor
        for rca in state.rca_hypotheses:
            if rca.confidence == Confidence.HIGH:
                sources = {e.source for e in rca.supporting_evidence}
                if len(rca.supporting_evidence) < 2 or len(sources) < 2:
                    findings.append(ReviewerFinding(
                        check=f"rca_evidence_rank_{rca.rank}",
                        passed=False,
                        message=f"RCA {rca.category.value} marked HIGH confidence without 2+ multi-source evidence points.",
                        request_reassessment=True
                    ))
                else:
                    findings.append(ReviewerFinding(
                        check=f"rca_evidence_rank_{rca.rank}",
                        passed=True,
                        message=f"RCA {rca.category.value} has multi-source corroboration."
                    ))

        # 5. Ensure Potentially Disruptive Actions Require Approval
        for action in state.actions:
            if action.category == ActionCategory.POTENTIALLY_DISRUPTIVE:
                if not action.requires_approval:
                    findings.append(ReviewerFinding(
                        check=f"safety_approval_guard_{action.action_id}",
                        passed=False,
                        message=f"Disruptive action '{action.description}' lacks mandatory approval requirement!",
                        request_reassessment=True
                    ))
                else:
                    findings.append(ReviewerFinding(
                        check=f"safety_approval_guard_{action.action_id}",
                        passed=True,
                        message=f"Disruptive action '{action.action_id}' properly gated behind human approval."
                    ))

        return findings
