import json
from pathlib import Path
import pytest

from app.models.enums import IncidentStatus, RootCauseCategory
from app.models.network import Topology, NormalizedEvent
from app.models.incident import IncidentState
from app.graph.workflow import NetworkNOCWorkflow


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


def test_end_to_end_cascade_workflow(topology, data_dir):
    events = load_events("scenario_cascade.json")

    initial_state = IncidentState(
        incident_id="INC-NET-101",
        events=events
    )

    workflow = NetworkNOCWorkflow(topology, data_dir)
    final_state = workflow.run(initial_state)

    # 1. Pipeline reached approval status
    assert final_state.status == IncidentStatus.AWAITING_APPROVAL

    # 2. Correlation completed
    assert final_state.correlation is not None
    assert final_state.correlation.primary_event_ids == ["EVT-10425"]

    # 3. Fault localization produced hypotheses
    assert len(final_state.fault_hypotheses) > 0
    assert final_state.fault_hypotheses[0].suspect_id == "LNK-CR01-AR01"

    # 4. Service impact completed
    assert final_state.service_impact is not None
    assert "BS-101" in final_state.service_impact.affected_devices
    assert "BS-103" in final_state.service_impact.unconfirmed_devices

    # 5. RCA completed via RAG
    assert len(final_state.rca_hypotheses) > 0
    assert final_state.rca_hypotheses[0].category == RootCauseCategory.PHYSICAL_LINK_FAILURE
    assert any(m.incident_id == "INC-NET-032" for m in final_state.historical_matches)

    # 6. Restoration actions planned
    assert len(final_state.actions) > 0

    # 7. Reviewer safety checks ran
    assert len(final_state.reviewer_findings) > 0
    assert all(f.passed for f in final_state.reviewer_findings)

    # 8. Agent trace recorded full lifecycle execution
    assert len(final_state.trace) == 7
    agents_in_trace = [t.agent.value for t in final_state.trace]
    assert agents_in_trace == [
        "correlation", "localization", "anomaly", "service_impact",
        "root_cause", "restoration", "reviewer"
    ]
