"""Tests for the shared-state models and the project's sample data."""
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.models import (Actor, ActionCategory, ActionError, ActionStatus, ActorRole, AnomalyFinding,
                        Confidence, CorrelationResult, DecisionType, Evidence, EventRole, EvidenceSource,
                        FaultLocationHypothesis, HumanDecision, IncidentState, NormalizedEvent,
                        PostRestorationValidation, RCAHypothesis, RestorationAction, RootCauseCategory,
                        RootCauseStatus, ServiceImpact, Topology, ValidationCheck,
                        load_historical_incidents)

DATA = Path(__file__).resolve().parents[2] / "data"
ENG = Actor(name="noc.engineer", role=ActorRole.ENGINEER)
BOT = Actor(name="restoration_agent", role=ActorRole.AGENT)
T0 = datetime(2026, 10, 3, 10, 5, 0)


def cascade_events():
    sc = json.loads((DATA / "alarms" / "scenario_cascade.json").read_text())
    return [NormalizedEvent.from_alarm_dict(a) for a in sc["alarms"]]


def cascade_correlation(events):
    roles = {events[0].event_id: EventRole.PRIMARY}
    roles.update({e.event_id: EventRole.CONSEQUENTIAL for e in events[1:]})
    return CorrelationResult(roles=roles, primary_event_ids=[events[0].event_id])


def make_action(category=ActionCategory.POTENTIALLY_DISRUPTIVE, incident_id="INC-NET-101"):
    return RestorationAction(action_id="ACT-1", incident_id=incident_id,
                             description="Bounce GE-0/0/1", category=category)


# ------------------------------ sample data --------------------------------- #
def test_topology_loads_and_is_consistent():
    t = Topology.from_file(DATA / "topology.json")
    assert (len(t.devices), len(t.links), len(t.services)) == (11, 11, 7)
    assert all(s.customer_count is None for s in t.services)  # customer counts are never invented


def test_every_alarm_scenario_parses_with_known_event_types():
    total = 0
    for f in (DATA / "alarms").glob("scenario_*.json"):
        for a in json.loads(f.read_text()).get("alarms", []):
            e = NormalizedEvent.from_alarm_dict(a)
            assert not e.validation_flags, (f.name, a["alarm_type"])
            total += 1
    assert total == 313  # cascade 5 + single 2 + dynamic 2 + congestion 4 + storm 300


def test_historical_incidents_parse_and_include_inc_net_032():
    recs = load_historical_incidents(DATA / "incidents.json")
    assert len(recs) == 8
    assert "INC-NET-032" in {r.incident_id for r in recs}


# ------------------------------ events -------------------------------------- #
def test_events_are_immutable_evidence():
    e = cascade_events()[0]
    with pytest.raises(ValidationError):
        e.device = "AR-02"


def test_unknown_alarm_type_is_flagged_not_dropped():
    e = NormalizedEvent.from_alarm_dict({"event_id": "X1", "timestamp": "2026-10-03T10:00:00",
                                         "device": "AR-01", "alarm_type": "weird_vendor_thing",
                                         "severity": "minor"})
    assert e.event_type.value == "other"
    assert e.validation_flags == ["unknown_event_type:weird_vendor_thing"]


# ------------------------------ state invariants ---------------------------- #
def test_incident_state_roundtrips_through_json():
    ev = cascade_events()
    s = IncidentState(incident_id="INC-NET-101", events=ev, correlation=cascade_correlation(ev))
    again = IncidentState.model_validate_json(s.model_dump_json())
    assert again == s
    assert [e.event_id for e in again.primary_events] == ["EVT-10425"]


def test_correlation_cannot_drop_or_invent_events():
    ev = cascade_events()
    roles = {e.event_id: EventRole.CONSEQUENTIAL for e in ev[:-1]}  # last event unlabeled
    corr = CorrelationResult(roles=roles, primary_event_ids=[])
    with pytest.raises(ValidationError, match="evidence must not vanish"):
        IncidentState(incident_id="INC-1", events=ev, correlation=corr)
    roles2 = {e.event_id: EventRole.CONSEQUENTIAL for e in ev}
    roles2["EVT-GHOST"] = EventRole.CONSEQUENTIAL
    with pytest.raises(ValidationError, match="not in the incident"):
        IncidentState(incident_id="INC-1", events=ev,
                      correlation=CorrelationResult(roles=roles2, primary_event_ids=[]))


def test_primary_must_have_primary_role():
    with pytest.raises(ValidationError):
        CorrelationResult(roles={"E1": EventRole.CONSEQUENTIAL}, primary_event_ids=["E1"])


def test_action_must_belong_to_incident():
    with pytest.raises(ValidationError, match="belongs to"):
        IncidentState(incident_id="INC-A", actions=[make_action(incident_id="INC-B")])


# ------------------------------ hypotheses ---------------------------------- #
def test_fault_hypothesis_needs_evidence():
    with pytest.raises(ValidationError, match="must cite evidence"):
        FaultLocationHypothesis(rank=1, suspect_id="AR-01", confidence=Confidence.LOW)


def test_high_confidence_fault_needs_alarms_and_topology():
    with pytest.raises(ValidationError, match="HIGH confidence"):
        FaultLocationHypothesis(rank=1, suspect_id="AR-01", confidence=Confidence.HIGH,
                                supporting_alarm_ids=["EVT-10425"])
    ok = FaultLocationHypothesis(rank=1, suspect_id="AR-01", confidence=Confidence.HIGH,
                                 supporting_alarm_ids=["EVT-10425"],
                                 topology_evidence=["BS-101 and BS-102 depend on AR-01"])
    assert ok.suspect_id == "AR-01"


def test_rca_needs_verification_steps_and_corroboration_for_high_confidence():
    ev = Evidence(source=EvidenceSource.ALARM, reference="EVT-10425", statement="interface down first")
    with pytest.raises(ValidationError, match="verify"):
        RCAHypothesis(rank=1, category=RootCauseCategory.PHYSICAL_LINK_FAILURE, description="x",
                      confidence=Confidence.LOW, supporting_evidence=[ev])
    with pytest.raises(ValidationError, match="HIGH confidence"):
        RCAHypothesis(rank=1, category=RootCauseCategory.PHYSICAL_LINK_FAILURE, description="x",
                      confidence=Confidence.HIGH, supporting_evidence=[ev, ev],
                      required_verification=["check optics"])  # same source twice is not corroboration
    topo = Evidence(source=EvidenceSource.TOPOLOGY, reference="LNK-CR01-AR01", statement="single uplink")
    assert RCAHypothesis(rank=1, category=RootCauseCategory.PHYSICAL_LINK_FAILURE, description="x",
                         confidence=Confidence.HIGH, supporting_evidence=[ev, topo],
                         required_verification=["check optics"])


def test_service_impact_refuses_unsourced_customer_count():
    with pytest.raises(ValidationError, match="customer_count_source"):
        ServiceImpact(customer_count=1200)
    assert ServiceImpact(customer_count=1200, customer_count_source="CRM export 2026-10-01").customer_count == 1200


def test_anomaly_window_must_be_ordered():
    with pytest.raises(ValidationError):
        AnomalyFinding(entity_id="LNK-CR01-AR01", window_start=T0, window_end=T0 - timedelta(minutes=1),
                       method="zscore", anomaly_score=0.9, is_anomalous=True)


# ------------------------------ approval workflow --------------------------- #
def test_agent_cannot_approve_its_own_action():
    a = make_action()
    with pytest.raises(ActionError, match="human engineer"):
        a.approve(BOT, explicit=True)
    assert a.status == ActionStatus.PROPOSED


def test_disruptive_action_needs_explicit_authorization():
    a = make_action()
    with pytest.raises(ActionError, match="explicit"):
        a.approve(ENG)                         # approving without explicit=True is not enough
    a.approve(ENG, explicit=True, at=T0)
    assert a.status == ActionStatus.APPROVED and a.approved_by == "noc.engineer"


def test_diagnostic_action_does_not_need_explicit_flag_but_still_needs_engineer():
    a = make_action(ActionCategory.DIAGNOSTIC)
    a.approve(ENG, at=T0)
    assert a.status == ActionStatus.APPROVED


def test_full_lifecycle_and_verification_gate():
    a = make_action()
    a.approve(ENG, explicit=True, at=T0)
    a.start(ENG, at=T0 + timedelta(minutes=1))
    a.complete(ENG, "interface restored", at=T0 + timedelta(minutes=9))
    with pytest.raises(ActionError, match="validation did not pass"):
        a.verify(False)
    a.verify(True, at=T0 + timedelta(minutes=20))
    assert a.status == ActionStatus.VERIFIED


def test_illegal_transitions_are_blocked():
    a = make_action()
    with pytest.raises(ActionError, match="illegal transition"):
        a.start(ENG)                           # cannot skip approval
    a.reject(ENG, "too risky during peak hours")
    with pytest.raises(ActionError, match="illegal transition"):
        a.approve(ENG, explicit=True)          # rejected is final
    b = make_action()
    b.approve(ENG, explicit=True, at=T0)
    b.start(ENG, at=T0 + timedelta(minutes=5))
    with pytest.raises(ActionError, match="before start"):
        b.complete(ENG, "done", at=T0)


def test_engineer_can_modify_only_while_proposed():
    a = make_action()
    a.modify(ENG, "Verify interface state only", comment="reduce risk")
    assert a.description == "Verify interface state only" and a.remarks
    a.approve(ENG, explicit=True, at=T0)
    with pytest.raises(ActionError, match="while proposed"):
        a.modify(ENG, "again")


def test_tampered_state_is_rejected_on_load():
    """A disruptive action marked in-progress without approval must fail validation."""
    bad = make_action().model_dump(mode="json")
    bad["status"] = "in_progress"
    with pytest.raises(ValidationError):
        RestorationAction.model_validate(bad)
    bad2 = make_action().model_dump(mode="json")
    bad2["requires_approval"] = False
    with pytest.raises(ValidationError, match="must require approval"):
        RestorationAction.model_validate(bad2)


def test_human_decisions_must_come_from_an_engineer():
    with pytest.raises(ValidationError, match="engineer"):
        HumanDecision(decision_id="D1", actor=BOT, decision_type=DecisionType.APPROVE_ACTION)


# ------------------------------ root cause status --------------------------- #
def test_root_cause_is_suspected_until_engineer_confirms():
    s = IncidentState(incident_id="INC-1")
    assert s.root_cause_status == RootCauseStatus.UNDETERMINED
    with pytest.raises(ActionError, match="human engineer"):
        s.confirm_root_cause(BOT, RootCauseCategory.PHYSICAL_LINK_FAILURE, "looks right")
    with pytest.raises(ActionError, match="verification note"):
        s.confirm_root_cause(ENG, RootCauseCategory.PHYSICAL_LINK_FAILURE, "  ")
    s.confirm_root_cause(ENG, RootCauseCategory.PHYSICAL_LINK_FAILURE, "Field team found fiber cut")
    assert s.root_cause_status == RootCauseStatus.CONFIRMED
    IncidentState.model_validate_json(s.model_dump_json())  # still valid after round trip


def test_confirmed_category_without_confirmed_status_is_invalid():
    with pytest.raises(ValidationError, match="not CONFIRMED"):
        IncidentState(incident_id="INC-1", confirmed_root_cause=RootCauseCategory.POWER_FAILURE)


def test_validation_all_passed_requires_checks_and_all_true():
    assert not PostRestorationValidation(checks=[]).all_passed
    ok = PostRestorationValidation(checks=[ValidationCheck(name="packet_loss", passed=True, before=8.5, after=0.4)])
    assert ok.all_passed
    bad = PostRestorationValidation(checks=[ValidationCheck(name="a", passed=True),
                                            ValidationCheck(name="b", passed=False)])
    assert not bad.all_passed
