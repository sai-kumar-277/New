# SOP-001: Interface Down / Link Failure Troubleshooting

**Document ID:** SOP-001 | **Version:** 2.1 | **Status:** Approved
**Applies to alarms:** interface_down, link_down, link_flap, interface_errors_high
**Applies to devices:** core_router, aggregation_router, transit_gateway

## 1. Scope
Use when a router interface reports operational state down, or a link is lost between two managed devices.

## 2. Initial Assessment
- [DIAGNOSTIC] Confirm the alarm is current: verify interface oper-state on the device and on the far end.
- [DIAGNOSTIC] Check whether the far-end device raised a matching alarm (same link, two sides = one fault).
- [DIAGNOSTIC] Check whether downstream devices raised backhaul or service alarms (indicates impact scope).

## 3. Diagnostic Steps
1. [DIAGNOSTIC] Review interface error counters (CRC, input errors, drops) for the 15 minutes before the event. Rising errors before the outage suggest a degrading physical link.
2. [DIAGNOSTIC] Check optical receive/transmit power if available in monitoring.
3. [DIAGNOSTIC] Review configuration change history for the last 24 hours on both ends.
4. [DIAGNOSTIC] Review maintenance calendar for planned work on this link or site.
5. [DIAGNOSTIC] Verify upstream connectivity and routing adjacency state.
6. [DIAGNOSTIC] Check device uptime and recent restart events.

## 4. Restoration Actions
- [NON-DISRUPTIVE] Re-check status after 2 minutes to rule out a transient flap.
- [DISRUPTIVE - APPROVAL REQUIRED] Administrative disable/enable (bounce) of the interface.
- [DISRUPTIVE - APPROVAL REQUIRED] Move traffic to a spare or redundant port or path.
- [DISRUPTIVE - APPROVAL REQUIRED] Roll back a configuration change that correlates with the outage.

## 5. Escalation
- [ESCALATE] Raise a field/network-engineering ticket if optical power is absent, errors preceded the outage, or the far end also shows loss of signal (suspected physical failure).
- [ESCALATE] Escalate to the transmission team if multiple links on one route fail together.

## 6. Verification
Interface oper-state up, alarms cleared, error counters stable, downstream services restored. See SOP-006.
