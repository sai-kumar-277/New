# SOP-004: Device Failure, Unexpected Restart and Power Events

**Document ID:** SOP-004 | **Version:** 1.6 | **Status:** Approved
**Applies to alarms:** device_unreachable, process_restart, power_supply_failure, cpu_high, memory_high
**Applies to devices:** all router and base station types

## 1. Scope
Use when a device becomes unreachable, restarts, shows power faults, or shows sustained CPU/memory growth.

## 2. Diagnostic Steps
1. [DIAGNOSTIC] Check uptime to detect an unexpected restart.
2. [DIAGNOSTIC] Check power and environmental alarms for the site.
3. [DIAGNOSTIC] Review CPU and memory trend. Steady growth over hours suggests a software leak.
4. [DIAGNOSTIC] Review recent software upgrades and configuration changes.
5. [DIAGNOSTIC] Check whether neighbours still see the device (routing adjacency, link state).

## 3. Restoration Actions
- [NON-DISRUPTIVE] Collect logs and diagnostic dumps through approved tooling.
- [DISRUPTIVE - APPROVAL REQUIRED] Restart a process or the device.
- [DISRUPTIVE - APPROVAL REQUIRED] Fail over to a standby unit or spare port.
- [ESCALATE] Dispatch field engineering for power or hardware faults. Open a vendor case for suspected software defects.

## 4. Verification
Device reachable, neighbours up, CPU/memory stable, alarms cleared. See SOP-006.
