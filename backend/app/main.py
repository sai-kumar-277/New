import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.models.enums import ActorRole, RootCauseCategory
from app.models.incident import Actor, IncidentState
from app.models.network import NormalizedEvent, Topology
from app.graph.workflow import NetworkNOCWorkflow
from app.services.workflow_service import WorkflowService

# Initialize app
app = FastAPI(
    title="Agentic AI Telecom Network Fault Diagnosis & Service Restoration API",
    description="Backend API for autonomous NOC decision support, multi-agent orchestration, and engineer approvals.",
    version="1.0.0"
)

# CORS setup for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Base Paths
BACKEND_DIR = Path(__file__).parent.parent
DATA_DIR = BACKEND_DIR.parent / "data"

# Load Core Services
topology = Topology.from_file(DATA_DIR / "topology.json")
workflow = NetworkNOCWorkflow(topology, str(DATA_DIR))
workflow_service = WorkflowService(workflow, topology)

# In-memory Incident and Alarm store
incidents_db: Dict[str, IncidentState] = {}
alarms_db: List[NormalizedEvent] = []


# Request DTOs
class IngestAlarmsRequest(BaseModel):
    raw_events: List[Dict[str, Any]]
    incident_id: Optional[str] = "INC-NET-101"


class ActionApprovalRequest(BaseModel):
    engineer_name: str
    explicit_authorization: bool = False


class ActionRejectRequest(BaseModel):
    engineer_name: str
    reason: str


class ActionModifyRequest(BaseModel):
    engineer_name: str
    new_description: str
    comment: str = ""


class ActionTransitionRequest(BaseModel):
    engineer_name: str
    result: Optional[str] = None


class ConfirmRootCauseRequest(BaseModel):
    engineer_name: str
    category: RootCauseCategory
    verification_note: str


# --------------------------------------------------------------------------- #
# 1. Network Inventory & Topology (Req 1 & 2)
# --------------------------------------------------------------------------- #
@app.get("/api/topology")
def get_topology():
    """Returns interactive network topology representation."""
    return topology.model_dump()


@app.get("/api/inventory/devices")
def get_devices():
    """Returns network elements inventory."""
    return [d.model_dump() for d in topology.devices]


@app.get("/api/inventory/devices/{device_id}")
def get_device(device_id: str):
    try:
        return topology.device(device_id).model_dump()
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Device {device_id} not found")


# --------------------------------------------------------------------------- #
# 2. Alarms & Ingestion (Req 3, 4, 5)
# --------------------------------------------------------------------------- #
@app.get("/api/alarms/scenarios")
def list_scenarios():
    """List available simulated fault and alarm scenarios."""
    scenarios_dir = DATA_DIR / "alarms"
    scenarios = []
    for f in scenarios_dir.glob("*.json"):
        data = json.loads(f.read_text())
        scenarios.append({
            "filename": f.name,
            "scenario_id": data.get("scenario_id", f.stem),
            "description": data.get("description", ""),
            "alarm_count": len(data.get("alarms", data.get("raw_events", [])))
        })
    return scenarios


@app.get("/api/alarms")
def get_alarms():
    """Returns all ingested alarms."""
    return [a.model_dump() for a in alarms_db]


@app.post("/api/alarms/ingest")
def ingest_alarms(req: IngestAlarmsRequest):
    """Normalize raw events and trigger multi-agent pipeline."""
    normalized_events = workflow.intake_agent.process_events(req.raw_events)
    alarms_db.extend(normalized_events)

    # Initial incident state
    initial_state = IncidentState(
        incident_id=req.incident_id or f"INC-NET-{len(incidents_db) + 1:03d}",
        events=normalized_events
    )

    # Run multi-agent pipeline
    processed_state = workflow.run(initial_state)
    incidents_db[processed_state.incident_id] = processed_state

    return processed_state.model_dump()


@app.post("/api/incidents/run-scenario/{scenario_filename}")
def run_scenario(scenario_filename: str):
    """Load a predefined scenario file and process it through all agents."""
    scenario_path = DATA_DIR / "alarms" / scenario_filename
    if not scenario_path.exists():
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_filename} not found")

    data = json.loads(scenario_path.read_text())

    # Some files use "alarms" (simulated), some use "raw_events" (vendor format)
    if "raw_events" in data:
        normalized_events = workflow.intake_agent.process_events(data["raw_events"])
    elif "alarms" in data:
        normalized_events = [NormalizedEvent.from_alarm_dict(a) for a in data["alarms"]]
    else:
        raise HTTPException(status_code=400, detail="Invalid scenario schema")

    alarms_db.extend(normalized_events)

    incident_id = data.get("expected", {}).get("incident_id_example", f"INC-NET-{len(incidents_db) + 101}")
    state = IncidentState(incident_id=incident_id, events=normalized_events)

    processed_state = workflow.run(state)
    incidents_db[processed_state.incident_id] = processed_state

    return processed_state.model_dump()


# --------------------------------------------------------------------------- #
# 3. Incident Management & Trace (Req 8, 9, 10, 11, 12, 19)
# --------------------------------------------------------------------------- #
@app.get("/api/incidents")
def list_incidents():
    """Returns list of active and historical incidents."""
    return [
        {
            "incident_id": inc.incident_id,
            "status": inc.status.value,
            "revision": inc.revision,
            "alarm_count": len(inc.events),
            "primary_alarms": inc.correlation.primary_event_ids if inc.correlation else [],
            "top_suspect": inc.fault_hypotheses[0].suspect_id if inc.fault_hypotheses else None,
            "root_cause": inc.confirmed_root_cause.value if inc.confirmed_root_cause else (inc.rca_hypotheses[0].category.value if inc.rca_hypotheses else "Undetermined"),
            "created_at": inc.created_at,
            "updated_at": inc.updated_at
        }
        for inc in incidents_db.values()
    ]


@app.get("/api/incidents/{incident_id}")
def get_incident(incident_id: str):
    """Returns complete state, hypotheses, impact, actions, and agent trace."""
    if incident_id not in incidents_db:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    return incidents_db[incident_id].model_dump()


@app.post("/api/incidents/{incident_id}/reassess")
def reassess_incident(incident_id: str, raw_event: Dict[str, Any]):
    """Dynamic reassessment when a new alarm arrives during an active incident (TC-08)."""
    if incident_id not in incidents_db:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")

    state = incidents_db[incident_id]
    new_event = workflow.intake_agent.process_event(raw_event)

    belongs, updated_state = workflow_service.handle_incoming_alarm(state, new_event)
    incidents_db[incident_id] = updated_state

    return {
        "belongs_to_incident": belongs,
        "incident": updated_state.model_dump()
    }


# --------------------------------------------------------------------------- #
# 4. Human Approval Workflow & Action Tracking (Req 13, 14, 15)
# --------------------------------------------------------------------------- #
@app.post("/api/incidents/{incident_id}/actions/{action_id}/approve")
def approve_action(incident_id: str, action_id: str, req: ActionApprovalRequest):
    if incident_id not in incidents_db:
        raise HTTPException(status_code=404, detail="Incident not found")
    state = incidents_db[incident_id]
    actor = Actor(name=req.engineer_name, role=ActorRole.ENGINEER)

    try:
        workflow_service.approve_action(state, action_id, actor, explicit=req.explicit_authorization)
        return state.model_dump()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/incidents/{incident_id}/actions/{action_id}/reject")
def reject_action(incident_id: str, action_id: str, req: ActionRejectRequest):
    if incident_id not in incidents_db:
        raise HTTPException(status_code=404, detail="Incident not found")
    state = incidents_db[incident_id]
    actor = Actor(name=req.engineer_name, role=ActorRole.ENGINEER)

    try:
        workflow_service.reject_action(state, action_id, actor, reason=req.reason)
        return state.model_dump()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/incidents/{incident_id}/actions/{action_id}/modify")
def modify_action(incident_id: str, action_id: str, req: ActionModifyRequest):
    if incident_id not in incidents_db:
        raise HTTPException(status_code=404, detail="Incident not found")
    state = incidents_db[incident_id]
    actor = Actor(name=req.engineer_name, role=ActorRole.ENGINEER)

    try:
        workflow_service.modify_action(state, action_id, actor, req.new_description, req.comment)
        return state.model_dump()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/incidents/{incident_id}/actions/{action_id}/start")
def start_action(incident_id: str, action_id: str, req: ActionTransitionRequest):
    if incident_id not in incidents_db:
        raise HTTPException(status_code=404, detail="Incident not found")
    state = incidents_db[incident_id]
    actor = Actor(name=req.engineer_name, role=ActorRole.ENGINEER)

    try:
        workflow_service.start_action(state, action_id, actor)
        return state.model_dump()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/incidents/{incident_id}/actions/{action_id}/complete")
def complete_action(incident_id: str, action_id: str, req: ActionTransitionRequest):
    if incident_id not in incidents_db:
        raise HTTPException(status_code=404, detail="Incident not found")
    state = incidents_db[incident_id]
    actor = Actor(name=req.engineer_name, role=ActorRole.ENGINEER)

    try:
        workflow_service.complete_action(state, action_id, actor, result=req.result or "Executed successfully")
        return state.model_dump()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/incidents/{incident_id}/confirm-root-cause")
def confirm_root_cause(incident_id: str, req: ConfirmRootCauseRequest):
    if incident_id not in incidents_db:
        raise HTTPException(status_code=404, detail="Incident not found")
    state = incidents_db[incident_id]
    actor = Actor(name=req.engineer_name, role=ActorRole.ENGINEER)

    try:
        state.confirm_root_cause(actor, req.category, req.verification_note)
        return state.model_dump()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# --------------------------------------------------------------------------- #
# 5. Post-Restoration Validation (Req 16 / TC-07)
# --------------------------------------------------------------------------- #
@app.post("/api/incidents/{incident_id}/validate")
def validate_restoration(incident_id: str):
    if incident_id not in incidents_db:
        raise HTTPException(status_code=404, detail="Incident not found")
    state = incidents_db[incident_id]

    validation = workflow_service.run_post_restoration_validation(state)
    return {
        "validation": validation.model_dump(),
        "incident": state.model_dump()
    }


# --------------------------------------------------------------------------- #
# 6. PDF Incident Report Download (Req 20)
# --------------------------------------------------------------------------- #
@app.get("/api/incidents/{incident_id}/report.pdf")
def download_pdf_report(incident_id: str):
    if incident_id not in incidents_db:
        raise HTTPException(status_code=404, detail="Incident not found")
    state = incidents_db[incident_id]

    pdf_bytes = workflow_service.generate_pdf_report(state)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=incident_report_{incident_id}.pdf"}
    )


# --------------------------------------------------------------------------- #
# 7. Telemetry & Performance Monitoring (Req 6)
# --------------------------------------------------------------------------- #
@app.get("/api/telemetry")
def get_telemetry(entity_id: Optional[str] = None, limit: int = 100):
    eval_csv = DATA_DIR / "telemetry" / "telemetry_eval.csv"
    if not eval_csv.exists():
        return []

    df = pd.read_csv(eval_csv)
    if entity_id:
        df = df[df["entity_id"] == entity_id]

    records = df.head(limit).fillna("").to_dict(orient="records")
    return records


# --------------------------------------------------------------------------- #
# 8. Knowledge Base: SOPs and Historical Incidents (Req 10 & 11)
# --------------------------------------------------------------------------- #
@app.get("/api/knowledge/sops")
def get_sops():
    return [
        {"doc_id": sop_id, "content": content}
        for sop_id, content in workflow.restoration_agent.sops.items()
    ]


@app.get("/api/knowledge/incidents")
def get_historical_incidents():
    incidents_file = DATA_DIR / "incidents.json"
    if not incidents_file.exists():
        return []
    data = json.loads(incidents_file.read_text())
    return data.get("incidents", [])


# Health check
@app.get("/health")
def health():
    return {"status": "ok", "app": "Telecom NOC Decision Support Platform"}
