from fastapi.testclient import TestClient
import pytest

from app.main import app

client = TestClient(app)


def test_api_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_api_topology():
    res = client.get("/api/topology")
    assert res.status_code == 200
    data = res.json()
    assert "devices" in data
    assert "links" in data
    assert len(data["devices"]) == 11


def test_api_devices():
    res = client.get("/api/inventory/devices")
    assert res.status_code == 200
    devices = res.json()
    assert len(devices) == 11
    assert any(d["device_id"] == "AR-01" for d in devices)

    res_single = client.get("/api/inventory/devices/AR-01")
    assert res_single.status_code == 200
    assert res_single.json()["name"] == "AR-01"


def test_api_run_scenario_and_actions():
    # 1. Trigger scenario run
    res = client.post("/api/incidents/run-scenario/scenario_cascade.json")
    assert res.status_code == 200
    incident = res.json()
    inc_id = incident["incident_id"]
    assert inc_id is not None
    assert incident["status"] == "awaiting_approval"
    assert len(incident["actions"]) > 0

    # 2. Get incident by ID
    res_get = client.get(f"/api/incidents/{inc_id}")
    assert res_get.status_code == 200
    assert res_get.json()["incident_id"] == inc_id

    # 3. Approve first action
    first_action = incident["actions"][0]
    act_id = first_action["action_id"]
    is_disruptive = (first_action["category"] == "potentially_disruptive")

    res_app = client.post(
        f"/api/incidents/{inc_id}/actions/{act_id}/approve",
        json={"engineer_name": "Bob NOC", "explicit_authorization": is_disruptive}
    )
    assert res_app.status_code == 200
    updated_inc = res_app.json()
    act = next(a for a in updated_inc["actions"] if a["action_id"] == act_id)
    assert act["status"] == "approved"

    # 4. Start action
    res_start = client.post(
        f"/api/incidents/{inc_id}/actions/{act_id}/start",
        json={"engineer_name": "Bob NOC"}
    )
    assert res_start.status_code == 200

    # 5. Complete action
    res_comp = client.post(
        f"/api/incidents/{inc_id}/actions/{act_id}/complete",
        json={"engineer_name": "Bob NOC", "result": "Cable replaced"}
    )
    assert res_comp.status_code == 200

    # 6. Post-restoration validation
    res_val = client.post(f"/api/incidents/{inc_id}/validate")
    assert res_val.status_code == 200
    assert res_val.json()["validation"]["all_passed"] is True

    # 7. Download PDF Report
    res_pdf = client.get(f"/api/incidents/{inc_id}/report.pdf")
    assert res_pdf.status_code == 200
    assert res_pdf.headers["content-type"] == "application/pdf"
    assert res_pdf.content.startswith(b"%PDF")
