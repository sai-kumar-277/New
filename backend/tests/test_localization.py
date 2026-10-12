import json
from pathlib import Path

import pytest

from app.models.network import Topology, NormalizedEvent
from app.agents.correlation import CorrelationAgent
from app.agents.localization import LocalizationAgent

@pytest.fixture
def topology():
    topo_path = Path(__file__).parent.parent.parent / "data" / "topology.json"
    return Topology.from_file(topo_path)

def load_events(scenario_file: str) -> list[NormalizedEvent]:
    path = Path(__file__).parent.parent.parent / "data" / "alarms" / scenario_file
    data = json.loads(path.read_text())
    return [NormalizedEvent.from_alarm_dict(d) for d in data["alarms"]]

def test_localization_cascade(topology):
    events = load_events("scenario_cascade.json")
    
    correlator = CorrelationAgent(topology)
    clusters = correlator.group_events(events)
    cluster = clusters[0]
    correlation_result = correlator.correlate(cluster)
    
    agent = LocalizationAgent(topology)
    hypotheses = agent.localize(cluster, correlation_result)
    
    assert len(hypotheses) >= 1
    h1 = hypotheses[0]
    
    # Primary event is on AR-01 GE-0/0/1, which connects to LNK-CR01-AR01
    assert h1.suspect_kind == "link"
    assert h1.suspect_id == "LNK-CR01-AR01"
    assert h1.confidence.value == "high"
    
    # It must have topology evidence
    assert len(h1.topology_evidence) > 0
    # Must have supporting alarms (the primary + the downstream)
    assert len(h1.supporting_alarm_ids) > 1

def test_localization_inferred(topology):
    # Test Strategy 2: Missing upstream alarm
    # We will pass only the consequential events from cascade
    events = load_events("scenario_cascade.json")
    events = [e for e in events if e.device != "AR-01"]
    
    correlator = CorrelationAgent(topology)
    clusters = correlator.group_events(events)
    cluster = clusters[0]
    correlation_result = correlator.correlate(cluster)
    
    agent = LocalizationAgent(topology)
    hypotheses = agent.localize(cluster, correlation_result)
    
    assert len(hypotheses) >= 1
    h1 = hypotheses[0]
    
    # The lowest common ancestor is AR-01
    assert h1.suspect_kind == "device"
    assert h1.suspect_id == "AR-01"
    assert "AR-01" in " ".join(h1.topology_evidence)
