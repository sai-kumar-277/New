# Agentic AI Telecom Network Fault Diagnosis & Service Restoration System

A Network Operations Center (NOC) **decision-support platform** that uses multiple specialized AI agents to correlate alarms, localize faults, analyze service impact, propose root causes, retrieve approved procedures, and recommend restoration steps, with a NOC engineer approving every consequential action.

> **Safety principle:** the system never modifies network infrastructure. All recommended actions are proposals; potentially disruptive actions require explicit human approval.

**Status legend:** ⬜ not started · 🟨 in progress · ✅ done
**Deadline:** 12 Oct 2026 · **Live frontend:** _TBD_ · **Live backend:** _TBD_

---

## 1. Progress Tracker

### Phase 0: Setup & Data
| Item | Status | Notes |
|---|---|---|
| Repo + folder structure | ✅ | `data/`, `scripts/` created; `backend/`, `frontend/` next |
| Sample topology (`data/topology.json`) | ✅ | 11 devices, 11 links, 7 services; AR-01 single-homed, AR-02 dual-homed |
| Alarm datasets (cascade, storm, congestion, single, dynamic, vendor-raw) | ✅ | 6 scenario files with expected outcomes. No standalone device-failure scenario yet |
| Telemetry dataset (normal + degraded) | ✅ | 24h normal train set + 4h eval set with injected faults and labels |
| Historical incidents (`data/incidents.json`) | ✅ | 8 incidents incl. INC-NET-032 |
| SOP / troubleshooting docs (`data/sops/*.md`) | ✅ | SOP-001 to SOP-006, actions tagged by risk class |

### Phase 1: Backend Core
| Item | Status | Notes |
|---|---|---|
| Pydantic schemas + shared `IncidentState` | ✅ | `backend/app/models/`, 25 tests passing |
| Agent 1: Telemetry & Alarm Intake | ✅ | Basic normalisation & testing done |
| Agent 2: Alarm Correlation | ✅ | NetworkX-based parent/child deduplication and storm detection done |
| Agent 3: Topology & Fault Localization | ✅ | Inference & evidence extraction via NetworkX done |
| Agent 4: Performance & Anomaly Detection | ✅ | Scikit-learn IsolationForest & Z-Score trained |
| Agent 5: Service Impact Analysis | ✅ | Graph-based service resolution and validation done |
| Agent 6: Root Cause Analysis | ✅ | TF-IDF based RAG & rules engine implemented |
| Agent 7: Restoration & Action Planning | ✅ | SOP parsing and multi-category action proposal implemented |
| Agent 8 (optional): Reviewer / Critic | ✅ | Safety, validation & hallucination review implemented |
| LangGraph orchestration | ✅ | Full multi-agent StateGraph pipeline with trace tracking |
| RAG (SOPs + historical incidents) | ✅ | TF-IDF retrieval for historical incidents + SOP markdown parser |
| Anomaly model trained + evaluated | ✅ | Isolation Forest trained on 24h baselines with Z-Score explainability |

### Phase 2: Workflow
| Item | Status | Notes |
|---|---|---|
| Human approval workflow | ✅ | Guarded engineer decisions, approval logging, and explicit authorizations |
| Action tracking state machine | ✅ | Proposed → Approved → In Progress → Completed → Verified |
| Post-restoration validation | ✅ | Pre- and post-telemetry comparisons + automated verification gates |
| Dynamic reassessment | ✅ | Re-evaluates active incidents on incoming alarms and tracks revisions |
| PDF incident report | ✅ | Automated 16-section post-mortem report generation via ReportLab |

### Phase 3: Frontend
| Page | Status | Notes |
|---|---|---|
| NOC Dashboard | ✅ | Network health score, KPI cards, quick scenario runners |
| Network Topology | ✅ | Interactive visual node-and-link graph with device inspector |
| Incident Center | ✅ | Correlated incident viewer with multi-agent LangGraph trace |
| Approval Center | ✅ | Guarded engineer authorization & action tracking state machine |
| Alarm Console | ✅ | Filterable alarms table with severity & primary badges |
| Network Inventory | ✅ | Router & Base Station interface inspection |
| Performance Monitoring | ✅ | Telemetry trend charts (latency, packet loss, jitter) via Recharts |
| Fault Localization / Service Impact / RCA | ✅ | Corroborated fault suspects & RAG historical citations |
| Knowledge Base | ✅ | Searchable approved SOPs & past incident repository |
| Restoration Planning / Action Tracker / Incident Reports | ✅ | Action progression & 1-click PDF incident report export |

### Phase 4: Delivery
| Item | Status | Notes |
|---|---|---|
| Test cases TC-01 to TC-08 documented | ✅ | 47 automated tests passing in pytest |
| Architecture diagram | ✅ | Multi-agent LangGraph workflow diagram included |
| Backend deployed (Render) | 🟨 | Ready to deploy (`backend/app/main.py`) |
| Frontend deployed (Vercel) | 🟨 | Ready to deploy (`frontend/dist`) |
| README sections completed | ✅ | Complete documentation of all agents, pipelines, and models |
| End-to-end demo rehearsed | ✅ | Full end-to-end flow verified |

---

## 2. Project Overview
The **Agentic AI Telecom Network Fault Diagnosis & Service Restoration System** is a mission-critical Network Operations Center (NOC) decision-support platform designed for high-availability cellular backhaul and IP core transport environments. By combining deterministic graph algorithms with machine-learned anomaly detection and local RAG retrieval, the system autonomously analyzes cascading network alarms, localizes physical and logical fault domains, quantifies customer service impact, matches historical resolution precedents, and formulates standard operating procedure (SOP) restoration action plans.

Crucially, the system operates under a strict **human-in-the-loop safety contract**: AI agents never autonomously push destructive configuration changes or physical modifications to live production infrastructure. Every proposed operational intervention is presented to a Tier-3 NOC engineer through an interactive cockpit, complete with full audit traces, evidence citations, and automated pre/post telemetry verification.

## 3. Problem Statement & Telecom Use Case
Modern cellular networks experience acute alarm storms when upstream aggregation elements degrade. A single fiber cut on an aggregation uplink (`AR-01`) immediately triggers cascading alarms across dependent cell sites (`BS-101`, `BS-102`, `BS-103`), generating hundreds of notifications within seconds. NOC engineers are routinely overwhelmed by redundant alerts, leading to:
1. **Prolonged Mean Time to Repair (MTTR):** Time lost manually tracing parent/child dependencies.
2. **Alert Fatigue:** Difficulty distinguishing isolated link outages from catastrophic core storms.
3. **Operational Risk:** Accidental execution of disruptive commands (such as bouncing transceivers or traffic draining) without verifying topological redundancies.

**Concrete Case Study (`scenario_cascade.json`):**
At `10:02:01`, aggregation router `AR-01` reports `interface_down` on interface `GE-0/0/1`. Over the next 7 seconds, base stations `BS-101` and `BS-102` drop backhaul (`backhaul_connectivity_lost`) and report `service_unavailable`. The system ingests all 5 alarms, cross-references the NetworkX topology graph, flags the initial interface drop as the single `PRIMARY` event, categorizes the rest as `CONSEQUENTIAL`, localizes the failure to physical link `LNK-CR01-AR01`, and presents a prioritized fiber-splicing SOP to the engineer.

## 4. System Architecture

```mermaid
flowchart TD
    subgraph Data Layer
        A1[Syslog / SNMP Traps / Vendor JSON] --> AG1
        A2[Baseline & Eval Telemetry CSV] --> AG4
        A3[Historical Incidents Database] --> AG6
        A4[Standard Operating Procedures SOPs] --> AG7
    end

    subgraph Multi-Agent Orchestration Engine [LangGraph StateGraph]
        AG1[Agent 1: Telemetry & Alarm Intake] -->|Normalized Events| AG2[Agent 2: Alarm Correlation]
        AG2 -->|Correlation Result & Primary IDs| AG3[Agent 3: Topology & Fault Localization]
        AG3 -->|Ranked Fault Hypotheses| AG4[Agent 4: Anomaly Detection]
        AG4 -->|Isolation Forest Metric Findings| AG5[Agent 5: Service Impact Analysis]
        AG5 -->|Service Reachability & Redundancy| AG6[Agent 6: Root Cause Analysis]
        AG6 -->|TF-IDF RAG & Corroborated Hypotheses| AG7[Agent 7: Restoration & Action Planning]
        AG7 -->|SOP Tagged Action Proposals| AG8[Agent 8: Safety Reviewer / Critic]
    end

    subgraph Human-in-the-Loop Cockpit
        AG8 -->|Validated Incident State| GATE{Engineer Approval Gate}
        GATE -->|Explicit Authorization| EXEC[Action Execution State Machine]
        EXEC --> VAL[Post-Restoration Validation]
        VAL --> PDF[16-Section PDF Incident Post-Mortem]
    end
```

## 5. Multi-Agent Design
The platform coordinates 8 specialized agents using LangGraph's event-driven `StateGraph`, passing a strongly typed Pydantic `IncidentState`:

| # | Agent | Engine Type | Reads from State | Writes to State | Key Responsibility |
|---|---|---|---|---|---|
| **1** | **Intake Agent** | Deterministic Regex & IP Mapper | Raw JSON / Syslog / SNMP | `events` (`list[NormalizedEvent]`) | Ingests multi-vendor formats, maps management IPs to device IDs, validates timestamps. |
| **2** | **Alarm Correlation** | NetworkX MultiDiGraph | `events` | `correlation` (`CorrelationResult`) | Identifies primary vs. consequential alarms, deduplicates repeats, and flags alarm storms (>50 alarms/60s). |
| **3** | **Fault Localization** | NetworkX Graph Traverser | `events`, `correlation` | `fault_hypotheses` (`list[FaultLocationHypothesis]`) | Maps primary interface alarms to links; computes Lowest Common Ancestor (LCA) when upstream alarms are absent. |
| **4** | **Anomaly Detection** | Scikit-Learn IsolationForest & Z-Score | `events`, `correlation` | `anomalies` (`list[AnomalyFinding]`) | Detects metric deviations against 24h baseline; calculates Z-Scores for latency, loss, and stuck sensors. |
| **5** | **Service Impact** | NetworkX Reachability & Redundancy Engine | `events`, `correlation`, `fault_hypotheses` | `service_impact` (`ServiceImpact`) | Traces downstream services; checks path redundancy (Degraded vs. Unavailable); never invents customer numbers. |
| **6** | **Root Cause Analysis** | Local TF-IDF Vectorizer + Cosine RAG | `events`, `correlation`, `fault_hypotheses`, `anomalies` | `rca_hypotheses`, `historical_matches` | Matches alarm patterns against `incidents.json`; demands multi-source corroboration for HIGH confidence. |
| **7** | **Restoration Planning** | Deterministic SOP Markdown Parser | `rca_hypotheses`, `service_impact` | `actions` (`list[RestorationAction]`) | Parses markdown SOP steps; categorizes risk classes (`diagnostic`, `disruptive`, `escalation`). |
| **8** | **Safety Reviewer / Critic** | Guardrail Rules Validator | Full `IncidentState` | `reviewer_findings` | Audits state for unassigned alarms, unsubstantiated claims, or disruptive actions missing approval gates. |

- **Agent Execution Visibility (Requirement 19):** Every agent logs its lifecycle using `AgentTraceEntry` (agent name, start/end timestamps, input summary, findings summary, status).

## 5a. Shared Workflow State (`IncidentState`)
Every agent reads from and writes to one `IncidentState` per correlated incident (`backend/app/models/incident.py`). Each agent owns one slice, so agents never overwrite each other.

| Slice | Written by |
|---|---|
| `events` (immutable `NormalizedEvent`s) | Intake |
| `correlation` (role per event, duplicates, storm flag) | Correlation |
| `fault_hypotheses`, `anomalies`, `service_impact` | Localization, Anomaly, Service Impact |
| `historical_matches`, `procedure_refs`, `rca_hypotheses` | Root Cause (via RAG) |
| `actions` | Restoration |
| `reviewer_findings` | Reviewer |
| `human_decisions`, `confirmed_root_cause`, `validation`, `reassessments`, `trace` | Engineer / system |

**Rules enforced by validators** (each has a test in `backend/tests/test_models.py`):
1. Original alarms are frozen and never removed; every event must have a correlation role.
2. A hypothesis must cite evidence. HIGH confidence needs alarms plus topology (fault) or 2+ distinct evidence sources (RCA).
3. Root cause stays *suspected* until an engineer confirms it with a verification note.
4. Actions move Proposed → Approved → In Progress → Completed → Verified. Only an engineer can approve; disruptive actions also need explicit authorization; Verified requires passing validation.
5. Customer counts need a named data source; otherwise they stay `null`.
6. Tampered JSON (for example a disruptive action marked in-progress with no approver) fails validation on load.

## 6. Data & Methodology

### Network Inventory & Topology Model (NetworkX)
- Defined in `data/topology.json` comprising 11 network elements: 1 Transit Gateway (`GW-01`), 1 Core Router (`CR-01`), 2 Aggregation Routers (`AR-01` single-homed, `AR-02` dual-homed), 6 Base Stations (`BS-101..103`, `BS-201..203`), and 1 Enterprise Link (`E-101`).
- The topology is modeled as a directed hierarchical acyclic graph (`NetworkX MultiDiGraph`) tiered from Tier-0 (Gateway) down to Tier-4 (Base Stations). Edge directions represent upstream $\to$ downstream dependencies.

### Alarm Ingestion & Normalization
- `IntakeAgent` parses RFC 5424 / RFC 3164 Syslog messages, SNMP trap key-value pairs, vendor JSON payloads, and synthetic test events.
- Device IPs are dynamically mapped to hostnames using the topology registry. Invalid timestamps or unmapped records are safely captured with `device: "UNKNOWN"`.

### Alarm Correlation & Storm Suppression
- **Temporal Windowing:** Groups alarms arriving within a rolling 120-second window.
- **Topological Parent-Child Suppression:** If device $U$ is an upstream ancestor of device $V$ and both report critical connectivity alarms within the window, $U$'s alarm is assigned role `PRIMARY` and $V$'s alarm is marked `CONSEQUENTIAL`.
- **Deduplication:** Repeated alarms on the same `(device, interface, event_type)` within the correlation window are assigned role `DUPLICATE` pointing to the root event ID.
- **Storm Detection:** If alarm frequency exceeds 50 events per 60 seconds (demonstrated in `scenario_storm.json` with 300 alarms in 90s), the system activates `storm_detected = True`, collapsing the storm into primary ingress root causes.

### Performance & Anomaly Detection
- **Model:** Scikit-Learn `IsolationForest` (`contamination=0.05`, `n_estimators=100`, random seed 42) pre-trained on 24 hours of 1-minute baseline telemetry (`telemetry_train_normal.csv`).
- **Explainability:** When an anomaly is detected on `telemetry_eval.csv`, the agent computes metric-level Z-Scores ($Z = \frac{x - \mu}{\sigma}$) against baseline means and standard deviations. It flags specific contributing metrics (e.g., `latency_ms: 180.0ms [Z=+6.8]`, `packet_loss_pct: 8.5% [Z=+12.1]`).
- **Sensor Fault Detection:** Detects flatlined telemetry ($100\%$ or $0\%$ utilization with zero downstream packet loss) and classifies them as sensor errors rather than real network faults.

### Fault Localization & Lowest Common Ancestor (LCA)
- **Direct Strategy:** When a primary alarm explicitly flags a physical interface (e.g., `GE-0/0/1` on `CR-01`), the agent maps the interface to its corresponding link ID (`LNK-CR01-AR01`).
- **Inferential LCA Strategy:** In scenarios where upstream core/aggregation alarms fail to arrive (e.g., simultaneous backhaul loss on `BS-101` and `BS-102`), the agent queries the directed graph for the lowest common topological ancestor. It identifies the shared aggregation node (`AR-01`) as the fault domain.

### Service Impact & Reachability
- Computes reachable graph components from the fault domain to all business service endpoints.
- Verifies path redundancy: services dependent on dual-homed nodes (`AR-02`) with only one link failed are categorized as `DEGRADED`; services with no redundant backup (`AR-01`) are marked `UNAVAILABLE`.
- **Rigor Contract:** Enforces strict adherence to Requirement 7—customer counts remain `null` unless backed by an explicit, verifiable external subscriber data source.

### Root Cause Analysis & Local Retrieval (RAG)
- Vectorizes alarm features, impacted device types, and topology patterns using `TfidfVectorizer` (unigrams + bigrams).
- Computes cosine similarity against the historical incidents repository (`incidents.json`), retrieving past incidents with similarity scores and explicit operational caveats (e.g., matching `INC-NET-032` for physical link failure).
- Evaluates multi-source corroboration: a hypothesis is only granted `HIGH` confidence if supported by 2 or more distinct evidence types (e.g., Alarm evidence + Topology evidence + Telemetry anomaly).

### Restoration Planning & SOP Parsing
- Reads approved standard operating procedure markdown files (`data/sops/SOP-001` to `SOP-006`).
- Uses regex tag extractors (`\[DIAGNOSTIC\]`, `\[NON-DISRUPTIVE\]`, `\[DISRUPTIVE\]`, `\[ESCALATION\]`) to parse structured actions into strongly-typed `RestorationAction` objects.
- Automatically marks potentially disruptive actions with `requires_approval = True`.

### Guarded Human Approvals & Action Tracking State Machine
- Strict state progression:
  $$\text{Proposed} \longrightarrow \text{Approved} \longrightarrow \text{In Progress} \longrightarrow \text{Completed} \longrightarrow \text{Verified}$$
- All actions are initiated in state `PROPOSED`.
- Potentially disruptive actions rejected if approved without `explicit_authorization = True`.
- State transitions are audited with engineer name, timestamp, and verification comments.

### Post-Restoration Validation (TC-07)
- Compares pre-restoration telemetry against post-restoration telemetry:
  - Latency: $180\text{ ms} \longrightarrow 22\text{ ms}$ (PASS if $<50\text{ ms}$)
  - Packet Loss: $8.5\% \longrightarrow 0.4\%$ (PASS if $<1.0\%$)
  - Jitter: $42\text{ ms} \longrightarrow 6\text{ ms}$ (PASS if $<15\text{ ms}$)
  - Operational interface state verified `UP`.
- Automatically transitions completed actions to `VERIFIED` only when all validation checks succeed.

### Dynamic Reassessment (TC-08)
- When a new alarm arrives while an incident is active:
  1. Checks if the new event falls within the incident's failure domain or downstream dependencies.
  2. If related (e.g. delayed `BS-103 backhaul lost` 7 minutes later), incorporates the alarm, recalculates hypotheses, increments `state.revision`, and appends an audit log to `state.reassessments`.
  3. If unrelated (e.g. `AR-02 CPU high`), leaves the active incident untouched and isolates the event.

## 6a. Dataset (synthetic, reproducible)
Everything under `data/` is generated by `python scripts/generate_data.py` (seed 42), except the incidents and SOPs, which are hand-written.

| File | Contents |
|---|---|
| `data/topology.json` | Devices (inventory fields), links with capacity and redundancy groups, services. `customer_count` is `null` on purpose: the system must not invent customer counts |
| `data/alarms/scenario_single.json` | TC-01: one AR-02 uplink down with a redundant uplink still up |
| `data/alarms/scenario_cascade.json` | TC-02/05/06: the AR-01 example from the assignment (5 alarms) |
| `data/alarms/scenario_storm.json` | TC-03: 300 alarms in 90 s (AR-02 dual-uplink loss) plus 2 unrelated alarms |
| `data/alarms/scenario_congestion.json` | TC-04: uplink A fails, traffic shifts to B and saturates |
| `data/alarms/scenario_dynamic.json` | TC-08: one related and one unrelated alarm arriving mid-incident |
| `data/alarms/scenario_vendor_raw.json` | Syslog, SNMP-style and vendor JSON raw events for the intake agent (includes a duplicate, a bad timestamp, and a missing device) |
| `data/telemetry/telemetry_train_normal.csv` | 2026-10-02, 24 h, 1-minute samples, no faults (model training) |
| `data/telemetry/telemetry_eval.csv` | 2026-10-03 08:00-12:00 with labelled faults (below) |
| `data/incidents.json` | 8 historical incidents (physical, hardware, config, power, sensor, software, external, congestion) |
| `data/sops/` | 6 approved procedures, each with sections the RAG can cite |

**Labelled faults in `telemetry_eval.csv`** (columns `scenario_label`, `is_anomaly`)

| Time | Entity | Label |
|---|---|---|
| 09:00 onward | CR-01 memory | `gradual_memory_growth` (slow leak) |
| 10:00-10:01 | LNK-CR01-AR01 | `precursor_errors` (error burst before the outage) |
| 10:02-10:34 | LNK-CR01-AR01 | `link_down` (matches the 10:02:01 alarm) |
| 10:50-11:29 | LNK-CR01-AR02-A | `link_down` |
| 10:50-11:29 | LNK-CR01-AR02-B | `congestion_traffic_shift` (latency about 180 ms, loss about 8.5%, utilisation about 96%, jitter about 42 ms) |
| 11:30-11:34 | LNK-CR01-AR02-B | `post_restoration` (loss about 0.4%) |
| 11:40-11:50 | AR-02 CPU/memory | `sensor_fault` (flat 100% / 0% with no matching effects) |

Note: about 20% of eval rows are anomalous, far higher than real networks. This is acceptable for a demo and evaluation set, but report precision/recall rather than accuracy.

## 7. Database & State Persistence Model
The platform adopts an immutable audit-log state architecture. Rather than ad-hoc document updates, every correlated event is versioned and captured in the shared `IncidentState` data structure:
- **`NormalizedEvent` Table/Store:** Immutable append-only log of physical and logical telemetry events.
- **`CorrelationResult` Entity:** Maps alarm UUIDs to roles (`PRIMARY`, `CONSEQUENTIAL`, `DUPLICATE`, `INDEPENDENT`).
- **`FaultLocationHypothesis` Collection:** Ranked suspect elements (`device`, `link`, `interface`) with supporting telemetry/topology evidence.
- **`RestorationAction` Audit Store:** Tracks transition history from `PROPOSED` $\to$ `APPROVED` $\to$ `IN_PROGRESS` $\to$ `COMPLETED` $\to$ `VERIFIED`, recording the approving engineer, authorization timestamp, and operational remarks.
- **`ReassessmentRecord` Log:** Historical ledger capturing dynamic alarm arrivals, material change evaluations, and topological recalculations.

## 8. API Documentation
The backend exposes a high-performance FastAPI REST API with automatic OpenAPI documentation available at `http://localhost:8000/docs`:

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Service health status and version verification. |
| `GET` | `/api/topology` | Returns complete multi-tier network topology (devices, links, services). |
| `GET` | `/api/inventory/devices` | Lists managed network inventory and operational interface statuses. |
| `GET` | `/api/inventory/devices/{id}` | Inspects detailed hardware, vendor, and interface states for a single device. |
| `GET` | `/api/alarms/scenarios` | Enumerates available benchmark scenarios (`cascade`, `storm`, `congestion`, etc.). |
| `POST` | `/api/alarms/ingest` | Ingests and normalizes raw Syslog, SNMP, or JSON alarms. |
| `POST` | `/api/incidents/run-scenario/{file}` | Runs end-to-end multi-agent LangGraph workflow on a scenario. |
| `GET` | `/api/incidents` | Lists active and historical incidents with revision counters and root cause. |
| `GET` | `/api/incidents/{id}` | Fetches full incident state, evidence citations, and agent execution trace. |
| `POST` | `/api/incidents/{id}/actions/{aid}/approve` | Engineer approval gate (requires `explicit_authorization` for disruptive actions). |
| `POST` | `/api/incidents/{id}/actions/{aid}/start` | Transitions action status to `IN_PROGRESS`. |
| `POST` | `/api/incidents/{id}/actions/{aid}/complete` | Records field resolution findings and moves action to `COMPLETED`. |
| `POST` | `/api/incidents/{id}/validate` | Triggers post-restoration telemetry & alarm validation checks (TC-07). |
| `POST` | `/api/incidents/{id}/reassess` | Ingests new alarm into active incident and recomputes fault domain (TC-08). |
| `GET` | `/api/incidents/{id}/report.pdf` | Streams generated 16-section incident post-mortem PDF report (Req 20). |
| `GET` | `/api/telemetry` | Telemetry timeseries for trend visualization and anomaly detection. |
| `GET` | `/api/knowledge/sops` | Returns library of approved standard operating procedures (SOPs). |
| `GET` | `/api/knowledge/incidents` | Returns historical incident database used for RAG matching. |

## 9. Setup & Local Execution

### Environment Variables
| Variable | Description | Default |
|---|---|---|
| `PORT` | FastAPI backend port | `8000` |
| `VITE_API_URL` | API proxy target for Vite | `http://localhost:8000` |

### Backend
```bash
cd telecom-noc/telecom-noc/backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
Interactive API docs: `http://localhost:8000/docs`

### Frontend
```bash
cd telecom-noc/telecom-noc/frontend
npm install
npm run dev
```
NOC Cockpit UI: `http://localhost:5173`

## 10. Deployment Guide
- **Backend (Render / Railway):** Deploy the `backend/` directory using the Python runtime. Set start command to `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- **Frontend (Vercel / Netlify):** Deploy the `frontend/` directory using the Vite template (`npm run build`, output directory `dist`). Configure rewrite rule `/api/*` to forward to the backend URL.

## 11. Testing & Benchmark Evidence

| ID | Scenario | Input Event / Condition | Primary Agent(s) | Verification & Evidence | Status |
|---|---|---|---|---|---|
| **TC-01** | Interface Down Alarm | Single `interface_down` alarm on redundant link `LNK-CR01-AR02-A` | Intake, Correlation | Incident created; primary alarm flagged; service marked `DEGRADED` due to backup uplink `B`. | ✅ PASS |
| **TC-02** | Downstream Cascade | `AR-01` down followed by `BS-101`, `BS-102` backhaul loss | Correlation, Localization | 5 alarms collapsed; `AR-01` identified as primary; consequential alarms suppressed. | ✅ PASS |
| **TC-03** | Alarm Storm | 300 alarms within 90s (`AR-02` dual uplink loss) | Correlation | `storm_detected = True`; duplicate alarms suppressed; root ingress links isolated. | ✅ PASS |
| **TC-04** | Performance Degradation | Link failover saturation: latency jumps to 180ms, loss to 8.5% | Anomaly Detection | Isolation Forest flags anomaly ($p<0.05$); Z-Score explainability pinpoints latency ($Z=+6.8$) & loss ($Z=+12.1$). | ✅ PASS |
| **TC-05** | Missing Upstream Alarm | `BS-101` and `BS-102` lose backhaul without core router alarm | Localization | Inferred shared dependency: Lowest Common Ancestor (LCA) identifies aggregation router `AR-01`. | ✅ PASS |
| **TC-06** | Historical Precedent Matching | Cascade pattern matches historical fiber break | RCA (TF-IDF RAG) | Retrieves `INC-NET-032` (88% similarity); cites SOP-001 with fiber splicing recommendation. | ✅ PASS |
| **TC-07** | Post-Restoration Verification | Restoration action completed; telemetry re-sampled | WorkflowService | Automated validation checks verify loss recovery ($8.5\% \to 0.4\%$) & alarm clearance. Status $\to$ `VERIFIED`. | ✅ PASS |
| **TC-08** | Dynamic Reassessment | Active incident receives delayed `BS-103` alarm | WorkflowService, Localization | Alarm recognized as downstream failure-domain member; revision bumped to #2; impact updated. | ✅ PASS |

## 12. Repository Structure
```
telecom-noc/
├── backend/
│   ├── app/
│   │   ├── agents/          # Intake, Correlation, Localization, Anomaly, Impact, RCA, Restoration, Reviewer
│   │   ├── graph/           # LangGraph StateGraph workflow orchestrator
│   │   ├── models/          # Strongly typed Pydantic models (IncidentState, NormalizedEvent, Actions)
│   │   ├── services/        # Anomaly model persistence, WorkflowService (Approvals, Reassessment, PDF)
│   │   └── main.py          # FastAPI application entrypoint
│   ├── tests/               # 47 unit & integration tests (pytest)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api.ts           # API client and TypeScript interface definitions
│   │   ├── App.tsx          # NOC Cockpit UI (Dashboard, Topology, Incident Trace, Action Approvals)
│   │   └── index.css        # Tailwind CSS styling
│   ├── package.json
│   └── vite.config.ts
├── data/
│   ├── alarms/              # Benchmark scenario datasets (TC-01 through TC-08)
│   ├── telemetry/           # 24h normal training baseline + 4h evaluation dataset
│   ├── sops/                # Approved Standard Operating Procedures (SOP-001 to SOP-006)
│   ├── incidents.json       # Historical incident repository for RAG matching
│   └── topology.json        # 11-node network topology inventory & connectivity
├── scripts/
│   └── generate_data.py     # Deterministic synthetic data generator (seed 42)
└── README.md
```

## 13. Design Decisions Log
Keep this updated; it's your prep for the technical discussion.

| Date | Decision | Alternatives considered | Reason |
|---|---|---|---|
| 10 Oct | LangGraph for orchestration | CrewAI, AutoGen | Explicit shared state fits the workflow-state requirement |
| 10 Oct | Deterministic logic for agents 1-5, LLM for RCA/restoration | LLM for everything | Testable, explainable, cheaper |
| 10 Oct | One shared Pydantic `IncidentState`, validated on every load | Free-form dict state | Typos and unsafe states fail at the boundary; the state doubles as the audit record |
| 10 Oct | Events frozen; roles stored separately in `CorrelationResult` | Mutating events with a role field | Audit evidence cannot be altered; correlation can be re-run on reassessment |
| 10 Oct | Approval rules coded as model methods (`approve`, `start`, ...) | Rules only in API handlers | Cannot be bypassed by any caller, including agents |
| 10 Oct | NetworkX `MultiGraph` for topology | Plain `Graph` | A plain graph merges AR-02's two parallel uplinks and hides redundancy |
