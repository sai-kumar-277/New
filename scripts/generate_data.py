#!/usr/bin/env python3
"""Generate the synthetic telecom datasets used by the NOC fault-diagnosis system.

Reproducible: fixed seed. Run from anywhere:  python scripts/generate_data.py

Outputs (under data/):
  topology.json                         network inventory, links, services
  alarms/scenario_*.json                alarm scenarios + expected outcomes (test cases)
  telemetry/telemetry_train_normal.csv  24h of normal operation (model training)
  telemetry/telemetry_eval.csv          08:00-12:00 with injected faults (model evaluation / demo)
"""
import csv
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SEED = 42
rng = np.random.default_rng(SEED)
random.seed(SEED)

DAY = "2026-10-03"          # incident day (matches the example in the assignment)
TRAIN_DAY = "2026-10-02"    # normal-operation day for model training


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n")


# --------------------------------------------------------------------------- #
# 1. Topology / inventory
# --------------------------------------------------------------------------- #
def itf(name, desc, peer=None, role="access"):
    return {"name": name, "description": desc, "peer_device": peer, "role": role,
            "admin_status": "up", "oper_status": "up"}


def dev(device_id, dtype, region, ip, vendor, model, interfaces, services=None):
    return {
        "device_id": device_id, "name": device_id, "device_type": dtype, "region": region,
        "ip_address": ip, "vendor": vendor, "model": model, "operational_status": "operational",
        "interfaces": interfaces,
        "connected_devices": sorted({i["peer_device"] for i in interfaces if i["peer_device"]}),
        "supported_services": services or [],
    }


def link(lid, a, a_if, b, b_if, cap, group=None):
    return {"link_id": lid, "endpoint_a": {"device": a, "interface": a_if},
            "endpoint_b": {"device": b, "interface": b_if}, "link_type": "fiber",
            "capacity_mbps": cap, "status": "up", "redundancy_group": group}


def svc(sid, name, stype, endpoint, region, priority, redundancy, notes=""):
    # customer_count is deliberately null: the system must NOT invent customer counts.
    return {"service_id": sid, "name": name, "service_type": stype, "endpoint_device": endpoint,
            "region": region, "priority": priority, "redundancy": redundancy,
            "customer_count": None, "customer_data_available": False, "notes": notes}


def build_topology():
    devices = [
        dev("GW-01", "transit_gateway", "core", "10.0.0.1", "Cisco", "ASR 1002-X", [
            itf("GE-0/0/0", "Link to CR-01", "CR-01", "downlink"),
            itf("TE-0/1/0", "Upstream transit provider", None, "external")]),
        dev("CR-01", "core_router", "core", "10.0.1.1", "Juniper", "MX480", [
            itf("GE-0/0/0", "Uplink to GW-01", "GW-01", "uplink"),
            itf("GE-0/0/1", "Downlink to AR-01", "AR-01", "downlink"),
            itf("GE-0/0/2", "Downlink to AR-02 (link A)", "AR-02", "downlink"),
            itf("GE-0/0/3", "Downlink to AR-02 (link B)", "AR-02", "downlink")]),
        dev("AR-01", "aggregation_router", "region-A", "10.0.2.1", "Cisco", "ASR 9001", [
            itf("GE-0/0/1", "Uplink to CR-01", "CR-01", "uplink"),
            itf("GE-0/0/2", "Access to BS-101", "BS-101"),
            itf("GE-0/0/3", "Access to BS-102", "BS-102"),
            itf("GE-0/0/4", "Access to BS-103", "BS-103"),
            itf("GE-0/0/5", "Access to enterprise link E-101", "E-101")],
            ["SVC-BS-101", "SVC-BS-102", "SVC-BS-103", "SVC-E-101"]),
        dev("AR-02", "aggregation_router", "region-B", "10.0.3.1", "Huawei", "ATN 910C", [
            itf("GE-0/0/1", "Uplink A to CR-01", "CR-01", "uplink"),
            itf("GE-0/0/2", "Uplink B to CR-01", "CR-01", "uplink"),
            itf("GE-0/0/3", "Access to BS-201", "BS-201"),
            itf("GE-0/0/4", "Access to BS-202", "BS-202"),
            itf("GE-0/0/5", "Access to BS-203", "BS-203")],
            ["SVC-BS-201", "SVC-BS-202", "SVC-BS-203"]),
    ]
    for n, ar, region, vendor, model in [
        (101, "AR-01", "region-A", "Ericsson", "Baseband 6630"),
        (102, "AR-01", "region-A", "Ericsson", "Baseband 6630"),
        (103, "AR-01", "region-A", "Ericsson", "Baseband 6630"),
        (201, "AR-02", "region-B", "Nokia", "AirScale"),
        (202, "AR-02", "region-B", "Nokia", "AirScale"),
        (203, "AR-02", "region-B", "Nokia", "AirScale"),
    ]:
        devices.append(dev(f"BS-{n}", "base_station", region, f"10.1.{1 if n < 200 else 2}.{n % 100}",
                           vendor, model, [itf("BH-0", f"Backhaul to {ar}", ar, "uplink")],
                           [f"SVC-BS-{n}"]))
    devices.append(dev("E-101", "enterprise_link", "region-A", "10.2.1.101", "Ciena", "3926",
                       [itf("WAN-0", "Enterprise WAN handoff to AR-01", "AR-01", "uplink")], ["SVC-E-101"]))

    links = [
        link("LNK-GW01-CR01", "GW-01", "GE-0/0/0", "CR-01", "GE-0/0/0", 40000),
        link("LNK-CR01-AR01", "CR-01", "GE-0/0/1", "AR-01", "GE-0/0/1", 10000),
        link("LNK-CR01-AR02-A", "CR-01", "GE-0/0/2", "AR-02", "GE-0/0/1", 10000, "RG-AR02-UPLINK"),
        link("LNK-CR01-AR02-B", "CR-01", "GE-0/0/3", "AR-02", "GE-0/0/2", 10000, "RG-AR02-UPLINK"),
        link("LNK-AR01-BS101", "AR-01", "GE-0/0/2", "BS-101", "BH-0", 1000),
        link("LNK-AR01-BS102", "AR-01", "GE-0/0/3", "BS-102", "BH-0", 1000),
        link("LNK-AR01-BS103", "AR-01", "GE-0/0/4", "BS-103", "BH-0", 1000),
        link("LNK-AR01-E101", "AR-01", "GE-0/0/5", "E-101", "WAN-0", 1000),
        link("LNK-AR02-BS201", "AR-02", "GE-0/0/3", "BS-201", "BH-0", 1000),
        link("LNK-AR02-BS202", "AR-02", "GE-0/0/4", "BS-202", "BH-0", 1000),
        link("LNK-AR02-BS203", "AR-02", "GE-0/0/5", "BS-203", "BH-0", 1000),
    ]

    services = [svc(f"SVC-BS-{n}", f"Mobile backhaul connectivity BS-{n}", "mobile_backhaul", f"BS-{n}",
                    "region-A" if n < 200 else "region-B", "high",
                    "none" if n < 200 else "aggregation_uplink_dual_homed",
                    "Single path to core via AR-01" if n < 200 else "AR-02 has two uplinks to CR-01")
                for n in (101, 102, 103, 201, 202, 203)]
    services.append(svc("SVC-E-101", "Enterprise Link E-101", "enterprise_vpn", "E-101", "region-A", "gold",
                        "none", "Enterprise SLA service; no subscriber/customer count available"))

    return {"network_name": "Demo Telecom Network", "version": "1.0",
            "notes": "Synthetic topology. AR-01 is single-homed to CR-01; AR-02 is dual-homed (RG-AR02-UPLINK).",
            "devices": devices, "links": links, "services": services}


# --------------------------------------------------------------------------- #
# 2. Alarm scenarios
# --------------------------------------------------------------------------- #
def mk(eid, tstr, device, atype, sev, comp, desc):
    return {"event_id": f"EVT-{eid}", "timestamp": f"{DAY}T{tstr}", "device": device, "alarm_type": atype,
            "severity": sev, "interface": comp, "description": desc, "status": "active"}


def scenario_single():  # TC-01
    return {
        "scenario_id": "SC-SINGLE", "test_cases": ["TC-01"],
        "description": "Single AR-02 uplink goes down; the redundant uplink B stays up.",
        "expected": {"incident_count": 1, "suspected_fault_location": "AR-02 GE-0/0/1 / LNK-CR01-AR02-A",
                     "service_impact": "none or degraded (redundant uplink available)",
                     "note": "The CR-01 far-end alarm should be recognised as the same fault, not a second incident."},
        "alarms": [
            mk(10300, "09:30:12", "AR-02", "interface_down", "critical", "GE-0/0/1",
               "Interface GE-0/0/1 (uplink A to CR-01) changed state to down"),
            mk(10301, "09:30:12", "CR-01", "interface_down", "major", "GE-0/0/2",
               "Interface GE-0/0/2 (downlink to AR-02) changed state to down"),
        ]}


def scenario_cascade():  # TC-02, TC-05, TC-06 (the exact example from the assignment)
    return {
        "scenario_id": "SC-CASCADE", "test_cases": ["TC-02", "TC-05", "TC-06"],
        "description": "The AR-01 example from the assignment: interface down followed by downstream losses.",
        "expected": {
            "incident_count": 1, "incident_id_example": "INC-NET-101",
            "primary_event": "EVT-10425",
            "consequential_events": ["EVT-10426", "EVT-10427", "EVT-10428", "EVT-10429"],
            "suspected_fault_location": "AR-01 uplink/interface (GE-0/0/1 / LNK-CR01-AR01)",
            "affected_elements": ["BS-101", "BS-102"], "confidence": "high",
            "topology_note": ("BS-103 and E-101 also depend on AR-01 but raised no alarm. The system should "
                              "flag them as 'potentially affected, unconfirmed' rather than ignore or assert them."),
            "healthy_comparison": "BS-201..203 (via AR-02) are unaffected, which supports AR-01 as the fault domain.",
            "historical_match": "INC-NET-032 (fiber uplink failure, three downstream sites)"},
        "alarms": [
            mk(10425, "10:02:01", "AR-01", "interface_down", "critical", "GE-0/0/1",
               "Interface GE-0/0/1 (uplink to CR-01) changed state to down"),
            mk(10426, "10:02:04", "BS-101", "backhaul_connectivity_lost", "critical", "BH-0",
               "Backhaul connectivity lost"),
            mk(10427, "10:02:05", "BS-102", "backhaul_connectivity_lost", "critical", "BH-0",
               "Backhaul connectivity lost"),
            mk(10428, "10:02:07", "BS-101", "service_unavailable", "critical", "CELL-0",
               "Cell service unavailable"),
            mk(10429, "10:02:08", "BS-102", "service_unavailable", "critical", "CELL-0",
               "Cell service unavailable"),
        ]}


def scenario_dynamic():  # TC-08
    return {
        "scenario_id": "SC-DYNAMIC", "test_cases": ["TC-08"],
        "description": "Replay after SC-CASCADE while the incident is active: one related and one unrelated alarm.",
        "active_incident_from": "SC-CASCADE",
        "expected": {
            "EVT-10430": "belongs to the existing incident (BS-103 depends on AR-01): update impact, "
                         "recompute hypotheses, notify the engineer of the material change",
            "EVT-10431": "independent (AR-02 CPU is not on the AR-01 failure path): separate or no incident"},
        "alarms": [
            mk(10430, "10:09:40", "BS-103", "backhaul_connectivity_lost", "critical", "BH-0",
               "Backhaul connectivity lost"),
            mk(10431, "10:10:15", "AR-02", "cpu_high", "warning", "CPU",
               "CPU utilisation 86% exceeds threshold 80%"),
        ]}


def scenario_congestion():  # TC-04 (pairs with the telemetry in telemetry_eval.csv at 10:50)
    return {
        "scenario_id": "SC-CONGESTION", "test_cases": ["TC-04", "TC-05"],
        "description": ("AR-02 uplink A fails at 10:50; traffic shifts to uplink B, which saturates "
                        "(latency 180 ms, loss 8.5%, utilisation 96%, jitter 42 ms in telemetry_eval.csv)."),
        "expected": {
            "root_cause_hypothesis": "traffic shift from failed link A causing congestion on link B",
            "must_not_conclude": "high utilisation alone is the root cause without the link-A failure evidence",
            "anomaly_entity": "LNK-CR01-AR02-B"},
        "alarms": [
            mk(10500, "10:50:03", "AR-02", "interface_down", "critical", "GE-0/0/1",
               "Interface GE-0/0/1 (uplink A to CR-01) changed state to down"),
            mk(10501, "10:50:03", "CR-01", "interface_down", "major", "GE-0/0/2",
               "Interface GE-0/0/2 (downlink to AR-02) changed state to down"),
            mk(10502, "10:51:10", "CR-01", "utilization_high", "warning", "GE-0/0/3",
               "Interface GE-0/0/3 utilisation 96% exceeds threshold 85%"),
            mk(10503, "10:51:40", "AR-02", "packet_loss_high", "major", "GE-0/0/2",
               "Packet loss 8.5% exceeds threshold 2%"),
        ]}


def scenario_storm():  # TC-03
    flat = []  # (offset_s, device, type, sev, comp, desc)
    flat += [(0, "AR-02", "interface_down", "critical", "GE-0/0/1", "Interface GE-0/0/1 changed state to down"),
             (0, "AR-02", "interface_down", "critical", "GE-0/0/2", "Interface GE-0/0/2 changed state to down"),
             (1, "CR-01", "interface_down", "major", "GE-0/0/2", "Interface GE-0/0/2 changed state to down"),
             (1, "CR-01", "interface_down", "major", "GE-0/0/3", "Interface GE-0/0/3 changed state to down")]
    for k, bs in enumerate(("BS-201", "BS-202", "BS-203")):
        flat.append((3 + k, bs, "backhaul_connectivity_lost", "critical", "BH-0", "Backhaul connectivity lost"))
        flat.append((5 + k, bs, "service_unavailable", "critical", "CELL-0", "Cell service unavailable"))
    # independent alarms that must NOT be merged into the storm incident
    flat.append((20, "BS-101", "high_temperature", "warning", "CHASSIS", "Cabinet temperature 58C exceeds 55C"))
    flat.append((47, "AR-01", "fan_speed_low", "minor", "FAN-2", "Fan 2 speed below threshold"))
    # repeated notifications (duplicates / flapping) to build the storm up to 300 alarms
    while len(flat) < 300:
        off = int(rng.integers(6, 90))
        r = rng.random()
        if r < 0.8:
            bs = random.choice(("BS-201", "BS-202", "BS-203"))
            if rng.random() < 0.5:
                flat.append((off, bs, "backhaul_connectivity_lost", "critical", "BH-0", "Backhaul connectivity lost"))
            else:
                flat.append((off, bs, "service_unavailable", "critical", "CELL-0", "Cell service unavailable"))
        elif r < 0.9:
            p = random.choice(("GE-0/0/1", "GE-0/0/2"))
            flat.append((off, "AR-02", "interface_down", "critical", p, f"Interface {p} changed state to down"))
        else:
            p = random.choice(("GE-0/0/2", "GE-0/0/3"))
            flat.append((off, "CR-01", "interface_down", "major", p, f"Interface {p} changed state to down"))
    flat.sort(key=lambda x: (x[0], x[1], x[2]))
    base = datetime.fromisoformat(f"{DAY}T14:15:00")
    alarms = []
    for i, (off, d, t, s, c, desc) in enumerate(flat):
        alarms.append({"event_id": f"EVT-{20001 + i}",
                       "timestamp": (base + timedelta(seconds=off)).isoformat(timespec="seconds"),
                       "device": d, "alarm_type": t, "severity": s, "interface": c,
                       "description": desc, "status": "active"})
    return {
        "scenario_id": "SC-STORM", "test_cases": ["TC-03"],
        "description": "AR-02 loses both uplinks at 14:15:00; 300 alarms in 90 s including repeats, plus 2 unrelated alarms.",
        "expected": {
            "total_alarms": len(alarms), "expected_incident_clusters": 3,
            "clusters": [
                {"name": "AR-02 dual-uplink loss (storm)", "primary_device": "AR-02",
                 "includes": "CR-01 far-end alarms, BS-201..203 consequences, all duplicates",
                 "affected_elements": ["BS-201", "BS-202", "BS-203"], "redundancy": "none left (both uplinks down)"},
                {"name": "independent", "event": "BS-101 high_temperature"},
                {"name": "independent", "event": "AR-01 fan_speed_low"}],
            "requirement": "Original alarms stay retrievable for audit; the incident view is de-duplicated."},
        "alarms": alarms}


def vendor_raw():  # Agent 1 normalisation / validation tests
    return {
        "scenario_id": "SC-VENDOR-RAW", "test_cases": ["TC-01"],
        "description": "Heterogeneous raw events for the intake agent: normalise, validate, de-duplicate.",
        "raw_events": [
            {"id": "RAW-1", "format": "syslog",
             "payload": "<187>Oct  3 10:02:01 AR-01 %LINK-3-UPDOWN: Interface GE-0/0/1, changed state to down"},
            {"id": "RAW-2", "format": "snmp_trap",
             "payload": {"trap": "linkDown", "agent_addr": "10.0.2.1", "ifDescr": "GE-0/0/1", "ifOperStatus": 2,
                         "received_at": "2026-10-03 10:02:02"}},
            {"id": "RAW-3", "format": "vendor_json",
             "payload": {"nodeName": "BS-101", "alarmName": "BackhaulLoss", "perceivedSeverity": "CRITICAL",
                         "eventTime": 1791021724, "probableCause": "Backhaul connectivity lost"}},
            {"id": "RAW-4", "format": "vendor_json",
             "payload": {"nodeName": "BS-102", "alarmName": "BackhaulLoss", "perceivedSeverity": "CRITICAL",
                         "eventTime": "not-a-timestamp"}},
            {"id": "RAW-5", "format": "syslog",
             "payload": "<187>Oct  3 10:02:01 AR-01 %LINK-3-UPDOWN: Interface GE-0/0/1, changed state to down"},
            {"id": "RAW-6", "format": "snmp_trap",
             "payload": {"trap": "linkDown", "ifDescr": "GE-0/0/9", "ifOperStatus": 2,
                         "received_at": "2026-10-03 10:03:00"}},
        ],
        "expected": {
            "RAW-1": "normalised: AR-01 interface_down GE-0/0/1 critical",
            "RAW-2": "same underlying event as RAW-1 (device resolved from IP 10.0.2.1); de-duplicate within window",
            "RAW-3": "normalised: BS-101 backhaul_connectivity_lost critical (epoch converted to ISO)",
            "RAW-4": "rejected/flagged: invalid timestamp",
            "RAW-5": "exact duplicate of RAW-1",
            "RAW-6": "flagged: missing device identity (no agent_addr/hostname) and unknown interface"}}


# --------------------------------------------------------------------------- #
# 3. Telemetry
# --------------------------------------------------------------------------- #
CAP = 10000
LINKS = {"LNK-CR01-AR01": 55.0, "LNK-CR01-AR02-A": 48.0, "LNK-CR01-AR02-B": 48.0}
DEVICES = {"CR-01": (22.0, 58.0), "AR-01": (30.0, 52.0), "AR-02": (28.0, 50.0)}
COLS = ["timestamp", "entity_id", "entity_type", "latency_ms", "packet_loss_pct", "jitter_ms",
        "throughput_mbps", "utilization_pct", "cpu_pct", "memory_pct", "interface_errors",
        "link_available", "scenario_label", "is_anomaly"]


def clip(x, lo, hi):
    return max(lo, min(hi, x))


def diurnal(t):
    m = t.hour * 60 + t.minute
    return 1 + 0.12 * np.sin(2 * np.pi * (m - 480) / 1440)


def link_row(t, lid, base):
    util = clip(base * diurnal(t) + rng.normal(0, 1.8), 5, 99)
    return {"timestamp": t.isoformat(timespec="seconds"), "entity_id": lid, "entity_type": "link",
            "latency_ms": round(max(5, 25 + 0.05 * (util - base) + rng.normal(0, 2.5)), 1),
            "packet_loss_pct": round(abs(rng.normal(0.3, 0.08)), 2),
            "jitter_ms": round(max(1, 8 + rng.normal(0, 1.2)), 1),
            "throughput_mbps": round(util / 100 * CAP, 1), "utilization_pct": round(util, 1),
            "cpu_pct": None, "memory_pct": None, "interface_errors": int(rng.poisson(0.3)),
            "link_available": 1, "scenario_label": "normal", "is_anomaly": 0}


def device_row(t, did, cpu_base, mem_base):
    return {"timestamp": t.isoformat(timespec="seconds"), "entity_id": did, "entity_type": "device",
            "latency_ms": None, "packet_loss_pct": None, "jitter_ms": None, "throughput_mbps": None,
            "utilization_pct": None,
            "cpu_pct": round(clip(cpu_base * diurnal(t) + rng.normal(0, 2), 2, 99), 1),
            "memory_pct": round(clip(mem_base + rng.normal(0, 0.6), 5, 99), 1),
            "interface_errors": None, "link_available": None, "scenario_label": "normal", "is_anomaly": 0}


def mm(t):
    return t.hour * 60 + t.minute


def between(t, s, e):
    return s[0] * 60 + s[1] <= mm(t) <= e[0] * 60 + e[1]


def lerp(a, b, r):
    return a + (b - a) * r


def set_down(row, label):
    row.update(latency_ms=None, jitter_ms=None, packet_loss_pct=100.0, throughput_mbps=0.0,
               utilization_pct=0.0, interface_errors=0, link_available=0, scenario_label=label, is_anomaly=1)


def set_recovery(row, loss):
    row.update(packet_loss_pct=loss, scenario_label="recovery", is_anomaly=1)


def inject(row, t):
    eid = row["entity_id"]
    if eid == "LNK-CR01-AR01":
        if between(t, (10, 0), (10, 1)):      # precursor: CRC/interface errors before the outage
            row.update(interface_errors=int(rng.integers(25, 60)),
                       packet_loss_pct=round(float(rng.uniform(1.5, 3.0)), 2),
                       scenario_label="precursor_errors", is_anomaly=1)
        elif between(t, (10, 2), (10, 34)):    # uplink down (matches the 10:02:01 alarm)
            set_down(row, "link_down")
        elif mm(t) == 10 * 60 + 35:
            set_recovery(row, 3.1)
        elif mm(t) == 10 * 60 + 36:
            set_recovery(row, 1.2)
    elif eid == "LNK-CR01-AR02-A":
        if between(t, (10, 50), (11, 29)):
            set_down(row, "link_down")
        elif mm(t) == 11 * 60 + 30:
            set_recovery(row, 2.4)
        elif mm(t) == 11 * 60 + 31:
            set_recovery(row, 0.9)
    elif eid == "LNK-CR01-AR02-B":
        if between(t, (10, 50), (11, 29)):     # traffic shift -> congestion (assignment's example numbers)
            r = min(1.0, (mm(t) - (10 * 60 + 50) + 1) / 3)
            util = round(lerp(row["utilization_pct"], clip(rng.normal(96, 1.0), 90, 99), r), 1)
            row.update(utilization_pct=util, throughput_mbps=round(util / 100 * CAP, 1),
                       latency_ms=round(lerp(row["latency_ms"], rng.normal(180, 10), r), 1),
                       packet_loss_pct=round(lerp(row["packet_loss_pct"], rng.normal(8.5, 0.5), r), 2),
                       jitter_ms=round(lerp(row["jitter_ms"], rng.normal(42, 3), r), 1),
                       interface_errors=int(rng.poisson(6 * r)),
                       scenario_label="congestion_traffic_shift", is_anomaly=1)
        elif between(t, (11, 30), (11, 34)):   # post-restoration: loss ~0.4% (assignment example)
            row.update(packet_loss_pct=round(float(rng.normal(0.4, 0.05)), 2), scenario_label="post_restoration")
    elif eid == "CR-01":                       # slow memory growth from 09:00 (gradual degradation)
        k = mm(t) - 9 * 60
        if k > 0:
            row["memory_pct"] = round(row["memory_pct"] + k * (24 / 180), 1)
            row["cpu_pct"] = round(row["cpu_pct"] + 0.02 * k, 1)
            if row["memory_pct"] - 58 >= 3.0:
                row.update(scenario_label="gradual_memory_growth", is_anomaly=1)
    elif eid == "AR-02":                       # stuck sensor: flat 100% / 0% with no matching effects
        if between(t, (11, 40), (11, 50)):
            row.update(cpu_pct=100.0, memory_pct=0.0, scenario_label="sensor_fault", is_anomaly=1)


def gen_telemetry(day, start_min, end_min, with_faults):
    start = datetime.fromisoformat(f"{day}T00:00:00") + timedelta(minutes=start_min)
    rows = []
    for i in range(end_min - start_min):
        t = start + timedelta(minutes=i)
        batch = [link_row(t, lid, b) for lid, b in LINKS.items()]
        batch += [device_row(t, did, c, m) for did, (c, m) in DEVICES.items()]
        if with_faults:
            for r in batch:
                inject(r, t)
        rows += batch
    return rows


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)


# --------------------------------------------------------------------------- #
def main():
    write_json(DATA / "topology.json", build_topology())
    for fn, fac in [("scenario_single", scenario_single), ("scenario_cascade", scenario_cascade),
                    ("scenario_dynamic", scenario_dynamic), ("scenario_congestion", scenario_congestion),
                    ("scenario_storm", scenario_storm), ("scenario_vendor_raw", vendor_raw)]:
        write_json(DATA / "alarms" / f"{fn}.json", fac())
    train = gen_telemetry(TRAIN_DAY, 0, 1440, with_faults=False)
    evald = gen_telemetry(DAY, 8 * 60, 12 * 60, with_faults=True)
    write_csv(DATA / "telemetry" / "telemetry_train_normal.csv", train)
    write_csv(DATA / "telemetry" / "telemetry_eval.csv", evald)
    n_anom = sum(r["is_anomaly"] for r in evald)
    print(f"topology.json, 6 alarm scenarios written")
    print(f"train rows: {len(train)} (all normal)")
    print(f"eval rows: {len(evald)}, anomalous: {n_anom} ({100 * n_anom / len(evald):.1f}%)")


if __name__ == "__main__":
    main()
