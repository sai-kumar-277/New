import pytest
from datetime import datetime

from app.models.enums import (
    ActionCategory, ActionStatus, Confidence, EventRole, EventType,
    EvidenceSource, RootCauseCategory, Severity
)
from app.models.network import NormalizedEvent
from app.models.incident import (
    CorrelationResult, Evidence, FaultLocationHypothesis, IncidentState,
    RCAHypothesis, RestorationAction, ServiceImpact
)
from app.agents.reviewer import ReviewerAgent

def test_reviewer_validates_healthy_state():
    evt = NormalizedEvent(
        event_id="EVT-1",
        timestamp=datetime.now(),
        device="AR-01",
        event_type=EventType.INTERFACE_DOWN,
        severity=Severity.CRITICAL,
        interface="GE-0/0/1"
    )
    corr = CorrelationResult(
        roles={"EVT-1": EventRole.PRIMARY},
        primary_event_ids=["EVT-1"],
        rationale=["Single event"]
    )
    fl = FaultLocationHypothesis(
        rank=1,
        suspect_id="LNK-CR01-AR01",
        suspect_kind="link",
        confidence=Confidence.HIGH,
        supporting_alarm_ids=["EVT-1"],
        topology_evidence=["Interface down matches uplink"],
        summary="Fault at link"
    )
    rca = RCAHypothesis(
        rank=1,
        category=RootCauseCategory.PHYSICAL_LINK_FAILURE,
        description="Fiber cut",
        confidence=Confidence.HIGH,
        supporting_evidence=[
            Evidence(source=EvidenceSource.ALARM, reference="EVT-1", statement="Alarm present"),
            Evidence(source=EvidenceSource.TOPOLOGY, reference="LNK", statement="Topology matches")
        ],
        required_verification=["OTDR check"]
    )
    action = RestorationAction(
        action_id="ACT-1",
        incident_id="INC-1",
        description="Bounce interface",
        category=ActionCategory.POTENTIALLY_DISRUPTIVE,
        requires_approval=True
    )

    state = IncidentState(
        incident_id="INC-1",
        events=[evt],
        correlation=corr,
        fault_hypotheses=[fl],
        rca_hypotheses=[rca],
        actions=[action],
        service_impact=ServiceImpact(summary="No impact")
    )

    reviewer = ReviewerAgent()
    findings = reviewer.review(state)
    assert len(findings) > 0
    assert all(f.passed for f in findings)
    assert not any(f.request_reassessment for f in findings)
