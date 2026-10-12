import json
from pathlib import Path

import pytest

from app.models.network import Topology, NormalizedEvent
from app.agents.correlation import CorrelationAgent
from app.agents.anomaly import AnomalyAgent

@pytest.fixture
def topology():
    topo_path = Path(__file__).parent.parent.parent / "data" / "topology.json"
    return Topology.from_file(topo_path)

@pytest.fixture
def data_dir():
    return Path(__file__).parent.parent.parent / "data" / "telemetry"

def load_events(scenario_file: str) -> list[NormalizedEvent]:
    path = Path(__file__).parent.parent.parent / "data" / "alarms" / scenario_file
    data = json.loads(path.read_text())
    return [NormalizedEvent.from_alarm_dict(d) for d in data["alarms"]]

def test_anomaly_congestion(topology, data_dir):
    # Train/load model and instantiate agent
    agent = AnomalyAgent(topology, str(data_dir))
    
    events = load_events("scenario_congestion.json")
    
    correlator = CorrelationAgent(topology)
    clusters = correlator.group_events(events)
    cluster = clusters[0]
    correlation_result = correlator.correlate(cluster)
    
    findings = agent.analyze(cluster, correlation_result)
    
    assert len(findings) > 0
    
    
    # Check if we found the congestion on LNK-CR01-AR02-B
    # (since the alarm is AR-02 interface GE-0/0/1 down, which maps to LNK-CR01-AR02-A,
    # the traffic shifted to LNK-CR01-AR02-B)
    congested_link = None
    for f in findings:
        if f.entity_id == "LNK-CR01-AR02-B" and f.is_anomalous:
            congested_link = f
            break
            
    assert congested_link is not None, "Did not detect anomaly on redundant link"
    
    # Check explainability metrics
    assert len(congested_link.metrics) > 0
    metric_names = [m.metric for m in congested_link.metrics]
    assert "utilization_pct" in metric_names or "latency_ms" in metric_names or "packet_loss_pct" in metric_names
