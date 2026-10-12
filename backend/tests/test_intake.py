import json
from pathlib import Path
from datetime import datetime

import pytest

from app.models.network import Topology, EventType, Severity
from app.agents.intake import IntakeAgent

@pytest.fixture
def topology():
    topo_path = Path(__file__).parent.parent.parent / "data" / "topology.json"
    return Topology.from_file(topo_path)

@pytest.fixture
def raw_events():
    events_path = Path(__file__).parent.parent.parent / "data" / "alarms" / "scenario_vendor_raw.json"
    return json.loads(events_path.read_text())["raw_events"]

def test_intake_agent_syslog(topology, raw_events):
    agent = IntakeAgent(topology)
    evt = agent.process_event(raw_events[0])  # RAW-1 syslog
    assert evt.event_id == "RAW-1"
    assert evt.device == "AR-01"
    assert evt.event_type == EventType.INTERFACE_DOWN
    assert evt.severity == Severity.CRITICAL
    assert evt.interface == "GE-0/0/1"
    assert evt.source_format == "syslog"
    assert not evt.validation_flags

def test_intake_agent_snmp_trap(topology, raw_events):
    agent = IntakeAgent(topology)
    evt = agent.process_event(raw_events[1])  # RAW-2 snmp_trap
    assert evt.event_id == "RAW-2"
    assert evt.device == "AR-01"  # Resolved from 10.0.2.1
    assert evt.event_type == EventType.INTERFACE_DOWN
    assert evt.severity == Severity.CRITICAL
    assert evt.interface == "GE-0/0/1"
    assert evt.source_format == "snmp_trap"
    assert not evt.validation_flags

def test_intake_agent_vendor_json(topology, raw_events):
    agent = IntakeAgent(topology)
    evt = agent.process_event(raw_events[2])  # RAW-3 vendor_json
    assert evt.event_id == "RAW-3"
    assert evt.device == "BS-101"
    assert evt.event_type == EventType.BACKHAUL_CONNECTIVITY_LOST
    assert evt.severity == Severity.CRITICAL
    assert evt.source_format == "vendor_json"
    assert evt.timestamp == datetime(2026, 10, 3, 10, 2, 4)
    assert not evt.validation_flags

def test_intake_agent_invalid_timestamp(topology, raw_events):
    agent = IntakeAgent(topology)
    evt = agent.process_event(raw_events[3])  # RAW-4 vendor_json
    assert evt.event_id == "RAW-4"
    assert "invalid_timestamp" in evt.validation_flags

def test_intake_agent_missing_device(topology, raw_events):
    agent = IntakeAgent(topology)
    evt = agent.process_event(raw_events[5])  # RAW-6 snmp_trap
    assert evt.event_id == "RAW-6"
    assert evt.device == "UNKNOWN"
    assert "missing_device_identity" in evt.validation_flags

def test_intake_agent_simulated(topology):
    agent = IntakeAgent(topology)
    simulated_event = {
        "id": "SIM-1",
        "format": "simulated",
        "payload": {
            "event_id": "SIM-1",
            "timestamp": "2026-10-03T10:02:01",
            "device": "BS-102",
            "alarm_type": "backhaul_connectivity_lost",
            "severity": "critical"
        }
    }
    evt = agent.process_event(simulated_event)
    assert evt.event_id == "SIM-1"
    assert evt.device == "BS-102"
    assert evt.event_type == EventType.BACKHAUL_CONNECTIVITY_LOST
    assert evt.severity == Severity.CRITICAL
