# SOP-003: Network Congestion, High Latency and Packet Loss

**Document ID:** SOP-003 | **Version:** 1.5 | **Status:** Approved
**Applies to alarms:** utilization_high, packet_loss_high, latency_high, jitter_high

## 1. Scope
Use when link utilization, latency, jitter or packet loss exceed normal baselines.

## 2. Do Not Assume
High utilization is a symptom, not a root cause. Determine why traffic is high before acting.

## 3. Diagnostic Steps
1. [DIAGNOSTIC] Compare current metrics with the baseline for the same link and time of day.
2. [DIAGNOSTIC] Check whether a parallel or redundant link has failed and traffic has shifted onto this link.
3. [DIAGNOSTIC] Check for a routing change that moved traffic onto this path.
4. [DIAGNOSTIC] Check interface errors and device CPU/memory to distinguish congestion from a degraded element.
5. [DIAGNOSTIC] Cross-check related metrics. Values that are perfectly flat, or that conflict with other telemetry, suggest a sensor problem (see SOP-005).

## 4. Restoration Actions
- [NON-DISRUPTIVE] Continue monitoring and alert the engineer when thresholds persist for 5 minutes.
- [DISRUPTIVE - APPROVAL REQUIRED] Apply a temporary traffic-engineering or rate-limit policy.
- [ESCALATE] If caused by a failed redundant link, prioritise repair of that link (SOP-001).

## 5. Verification
Utilization, latency, loss and jitter return to baseline. See SOP-006.
