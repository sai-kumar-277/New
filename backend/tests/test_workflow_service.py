import json
from pathlib import Path
import pytest

from app.models.enums import (
    ActionCategory, ActionStatus, ActorRole, Confidence, EventRole,
    EventType, IncidentStatus, RootCauseCategory, Severity
)
from app.models.incident import Actor, IncidentState
from app.models.network import NormalizedEvent, Topology
from app.graph.workflow import NetworkNOCWorkflow
from app.services.workflow_service import WorkflowService


@pytest.fixture
def topology():
    topo_path = Path(__file__).parent.parent.parent / "data" / "topology.json"
    return Topology.from_file(topo_path)


@pytest.fixture
def data_dir():
    return str(Path(__file__).parent.parent.parent / "data")


def load_events(scenario_file: str) -> list[NormalizedEvent]:
    path = Path(__file__).parent.parent.parent / "data" / "alarms" / scenario_file
    data = json.loads(path.read_text())
    return [NormalizedEvent.from_alarm_dict(d) for d in data["alarms"]]


def test_workflow_service_lifecycle_and_validation(topology, data_dir):
    events = load_events("scenario_cascade.json")
    state = IncidentState(incident_id="INC-NET-101", events=events)

    workflow = NetworkNOCWorkflow(topology, data_dir)
    state = workflow.run(state)
    service = WorkflowService(workflow, topology)

    engineer = Actor(name="Alice NOC", role=ActorRole.ENGINEER)

    # 1. Test Engineer Approval on Proposed Action
    proposed_actions = [a for a in state.actions if a.status == ActionStatus.PROPOSED]
    assert len(proposed_actions) > 0
    target_action = proposed_actions[0]

    is_disruptive = (target_action.category == ActionCategory.POTENTIALLY_DISRUPTIVE)
    service.approve_action(state, target_action.action_id, engineer, explicit=is_disruptive)
    assert target_action.status == ActionStatus.APPROVED
    assert target_action.approved_by == engineer.name

    # 2. Test State Transitions: In Progress -> Completed
    service.start_action(state, target_action.action_id, engineer)
    assert target_action.status == ActionStatus.IN_PROGRESS

    service.complete_action(state, target_action.action_id, engineer, result="Fiber spliced, signal restored")
    assert target_action.status == ActionStatus.COMPLETED

    # 3. Post-Restoration Validation (TC-07)
    validation = service.run_post_restoration_validation(
        state,
        pre_metrics={"packet_loss_pct": 8.5, "latency_ms": 180.0, "jitter_ms": 42.0},
        post_metrics={"packet_loss_pct": 0.4, "latency_ms": 22.0, "jitter_ms": 6.0}
    )
    assert validation.all_passed is True
    # Verify the action automatically verified upon validation pass
    assert target_action.status == ActionStatus.VERIFIED

    # 4. Generate PDF Report (Requirement 20)
    pdf_bytes = service.generate_pdf_report(state)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")


def test_dynamic_reassessment_tc08(topology, data_dir):
    events = load_events("scenario_cascade.json")
    state = IncidentState(incident_id="INC-NET-101", events=events)

    workflow = NetworkNOCWorkflow(topology, data_dir)
    state = workflow.run(state)
    service = WorkflowService(workflow, topology)

    initial_revision = state.revision

    # Simulate related new alarm during active incident: BS-103 backhaul lost
    related_event = NormalizedEvent.from_alarm_dict({
        "event_id": "EVT-DYNAMIC-1",
        "timestamp": "2026-10-03T10:05:00",
        "device": "BS-103",
        "alarm_type": "backhaul_connectivity_lost",
        "severity": "critical",
        "description": "Downstream BS-103 lost backhaul"
    })

    belongs, reassessed_state = service.handle_incoming_alarm(state, related_event)
    assert belongs is True
    assert reassessed_state.revision == initial_revision + 1
    assert "EVT-DYNAMIC-1" in [e.event_id for e in reassessed_state.events]
    assert len(reassessed_state.reassessments) > 0
    assert reassessed_state.reassessments[-1].belongs_to_incident is True

    # Simulate unrelated new alarm: BS-201 temperature alarm in different region
    unrelated_event = NormalizedEvent.from_alarm_dict({
        "event_id": "EVT-DYNAMIC-2",
        "timestamp": "2026-10-03T10:06:00",
        "device": "BS-201",
        "alarm_type": "high_temperature",
        "severity": "warning",
        "description": "Cabinet temperature high"
    })

    belongs_unrelated, _ = service.handle_incoming_alarm(reassessed_state, unrelated_event)
    assert belongs_unrelated is False
