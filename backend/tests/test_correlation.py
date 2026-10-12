import json
from pathlib import Path

import pytest

from app.models.network import Topology, NormalizedEvent
from app.models.enums import EventRole
from app.agents.correlation import CorrelationAgent

@pytest.fixture
def topology():
    topo_path = Path(__file__).parent.parent.parent / "data" / "topology.json"
    return Topology.from_file(topo_path)

def load_events(scenario_file: str) -> list[NormalizedEvent]:
    path = Path(__file__).parent.parent.parent / "data" / "alarms" / scenario_file
    data = json.loads(path.read_text())
    return [NormalizedEvent.from_alarm_dict(d) for d in data["alarms"]]

def test_correlation_cascade(topology):
    events = load_events("scenario_cascade.json")
    agent = CorrelationAgent(topology)
    
    # We group the events first
    clusters = agent.group_events(events)
    
    # Cascade scenario should form exactly 1 cluster
    assert len(clusters) == 1
    cluster = clusters[0]
    assert len(cluster) == 5
    
    # Correlate
    result = agent.correlate(cluster)
    
    # AR-01 is the root device (ancestor to BS-101 and BS-102)
    assert result.primary_event_ids == ["EVT-10425"]
    assert result.roles["EVT-10425"] == EventRole.PRIMARY
    assert result.roles["EVT-10426"] == EventRole.CONSEQUENTIAL
    assert result.roles["EVT-10427"] == EventRole.CONSEQUENTIAL
    assert result.roles["EVT-10428"] == EventRole.CONSEQUENTIAL
    assert result.roles["EVT-10429"] == EventRole.CONSEQUENTIAL
    
    assert not result.storm_detected

def test_correlation_storm(topology):
    events = load_events("scenario_storm.json")
    agent = CorrelationAgent(topology)
    
    clusters = agent.group_events(events)
    
    # Expected clusters: 3
    assert len(clusters) == 3
    
    storm_cluster = None
    for c in clusters:
        if len(c) > 10:
            storm_cluster = c
            
    assert storm_cluster is not None
    result = agent.correlate(storm_cluster)
    
    assert result.storm_detected
    
    # CR-01 is upstream of AR-02, so CR-01 events should be primary
    # EVT-20003 is CR-01 interface down
    assert "EVT-20003" in result.primary_event_ids
    
    # Duplicates should be correctly identified
    duplicates = [eid for eid, role in result.roles.items() if role == EventRole.DUPLICATE]
    assert len(duplicates) > 10
