# Antigravity Telecom NOC Decision-Support Platform
# Comprehensive System Requirements Specification

## 1. Runtime System Requirements
| Software Component | Minimum Version | Recommended Version | Verification Command | Notes |
|---|---|---|---|---|
| **Python** | 3.10.0 | 3.11 or 3.13 | `python --version` | Standard CPython. Add to system PATH during installation. |
| **Node.js** | 18.0.0 | 20.x or 22.x LTS | `node --version` | Required for building and running the React Vite cockpit. |
| **npm** | 9.0.0 | 10.x+ | `npm --version` | Bundled automatically with Node.js. |
| **Git** | 2.30.0+ | Latest | `git --version` | Version control & repository synchronization. |
| **Operating System**| Windows 10/11, macOS 12+, or Ubuntu 20.04+ LTS | Cross-platform compatible. |

---

## 2. Python Backend Dependencies (`backend/requirements.txt`)
All packages installable via `pip install -r backend/requirements.txt`:

| Package | Version | Architectural Purpose in Platform |
|---|---|---|
| `fastapi` | `>=0.110.0` | High-performance asynchronous REST API framework with automatic OpenAPI docs. |
| `uvicorn` | `>=0.28.0` | Production ASGI web server for running FastAPI. |
| `pydantic` | `>=2.6.0` | Strongly typed validation for `IncidentState`, events, hypotheses, and actions. |
| `langgraph` | `>=0.0.1` | Multi-agent state machine graph (`StateGraph`) orchestrating Agents 1 through 8. |
| `networkx` | `>=3.2.0` | Directed multi-graph topology modeling, reachability, and Lowest Common Ancestor (LCA). |
| `scikit-learn` | `>=1.4.0` | Isolation Forest unsupervised anomaly detection & StandardScaler preprocessing. |
| `pandas` | `>=2.0.0` | Time-series telemetry batch loading, windowing, and statistical analysis. |
| `reportlab` | `>=4.0.0` | Automated generation of the 16-section post-mortem incident PDF report (Req 20). |
| `pytest` | `>=8.0.0` | Unit and integration test suite covering all agents and TC-01 through TC-08. |
| `anyio` | `>=4.0.0` | Asynchronous worker thread pool management. |

---

## 3. Frontend JavaScript / TypeScript Dependencies (`frontend/package.json`)
All packages installable via `npm install`:

| Package | Version | Architectural Purpose in Platform |
|---|---|---|
| `react` | `^19.0.0` | Core UI component rendering. |
| `react-dom` | `^19.0.0` | DOM bindings for React. |
| `vite` | `^8.0.0` | Modern frontend development server and optimized bundler. |
| `typescript` | `^5.0.0` | Strict type checking and Pydantic-aligned interface definitions. |
| `tailwindcss` | `^4.0.0` | Modern utility-first responsive styling and NOC dark-mode theme. |
| `@tailwindcss/vite` | `^4.0.0` | High-speed Vite integration plugin for Tailwind CSS. |
| `lucide-react` | `^1.55.0` | Telecom and operational UI iconography. |
| `recharts` | `^3.10.0` | Real-time telemetry line charts (latency, packet loss, jitter, link utilization). |

---

## 4. Hardware & Port Requirements
- **RAM:** Minimum 4 GB (8 GB recommended).
- **Disk Space:** ~500 MB (includes Python packages, Node modules, baseline datasets).
- **Network Ports:**
  - `8000` — Backend API (FastAPI)
  - `5173` — Frontend Dashboard (Vite)
