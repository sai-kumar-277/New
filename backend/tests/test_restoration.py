import json
from pathlib import Path

import pytest

from app.models.network import Topology, NormalizedEvent
from app.models.enums import ActionCategory
from app.agents.correlation import CorrelationAgent
from app.agents.localization import LocalizationAgent
from app.agents.impact import ImpactAgent
from app.agents.rca import RCAAgent
from app.agents.restoration import RestorationAgent

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

def test_restoration_cascade(topology, data_dir):
    events = load_events("scenario_cascade.json")
    incident_id = "INC-NET-101"
    
    correlator = CorrelationAgent(topology)
    clusters = correlator.group_events(events)
    cluster = clusters[0]
    correlation_result = correlator.correlate(cluster)
    
    localizer = LocalizationAgent(topology)
    hypotheses = localizer.localize(cluster, correlation_result)
    
    impact_agent = ImpactAgent(topology)
    impact = impact_agent.analyze(cluster, correlation_result, hypotheses)
    
    rca_agent = RCAAgent(topology, str(data_dir))
    matches, rca_hypotheses = rca_agent.analyze(cluster, correlation_result, hypotheses, [])
    
    restoration_agent = RestorationAgent(str(data_dir))
    actions = restoration_agent.plan(incident_id, rca_hypotheses, impact)
    
    assert len(actions) > 0
    
    # We should have actions across different risk categories based on SOP-001/002
    diagnostic_actions = [a for a in actions if a.category == ActionCategory.DIAGNOSTIC]
    disruptive_actions = [a for a in actions if a.category == ActionCategory.POTENTIALLY_DISRUPTIVE]
    
    assert len(diagnostic_actions) > 0
    assert len(disruptive_actions) > 0
    
    # Diagnostics should not require approval, disruptive must
    assert diagnostic_actions[0].requires_approval is False
    assert disruptive_actions[0].requires_approval is True
    
    # Order should be low-risk first
    assert actions[0].category == ActionCategory.DIAGNOSTIC
