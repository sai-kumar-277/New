"""The shared workflow state passed between agents.

Design rules enforced in code (not just documented):
  1. Original alarms are immutable evidence and are never removed from the incident.
  2. Hypotheses must carry evidence; HIGH confidence needs corroboration.
  3. Root cause is SUSPECTED until an engineer CONFIRMS it with a verification note.
  4. Restoration actions follow Proposed -> Approved -> In Progress -> Completed -> Verified.
     Only a human engineer can approve, and potentially disruptive actions additionally
     need explicit authorization. An agent can never approve its own recommendation.
  5. Customer counts are never invented: a number needs a named data source.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, Union

from pydantic import BaseModel, Field, computed_field, model_validator

from .enums import (ActionCategory, ActionStatus, ActorRole, AgentName, Confidence, DecisionType,
                    EventRole, EvidenceSource, IncidentStatus, RootCauseCategory, RootCauseStatus,
                    ServiceState)
from .network import NormalizedEvent


def _now() -> datetime:
    return datetime.now().replace(microsecond=0)


# --------------------------------------------------------------------------- #
# Small shared pieces
# --------------------------------------------------------------------------- #
class Actor(BaseModel):
    name: str
    role: ActorRole


class Evidence(BaseModel):
    source: EvidenceSource
    reference: str       # e.g. "EVT-10425", "LNK-CR01-AR01", "SOP-001 s3"
    statement: str       # plain-language explanation shown to the engineer


class MetricComparison(BaseModel):
    metric: str
    normal: Optional[float] = None
    current: Optional[float] = None
    unit: str = ""


# --------------------------------------------------------------------------- #
# Agent 2: correlation
# --------------------------------------------------------------------------- #
class CorrelationResult(BaseModel):
    roles: dict[str, EventRole]                 # event_id -> role (events themselves stay untouched)
    primary_event_ids: list[str]
    duplicate_of: dict[str, str] = Field(default_factory=dict)   # duplicate event_id -> kept event_id
    storm_detected: bool = False
    time_window_seconds: int = 60
    rationale: list[str] = Field(default_factory=list)
    engineer_confirmed: Optional[bool] = None   # None = not reviewed yet

    @model_validator(mode="after")
    def _consistent(self) -> "CorrelationResult":
        for eid in self.primary_event_ids:
            if self.roles.get(eid) != EventRole.PRIMARY:
                raise ValueError(f"{eid} listed as primary but its role is {self.roles.get(eid)}")
        for dup, kept in self.duplicate_of.items():
            if self.roles.get(dup) != EventRole.DUPLICATE:
                raise ValueError(f"{dup} in duplicate_of but role is not duplicate")
            if kept not in self.roles:
                raise ValueError(f"duplicate_of target {kept} is not part of this correlation")
        return self

    def count(self, role: EventRole) -> int:
        return sum(1 for r in self.roles.values() if r == role)


# --------------------------------------------------------------------------- #
# Agent 3: topology and fault localization
# --------------------------------------------------------------------------- #
class FaultLocationHypothesis(BaseModel):
    rank: int = Field(ge=1)
    suspect_id: str                              # device id or link id
    suspect_kind: str = "device"                 # device | link | interface
    confidence: Confidence
    confidence_score: Optional[float] = Field(default=None, ge=0, le=1)
    supporting_alarm_ids: list[str] = Field(default_factory=list)
    topology_evidence: list[str] = Field(default_factory=list)
    telemetry_evidence: list[str] = Field(default_factory=list)
    contradicting_evidence: list[str] = Field(default_factory=list)
    summary: str = ""

    @model_validator(mode="after")
    def _needs_evidence(self) -> "FaultLocationHypothesis":
        if not (self.supporting_alarm_ids or self.topology_evidence or self.telemetry_evidence):
            raise ValueError("a fault hypothesis must cite evidence, not just name a device")
        if self.confidence == Confidence.HIGH and not (self.supporting_alarm_ids and self.topology_evidence):
            raise ValueError("HIGH confidence requires both supporting alarms and topology evidence")
        return self


# --------------------------------------------------------------------------- #
# Agent 4: anomaly detection
# --------------------------------------------------------------------------- #
class AnomalyFinding(BaseModel):
    entity_id: str                               # link or device id
    window_start: datetime
    window_end: datetime
    method: str                                  # e.g. "zscore+isolation_forest"
    anomaly_score: float
    is_anomalous: bool
    metrics: list[MetricComparison] = Field(default_factory=list)
    suspected_sensor_issue: bool = False         # e.g. flat-lined or impossible values
    notes: str = ""

    @model_validator(mode="after")
    def _window(self) -> "AnomalyFinding":
        if self.window_end < self.window_start:
            raise ValueError("window_end before window_start")
        return self


# --------------------------------------------------------------------------- #
# Agent 5: service impact
# --------------------------------------------------------------------------- #
class ServiceImpactItem(BaseModel):
    service_id: str
    state: ServiceState
    confirmed: bool                              # True only if backed by an alarm or telemetry
    redundancy_available: bool = False
    reason: str = ""


class ServiceImpact(BaseModel):
    affected_devices: list[str] = Field(default_factory=list)      # confirmed by alarms
    unconfirmed_devices: list[str] = Field(default_factory=list)   # depend on the fault, no alarm yet
    affected_links: list[str] = Field(default_factory=list)
    services: list[ServiceImpactItem] = Field(default_factory=list)
    customer_count: Optional[int] = None
    customer_count_source: Optional[str] = None
    summary: str = ""

    @model_validator(mode="after")
    def _no_invented_counts(self) -> "ServiceImpact":
        if self.customer_count is not None and not self.customer_count_source:
            raise ValueError("customer_count requires customer_count_source; do not estimate without data")
        return self


# --------------------------------------------------------------------------- #
# Retrieval: history and procedures
# --------------------------------------------------------------------------- #
class HistoricalMatch(BaseModel):
    incident_id: str
    similarity: float = Field(ge=0, le=1)
    matched_on: list[str] = Field(default_factory=list)
    root_cause_category: RootCauseCategory
    caveat: str = "Historical evidence only; it does not establish the current root cause."


class ProcedureReference(BaseModel):
    doc_id: str                                  # e.g. SOP-001
    title: str
    section: str
    excerpt: str
    score: Optional[float] = None


# --------------------------------------------------------------------------- #
# Agent 6: root cause analysis
# --------------------------------------------------------------------------- #
class RCAHypothesis(BaseModel):
    rank: int = Field(ge=1)
    category: RootCauseCategory
    description: str
    supporting_evidence: list[Evidence] = Field(default_factory=list)
    contradicting_evidence: list[Evidence] = Field(default_factory=list)
    confidence: Confidence
    confidence_score: Optional[float] = Field(default=None, ge=0, le=1)
    required_verification: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _evidence_rules(self) -> "RCAHypothesis":
        if not self.required_verification:
            raise ValueError("every hypothesis must state what is needed to verify it")
        if self.confidence == Confidence.HIGH:
            sources = {e.source for e in self.supporting_evidence}
            if len(self.supporting_evidence) < 2 or len(sources) < 2:
                raise ValueError("HIGH confidence needs 2+ supporting items from 2+ distinct sources")
        return self


# --------------------------------------------------------------------------- #
# Agent 7: restoration planning and action tracking
# --------------------------------------------------------------------------- #
_ALLOWED_TRANSITIONS: dict[ActionStatus, set[ActionStatus]] = {
    ActionStatus.PROPOSED: {ActionStatus.APPROVED, ActionStatus.REJECTED},
    ActionStatus.APPROVED: {ActionStatus.IN_PROGRESS},
    ActionStatus.IN_PROGRESS: {ActionStatus.COMPLETED},
    ActionStatus.COMPLETED: {ActionStatus.VERIFIED},
    ActionStatus.REJECTED: set(),
    ActionStatus.VERIFIED: set(),
}


class ActionError(ValueError):
    """Raised when an action change would break the approval rules."""


class RestorationAction(BaseModel):
    action_id: str
    incident_id: str
    description: str
    category: ActionCategory
    rationale: str = ""
    sop_reference: Optional[str] = None
    status: ActionStatus = ActionStatus.PROPOSED
    requires_approval: bool = True
    assigned_to: Optional[str] = None
    approved_by: Optional[str] = None
    explicit_authorization: bool = False
    proposed_at: datetime = Field(default_factory=_now)
    approved_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    result: Optional[str] = None
    remarks: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _invariants(self) -> "RestorationAction":
        if self.category == ActionCategory.POTENTIALLY_DISRUPTIVE and not self.requires_approval:
            raise ValueError("potentially disruptive actions must require approval")
        past_proposal = self.status not in (ActionStatus.PROPOSED, ActionStatus.REJECTED)
        if past_proposal and not self.approved_by:
            raise ValueError(f"status {self.status.value} requires an approver")
        if (past_proposal and self.category == ActionCategory.POTENTIALLY_DISRUPTIVE
                and not self.explicit_authorization):
            raise ValueError("disruptive action advanced without explicit authorization")
        return self

    # -- guarded transitions ------------------------------------------------ #
    def _require_engineer(self, actor: Actor) -> None:
        if actor.role != ActorRole.ENGINEER:
            raise ActionError("only a human engineer may take this step")

    def _move(self, new: ActionStatus) -> None:
        if new not in _ALLOWED_TRANSITIONS[self.status]:
            raise ActionError(f"illegal transition {self.status.value} -> {new.value}")
        self.status = new

    def modify(self, actor: Actor, new_description: str, comment: str = "") -> None:
        self._require_engineer(actor)
        if self.status != ActionStatus.PROPOSED:
            raise ActionError("an action can only be modified while proposed")
        self.remarks.append(f"modified by {actor.name}: was '{self.description}'. {comment}".strip())
        self.description = new_description

    def approve(self, actor: Actor, explicit: bool = False, at: Optional[datetime] = None) -> None:
        self._require_engineer(actor)
        if self.category == ActionCategory.POTENTIALLY_DISRUPTIVE and not explicit:
            raise ActionError("potentially disruptive action needs explicit authorization")
        self._move(ActionStatus.APPROVED)
        self.approved_by = actor.name
        self.explicit_authorization = explicit
        self.approved_at = at or _now()

    def reject(self, actor: Actor, reason: str) -> None:
        self._require_engineer(actor)
        self._move(ActionStatus.REJECTED)
        self.remarks.append(f"rejected by {actor.name}: {reason}")

    def start(self, actor: Actor, at: Optional[datetime] = None) -> None:
        self._require_engineer(actor)
        self._move(ActionStatus.IN_PROGRESS)
        self.started_at = at or _now()

    def complete(self, actor: Actor, result: str, at: Optional[datetime] = None) -> None:
        self._require_engineer(actor)
        when = at or _now()
        if self.started_at and when < self.started_at:
            raise ActionError("completion time is before start time")
        self._move(ActionStatus.COMPLETED)
        self.completed_at = when
        self.result = result

    def verify(self, validation_passed: bool, at: Optional[datetime] = None) -> None:
        if not validation_passed:
            raise ActionError("cannot mark verified: post-restoration validation did not pass")
        self._move(ActionStatus.VERIFIED)
        self.verified_at = at or _now()


# --------------------------------------------------------------------------- #
# Reviewer, human decisions, validation, reassessment, trace
# --------------------------------------------------------------------------- #
class ReviewerFinding(BaseModel):
    check: str
    passed: bool
    message: str
    request_reassessment: bool = False


class HumanDecision(BaseModel):
    decision_id: str
    at: datetime = Field(default_factory=_now)
    actor: Actor
    decision_type: DecisionType
    target_id: Optional[str] = None              # event / action / hypothesis id
    comment: str = ""

    @model_validator(mode="after")
    def _human_only(self) -> "HumanDecision":
        if self.actor.role != ActorRole.ENGINEER:
            raise ValueError("human decisions must be made by an engineer")
        return self


class ValidationCheck(BaseModel):
    name: str                                    # alarm_clearance, interface_status, latency, ...
    passed: bool
    before: Optional[Union[float, str]] = None
    after: Optional[Union[float, str]] = None
    detail: str = ""


class PostRestorationValidation(BaseModel):
    performed_at: datetime = Field(default_factory=_now)
    observation_minutes: int = Field(default=15, ge=0)
    checks: list[ValidationCheck]

    @computed_field
    @property
    def all_passed(self) -> bool:
        return bool(self.checks) and all(c.passed for c in self.checks)


class ReassessmentRecord(BaseModel):
    at: datetime = Field(default_factory=_now)
    trigger_event_id: str
    belongs_to_incident: bool
    material_change: bool
    actions_taken: list[str] = Field(default_factory=list)
    summary: str = ""


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result_summary: str = ""


class AgentTraceEntry(BaseModel):
    agent: AgentName
    started_at: datetime = Field(default_factory=_now)
    finished_at: Optional[datetime] = None
    input_summary: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    output_summary: str = ""
    status: str = "ok"                           # ok | error | skipped


# --------------------------------------------------------------------------- #
# The shared state
# --------------------------------------------------------------------------- #
class IncidentState(BaseModel):
    incident_id: str
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    status: IncidentStatus = IncidentStatus.NEW
    revision: int = 1                            # incremented on every reassessment
    current_agent: Optional[AgentName] = None

    events: list[NormalizedEvent] = Field(default_factory=list)   # original evidence, never removed
    correlation: Optional[CorrelationResult] = None
    fault_hypotheses: list[FaultLocationHypothesis] = Field(default_factory=list)
    anomalies: list[AnomalyFinding] = Field(default_factory=list)
    service_impact: Optional[ServiceImpact] = None
    historical_matches: list[HistoricalMatch] = Field(default_factory=list)
    procedure_refs: list[ProcedureReference] = Field(default_factory=list)
    rca_hypotheses: list[RCAHypothesis] = Field(default_factory=list)

    root_cause_status: RootCauseStatus = RootCauseStatus.UNDETERMINED
    confirmed_root_cause: Optional[RootCauseCategory] = None
    confirmed_root_cause_note: Optional[str] = None
    confirmed_by: Optional[str] = None

    actions: list[RestorationAction] = Field(default_factory=list)
    reviewer_findings: list[ReviewerFinding] = Field(default_factory=list)
    human_decisions: list[HumanDecision] = Field(default_factory=list)
    validation: Optional[PostRestorationValidation] = None
    reassessments: list[ReassessmentRecord] = Field(default_factory=list)
    trace: list[AgentTraceEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def _invariants(self) -> "IncidentState":
        ids = {e.event_id for e in self.events}
        if len(ids) != len(self.events):
            raise ValueError("duplicate event_id in incident events")
        if self.correlation:
            missing = set(self.correlation.roles) - ids
            if missing:
                raise ValueError(f"correlation references events not in the incident: {sorted(missing)}")
            unlabeled = ids - set(self.correlation.roles)
            if unlabeled:
                raise ValueError(f"events with no correlation role (evidence must not vanish): {sorted(unlabeled)}")
        for a in self.actions:
            if a.incident_id != self.incident_id:
                raise ValueError(f"action {a.action_id} belongs to {a.incident_id}")
        if self.root_cause_status == RootCauseStatus.CONFIRMED:
            if not (self.confirmed_root_cause and self.confirmed_by and self.confirmed_root_cause_note):
                raise ValueError("confirmed root cause needs category, engineer and verification note")
        elif self.confirmed_root_cause is not None:
            raise ValueError("confirmed_root_cause set while status is not CONFIRMED")
        return self

    # -- helpers ------------------------------------------------------------- #
    def touch(self) -> None:
        self.updated_at = _now()

    def add_trace(self, entry: AgentTraceEntry) -> None:
        self.trace.append(entry)
        self.touch()

    def record_decision(self, decision: HumanDecision) -> None:
        self.human_decisions.append(decision)
        self.touch()

    def get_action(self, action_id: str) -> RestorationAction:
        for a in self.actions:
            if a.action_id == action_id:
                return a
        raise KeyError(action_id)

    def confirm_root_cause(self, actor: Actor, category: RootCauseCategory, verification_note: str) -> None:
        """Only an engineer, with a verification note, can turn 'suspected' into 'confirmed'."""
        if actor.role != ActorRole.ENGINEER:
            raise ActionError("only a human engineer may confirm a root cause")
        if not verification_note.strip():
            raise ActionError("a verification note is required to confirm a root cause")
        self.root_cause_status = RootCauseStatus.CONFIRMED
        self.confirmed_root_cause = category
        self.confirmed_root_cause_note = verification_note
        self.confirmed_by = actor.name
        self.touch()

    @property
    def primary_events(self) -> list[NormalizedEvent]:
        if not self.correlation:
            return []
        wanted = set(self.correlation.primary_event_ids)
        return [e for e in self.events if e.event_id in wanted]
