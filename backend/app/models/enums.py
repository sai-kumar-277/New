"""Controlled vocabularies used across the system.

Using enums (instead of free strings) means a typo like "critcal" fails validation at the
boundary instead of silently breaking correlation or reporting later.
"""
from enum import Enum


class Severity(str, Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    WARNING = "warning"
    INFO = "info"


class EventType(str, Enum):
    INTERFACE_DOWN = "interface_down"
    LINK_FLAP = "link_flap"
    INTERFACE_ERRORS_HIGH = "interface_errors_high"
    BACKHAUL_CONNECTIVITY_LOST = "backhaul_connectivity_lost"
    SERVICE_UNAVAILABLE = "service_unavailable"
    DEVICE_UNREACHABLE = "device_unreachable"
    PROCESS_RESTART = "process_restart"
    POWER_SUPPLY_FAILURE = "power_supply_failure"
    ROUTING_NEIGHBOR_DOWN = "routing_neighbor_down"
    UTILIZATION_HIGH = "utilization_high"
    PACKET_LOSS_HIGH = "packet_loss_high"
    LATENCY_HIGH = "latency_high"
    JITTER_HIGH = "jitter_high"
    CPU_HIGH = "cpu_high"
    MEMORY_HIGH = "memory_high"
    HIGH_TEMPERATURE = "high_temperature"
    FAN_SPEED_LOW = "fan_speed_low"
    OTHER = "other"  # unknown vendor alarm; the raw payload is kept and a validation flag is set


class EventStatus(str, Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    CLEARED = "cleared"


class EventRole(str, Enum):
    """Role of an alarm inside a correlated incident (Requirement 4)."""
    PRIMARY = "primary"
    CONSEQUENTIAL = "consequential"
    DUPLICATE = "duplicate"
    INDEPENDENT = "independent"


class DeviceType(str, Enum):
    TRANSIT_GATEWAY = "transit_gateway"
    CORE_ROUTER = "core_router"
    AGGREGATION_ROUTER = "aggregation_router"
    SWITCH = "switch"
    BASE_STATION = "base_station"
    ENTERPRISE_LINK = "enterprise_link"


class ServiceState(str, Enum):
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"
    POTENTIALLY_AFFECTED = "potentially_affected"  # depends on the fault but no alarm seen yet
    UNAFFECTED = "unaffected"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RootCauseCategory(str, Enum):
    PHYSICAL_LINK_FAILURE = "physical_link_failure"
    DEVICE_HARDWARE_FAILURE = "device_hardware_failure"
    INTERFACE_HARDWARE_FAILURE = "interface_hardware_failure"
    CONFIGURATION_ISSUE = "configuration_issue"
    ROUTING_ISSUE = "routing_issue"
    NETWORK_CONGESTION = "network_congestion"
    POWER_FAILURE = "power_failure"
    SOFTWARE_PROCESS_FAILURE = "software_process_failure"
    EXTERNAL_CONNECTIVITY_FAILURE = "external_connectivity_failure"
    TELEMETRY_SENSOR_ISSUE = "telemetry_sensor_issue"
    UNKNOWN = "unknown"


class RootCauseStatus(str, Enum):
    """Suspected vs confirmed (Requirement 12). Only an engineer can move to CONFIRMED."""
    UNDETERMINED = "undetermined"
    SUSPECTED = "suspected"
    CONFIRMED = "confirmed"


class EvidenceSource(str, Enum):
    ALARM = "alarm"
    TOPOLOGY = "topology"
    TELEMETRY = "telemetry"
    LOG = "log"
    CONFIG_HISTORY = "config_history"
    MAINTENANCE = "maintenance"
    HISTORICAL_INCIDENT = "historical_incident"
    SOP = "sop"


class ActionCategory(str, Enum):
    """Risk class of a restoration action (Requirement 13)."""
    DIAGNOSTIC = "diagnostic"
    NON_DISRUPTIVE = "non_disruptive"
    POTENTIALLY_DISRUPTIVE = "potentially_disruptive"
    ESCALATION_REQUIRED = "escalation_required"


class ActionStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    VERIFIED = "verified"


class IncidentStatus(str, Enum):
    NEW = "new"
    DIAGNOSING = "diagnosing"
    AWAITING_APPROVAL = "awaiting_approval"
    RESTORING = "restoring"
    VALIDATING = "validating"
    CLOSED = "closed"
    ESCALATED = "escalated"


class ActorRole(str, Enum):
    AGENT = "agent"
    ENGINEER = "engineer"
    SYSTEM = "system"


class DecisionType(str, Enum):
    CONFIRM_CORRELATION = "confirm_correlation"
    REJECT_CORRELATION = "reject_correlation"
    APPROVE_ACTION = "approve_action"
    REJECT_ACTION = "reject_action"
    MODIFY_ACTION = "modify_action"
    COMMENT = "comment"
    ESCALATE = "escalate"
    CONFIRM_ROOT_CAUSE = "confirm_root_cause"
    CLOSE_INCIDENT = "close_incident"


class AgentName(str, Enum):
    INTAKE = "intake"
    CORRELATION = "correlation"
    LOCALIZATION = "localization"
    ANOMALY = "anomaly"
    SERVICE_IMPACT = "service_impact"
    ROOT_CAUSE = "root_cause"
    RESTORATION = "restoration"
    REVIEWER = "reviewer"
