import json
from pathlib import Path

import pytest

from app.models.network import Topology, NormalizedEvent
from app.models.enums import RootCauseCategory, Confidence
from app.agents.correlation import CorrelationAgent
from app.agents.localization import LocalizationAgent
from app.agents.rca import RCAAgent

@pytest.fixture
def topology():
    topo_path = Path(__file__).parent.parent.parent / "data" / "topology.json"
    return Topology.from_file(topo_path)

@pytest.fixture
def data_dir():
    return Path(__file__).parent.parent.parent / "data"

def load_events(scenario_file: str) -> list[NormalizedEvent]:
    path = Path(__file__).parent.parent.parent / "data" / "alarms" / scenario_file
    data = json.loads(path.read_text())
    return [NormalizedEvent.from_alarm_dict(d) for d in data["alarms"]]

def test_rca_cascade(topology, data_dir):
    events = load_events("scenario_cascade.json")
    
    correlator = CorrelationAgent(topology)
    clusters = correlator.group_events(events)
    cluster = clusters[0]
    correlation_result = correlator.correlate(cluster)
    
    localizer = LocalizationAgent(topology)
    hypotheses = localizer.localize(cluster, correlation_result)
    
    agent = RCAAgent(topology, str(data_dir))
    matches, rca_hypotheses = agent.analyze(cluster, correlation_result, hypotheses, [])
    
    # Check RAG matches
    # INC-NET-032 is the historical cascade (fiber uplink failure)
    assert len(matches) > 0
    assert any(m.incident_id == "INC-NET-032" for m in matches)
    
    # Check RCA Hypothesis
    assert len(rca_hypotheses) > 0
    h1 = rca_hypotheses[0]
    
    # The primary event is interface_down, so PHYSICAL_LINK_FAILURE should be generated
    assert h1.category == RootCauseCategory.PHYSICAL_LINK_FAILURE
    assert h1.confidence in [Confidence.HIGH, Confidence.MEDIUM]
    
    # It must have required_verification steps
    assert len(h1.required_verification) > 0
    
    # It should have evidence
    assert len(h1.supporting_evidence) >= 2 # Alarm + Topology
