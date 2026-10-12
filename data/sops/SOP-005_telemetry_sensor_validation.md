# SOP-005: Telemetry and Sensor Validation

**Document ID:** SOP-005 | **Version:** 1.2 | **Status:** Approved
**Applies to alarms:** any metric alarm that conflicts with other evidence

## 1. Scope
Use when a metric looks implausible or is not backed by any alarm or neighbouring evidence.

## 2. Indicators of a Telemetry Problem
- Values perfectly constant for many consecutive samples (for example CPU exactly 100%).
- Impossible combinations (memory 0% on a running device).
- No related alarms, traffic effect, or neighbour impact.
- Missing samples or timestamps out of order.

## 3. Diagnostic Steps
1. [DIAGNOSTIC] Compare the device's metrics with related metrics and neighbours.
2. [DIAGNOSTIC] Check the monitoring agent or collector health.
3. [DIAGNOSTIC] Re-poll the metric through a second method if available.

## 4. Actions
- [NON-DISRUPTIVE] Mark the data as suspect and exclude it from anomaly scoring until validated.
- [ESCALATE] Notify the monitoring team to repair the collector. No network change is needed if the device is confirmed healthy.
