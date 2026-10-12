import json
from pathlib import Path

import pytest

from app.models.enums import ServiceState
from app.models.network import Topology, NormalizedEvent
from app.agents.correlation import CorrelationAgent
from app.agents.localization import LocalizationAgent
from app.agents.impact import ImpactAgent

@pytest.fixture
def topology():
    topo_path = Path(__file__).parent.parent.parent / "data" / "topology.json"
    return Topology.from_file(topo_path)

def load_events(scenario_file: str) -> list[NormalizedEvent]:
    path = Path(__file__).parent.parent.parent / "data" / "alarms" / scenario_file
    data = json.loads(path.read_text())
    return [NormalizedEvent.from_alarm_dict(d) for d in data["alarms"]]

def test_service_impact_cascade(topology):
    events = load_events("scenario_cascade.json")
    
    correlator = CorrelationAgent(topology)
    clusters = correlator.group_events(events)
    cluster = clusters[0]
    correlation_result = correlator.correlate(cluster)
    
    localizer = LocalizationAgent(topology)
    hypotheses = localizer.localize(cluster, correlation_result)
    
    agent = ImpactAgent(topology)
    impact = agent.analyze(cluster, correlation_result, hypotheses)
    
    # In cascade, AR-01 goes down. Confirmed devices: AR-01, BS-101, BS-102.
    assert "AR-01" in impact.affected_devices
    assert "BS-101" in impact.affected_devices
    assert "BS-102" in impact.affected_devices
    
    # BS-103 and E-101 depend on AR-01 but have no alarms. They should be in unconfirmed.
    assert "BS-103" in impact.unconfirmed_devices
    assert "E-101" in impact.unconfirmed_devices
    
    # Check services
    assert len(impact.services) == 4
    
    svc_101 = next(s for s in impact.services if s.service_id == "SVC-BS-101")
    assert svc_101.state == ServiceState.UNAVAILABLE
    assert svc_101.confirmed is True
    
    svc_103 = next(s for s in impact.services if s.service_id == "SVC-BS-103")
    assert svc_103.state == ServiceState.POTENTIALLY_AFFECTED
    assert svc_103.confirmed is False
    
    # Customer counts shouldn't be invented
    assert impact.customer_count is None
