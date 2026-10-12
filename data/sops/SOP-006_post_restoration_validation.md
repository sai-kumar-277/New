# SOP-006: Post-Restoration Validation and Incident Closure

**Document ID:** SOP-006 | **Version:** 1.4 | **Status:** Approved

## 1. Scope
Use after any restoration action, before closing or escalating an incident.

## 2. Validation Checklist
1. [DIAGNOSTIC] Related alarms cleared (not just suppressed).
2. [DIAGNOSTIC] Interface oper-state up on both link ends.
3. [DIAGNOSTIC] Latency, packet loss, jitter and utilization compared with the pre-incident baseline and the values during the incident.
4. [DIAGNOSTIC] Service status restored for every affected service, including those previously only "potentially affected".
5. [DIAGNOSTIC] Observe for at least 15 minutes to rule out recurrence or flapping.

## 3. Closure Criteria
- All checks pass: close the incident and record the confirmed root cause only if it was actually verified. Otherwise record it as "suspected".
- Any check fails or the fault recurs: [ESCALATE] and reopen the incident.

## 4. Record Keeping
Record the pre/post metrics, approvals, engineer comments, and the final root-cause status in the incident report.
