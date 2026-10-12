import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.models.enums import DeviceType, EventStatus, EventType, Severity
from app.models.network import NormalizedEvent, Topology

class IntakeAgent:
    """Agent 1 - Network Telemetry & Alarm Intake Agent
    Collects, normalizes, and validates network operational data.
    """
    def __init__(self, topology: Topology):
        self.topology = topology
        self.ip_to_device = {d.ip_address: d.name for d in topology.devices}
        self.device_to_type = {d.name: d.device_type for d in topology.devices}

    def process_event(self, raw_event: dict[str, Any]) -> NormalizedEvent:
        event_id = raw_event.get("id") or raw_event.get("event_id")
        if not event_id:
            raise ValueError("Event must have an ID")
            
        fmt = raw_event.get("format", "simulated")
        payload = raw_event.get("payload", raw_event)
        
        flags: List[str] = []
        
        if fmt == "syslog":
            m = re.search(r'<(\d+)>(.+?)\s+([A-Z0-9-]+)\s+%(.+?):\s+(.+)', payload)
            if m:
                timestamp_str = m.group(2)
                timestamp_str = re.sub(r'\s+', ' ', timestamp_str)
                device = m.group(3)
                msg = m.group(5)
                
                try:
                    # Assuming the year is 2026 for the assignment context
                    ts = datetime.strptime(f"2026 {timestamp_str}", "%Y %b %d %H:%M:%S")
                except ValueError:
                    flags.append("invalid_timestamp")
                    ts = datetime.now()
                
                event_type = EventType.OTHER
                severity = Severity.INFO
                interface = None
                
                if "changed state to down" in msg:
                    event_type = EventType.INTERFACE_DOWN
                    severity = Severity.CRITICAL
                    intf_m = re.search(r'Interface\s+([^,]+)', msg)
                    if intf_m:
                        interface = intf_m.group(1)
                
                return NormalizedEvent(
                    event_id=event_id,
                    timestamp=ts,
                    device=device,
                    device_type=self.device_to_type.get(device),
                    event_type=event_type,
                    interface=interface,
                    severity=severity,
                    description=payload,
                    source_format=fmt,
                    raw=payload,
                    validation_flags=flags
                )
            else:
                flags.append("unparseable_syslog")
                return NormalizedEvent(
                    event_id=event_id,
                    timestamp=datetime.now(),
                    device="UNKNOWN",
                    event_type=EventType.OTHER,
                    severity=Severity.INFO,
                    source_format=fmt,
                    raw=payload,
                    validation_flags=flags
                )
                
        elif fmt == "snmp_trap":
            device = "UNKNOWN"
            if "agent_addr" in payload:
                device = self.ip_to_device.get(payload["agent_addr"], "UNKNOWN")
            elif "hostname" in payload:
                device = payload["hostname"]
                
            if device == "UNKNOWN":
                flags.append("missing_device_identity")
                
            ts = datetime.now()
            if "received_at" in payload:
                try:
                    ts = datetime.strptime(payload["received_at"], "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    flags.append("invalid_timestamp")
                    
            event_type = EventType.OTHER
            severity = Severity.INFO
            interface = payload.get("ifDescr")
            
            if payload.get("trap") == "linkDown":
                event_type = EventType.INTERFACE_DOWN
                severity = Severity.CRITICAL
                
            return NormalizedEvent(
                event_id=event_id,
                timestamp=ts,
                device=device,
                device_type=self.device_to_type.get(device),
                event_type=event_type,
                interface=interface,
                severity=severity,
                description=str(payload),
                source_format=fmt,
                raw=payload,
                validation_flags=flags
            )
            
        elif fmt == "vendor_json":
            device = payload.get("nodeName", "UNKNOWN")
            
            ts = datetime.now()
            if "eventTime" in payload:
                try:
                    ts = datetime.fromtimestamp(int(payload["eventTime"]), tz=timezone.utc).replace(tzinfo=None)
                except (ValueError, TypeError):
                    flags.append("invalid_timestamp")
                    
            event_type = EventType.OTHER
            severity = Severity.INFO
            
            if payload.get("alarmName") == "BackhaulLoss":
                event_type = EventType.BACKHAUL_CONNECTIVITY_LOST
            
            try:
                severity = Severity(payload.get("perceivedSeverity", "").lower())
            except ValueError:
                pass
                
            return NormalizedEvent(
                event_id=event_id,
                timestamp=ts,
                device=device,
                device_type=self.device_to_type.get(device),
                event_type=event_type,
                severity=severity,
                description=payload.get("probableCause", ""),
                source_format=fmt,
                raw=payload,
                validation_flags=flags
            )
            
        elif fmt == "simulated":
            return NormalizedEvent.from_alarm_dict(payload, device_type=self.device_to_type.get(payload.get("device")))
            
        else:
            flags.append("unknown_format")
            return NormalizedEvent(
                event_id=event_id,
                timestamp=datetime.now(),
                device="UNKNOWN",
                event_type=EventType.OTHER,
                severity=Severity.INFO,
                source_format=fmt,
                raw=payload,
                validation_flags=flags
            )

    def process_events(self, raw_events: list[dict[str, Any]]) -> list[NormalizedEvent]:
        """Process a batch of raw events into NormalizedEvent objects."""
        return [self.process_event(raw) for raw in raw_events]
