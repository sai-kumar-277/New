# SOP-002: Backhaul Connectivity Loss / Base Station Unavailable

**Document ID:** SOP-002 | **Version:** 1.8 | **Status:** Approved
**Applies to alarms:** backhaul_connectivity_lost, service_unavailable
**Applies to devices:** base_station, enterprise_link

## 1. Scope
Use when a base station or enterprise link reports loss of backhaul or service.

## 2. Initial Assessment
- [DIAGNOSTIC] Determine whether the alarm is local to one site or shared by several sites under the same aggregation router.
- [DIAGNOSTIC] Compare against sites behind a different aggregation router that remain healthy. Shared failure under one parent points to the parent or its uplink, not the individual sites.
- [DIAGNOSTIC] Check the parent aggregation router for interface alarms and its uplink status.

## 3. Diagnostic Steps
1. [DIAGNOSTIC] Identify all devices and services that depend on the suspected parent; list those with no alarm yet as "potentially affected, unconfirmed".
2. [DIAGNOSTIC] Check last-known telemetry from the affected sites for errors or degradation before the loss.
3. [DIAGNOSTIC] Check site power and environmental alarms.
4. [DIAGNOSTIC] Review recent configuration and maintenance activity on the parent.

## 4. Restoration Actions
- [NON-DISRUPTIVE] Follow the parent-device procedure (SOP-001 for interface faults, SOP-004 for device faults).
- [ESCALATE] If a single site is affected and the parent is healthy, dispatch field engineering to the site.

## 5. Notes
Do not state customer counts unless real subscriber data is available for the sites.

## 6. Verification
Backhaul restored, cell/service state up, alarms cleared. See SOP-006.
