"""Normalised events, network inventory/topology, and historical-incident records."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import (DeviceType, EventStatus, EventType, RootCauseCategory, Severity)


# --------------------------------------------------------------------------- #
# Events
# --------------------------------------------------------------------------- #
class NormalizedEvent(BaseModel):
    """One alarm after vendor normalisation (Agent 1 output).

    frozen=True: original alarms are audit evidence and must never be edited after intake.
    Duplicate/primary/consequential labelling lives in the correlation result, not here.
    """
    model_config = ConfigDict(frozen=True)

    event_id: str
    timestamp: datetime
    device: str
    device_type: Optional[DeviceType] = None
    event_type: EventType
    interface: Optional[str] = None      # interface or component (e.g. "GE-0/0/1", "FAN-2")
    severity: Severity
    description: str = ""
    status: EventStatus = EventStatus.ACTIVE
    source_format: str = "simulated"     # syslog | snmp_trap | vendor_json | simulated
    raw: Optional[Union[dict[str, Any], str]] = None
    validation_flags: list[str] = Field(default_factory=list)  # e.g. "unknown_event_type:foo"

    @classmethod
    def from_alarm_dict(cls, d: dict[str, Any], device_type: Optional[DeviceType] = None) -> "NormalizedEvent":
        """Build from the simulated alarm format used in data/alarms/*.json."""
        flags: list[str] = []
        try:
            etype = EventType(d["alarm_type"])
        except ValueError:
            etype = EventType.OTHER
            flags.append(f"unknown_event_type:{d['alarm_type']}")
        return cls(event_id=d["event_id"], timestamp=d["timestamp"], device=d["device"],
                   device_type=device_type, event_type=etype, interface=d.get("interface"),
                   severity=d["severity"], description=d.get("description", ""),
                   status=d.get("status", "active"), validation_flags=flags)


# --------------------------------------------------------------------------- #
# Inventory / topology
# --------------------------------------------------------------------------- #
class Interface(BaseModel):
    name: str
    description: str = ""
    peer_device: Optional[str] = None
    role: str = "access"
    admin_status: str = "up"
    oper_status: str = "up"


class Device(BaseModel):
    device_id: str
    name: str
    device_type: DeviceType
    region: str
    ip_address: str
    vendor: str
    model: str
    operational_status: str = "operational"
    interfaces: list[Interface] = Field(default_factory=list)
    connected_devices: list[str] = Field(default_factory=list)
    supported_services: list[str] = Field(default_factory=list)


class LinkEndpoint(BaseModel):
    device: str
    interface: str


class Link(BaseModel):
    link_id: str
    endpoint_a: LinkEndpoint
    endpoint_b: LinkEndpoint
    link_type: str = "fiber"
    capacity_mbps: int = Field(gt=0)
    status: str = "up"
    redundancy_group: Optional[str] = None  # links sharing a group back each other up


class Service(BaseModel):
    service_id: str
    name: str
    service_type: str
    endpoint_device: str
    region: str
    priority: str = "normal"
    redundancy: str = "none"
    customer_count: Optional[int] = None       # None = unknown. Never estimate.
    customer_data_available: bool = False
    notes: str = ""

    @model_validator(mode="after")
    def _count_needs_data(self) -> "Service":
        if self.customer_count is not None and not self.customer_data_available:
            raise ValueError("customer_count set but customer_data_available is False")
        return self


class Topology(BaseModel):
    network_name: str
    version: str = "1.0"
    notes: str = ""
    devices: list[Device]
    links: list[Link]
    services: list[Service]

    @model_validator(mode="after")
    def _referential_integrity(self) -> "Topology":
        ids = {d.device_id for d in self.devices}
        if len(ids) != len(self.devices):
            raise ValueError("duplicate device_id in topology")
        svc_ids = {s.service_id for s in self.services}
        for link in self.links:
            for ep in (link.endpoint_a, link.endpoint_b):
                if ep.device not in ids:
                    raise ValueError(f"link {link.link_id} references unknown device {ep.device}")
        for s in self.services:
            if s.endpoint_device not in ids:
                raise ValueError(f"service {s.service_id} references unknown device {s.endpoint_device}")
        for d in self.devices:
            for peer in d.connected_devices:
                if peer not in ids:
                    raise ValueError(f"device {d.device_id} connected to unknown device {peer}")
            for sid in d.supported_services:
                if sid not in svc_ids:
                    raise ValueError(f"device {d.device_id} supports unknown service {sid}")
        return self

    def device(self, device_id: str) -> Device:
        for d in self.devices:
            if d.device_id == device_id:
                return d
        raise KeyError(device_id)

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> "Topology":
        return cls.model_validate(json.loads(Path(path).read_text()))


# --------------------------------------------------------------------------- #
# Knowledge base records
# --------------------------------------------------------------------------- #
class HistoricalIncidentRecord(BaseModel):
    incident_id: str
    title: str
    date: str
    root_cause_category: RootCauseCategory
    alarm_pattern: list[str]
    affected_devices: list[str]
    topology_pattern: str
    precursors: str
    confirmed_root_cause: str
    resolution: str
    time_to_restore_min: int
    applicable_sops: list[str] = Field(default_factory=list)


def load_historical_incidents(path: Union[str, Path]) -> list[HistoricalIncidentRecord]:
    data = json.loads(Path(path).read_text())
    return [HistoricalIncidentRecord.model_validate(i) for i in data["incidents"]]
