// API client for Telecom NOC Backend
const API_BASE = '/api';

export interface Device {
  device_id: string;
  name: string;
  device_type: string;
  region: string;
  ip_address: string;
  vendor: string;
  model: string;
  operational_status: string;
  interfaces: any[];
  connected_devices: string[];
  supported_services: string[];
}

export interface Link {
  link_id: string;
  endpoint_a: { device: string; interface: string };
  endpoint_b: { device: string; interface: string };
  link_type: string;
  capacity_mbps: number;
  status: string;
  redundancy_group: string | null;
}

export interface Service {
  service_id: string;
  name: string;
  service_type: string;
  endpoint_device: string;
  region: string;
  priority: string;
  redundancy: string;
  customer_count: number | null;
}

export interface TopologyData {
  network_name: string;
  version: string;
  devices: Device[];
  links: Link[];
  services: Service[];
}

export interface NormalizedEvent {
  event_id: string;
  timestamp: string;
  device: string;
  device_type?: string;
  event_type: string;
  interface?: string;
  severity: string;
  description: string;
  status: string;
  source_format?: string;
}

export interface AgentTraceEntry {
  agent: string;
  started_at: string;
  finished_at: string;
  input_summary: string;
  output_summary: string;
  status: string;
}

export interface RestorationAction {
  action_id: string;
  incident_id: string;
  description: string;
  category: 'diagnostic' | 'non_disruptive' | 'potentially_disruptive' | 'escalation_required';
  rationale: string;
  sop_reference?: string;
  status: 'proposed' | 'approved' | 'rejected' | 'in_progress' | 'completed' | 'verified';
  requires_approval: boolean;
  assigned_to?: string;
  approved_by?: string;
  explicit_authorization: boolean;
  result?: string;
  remarks: string[];
}

export interface IncidentState {
  incident_id: string;
  created_at: string;
  updated_at: string;
  status: string;
  revision: number;
  current_agent?: string;
  events: NormalizedEvent[];
  correlation?: {
    roles: Record<string, string>;
    primary_event_ids: string[];
    duplicate_of: Record<string, string>;
    storm_detected: boolean;
    time_window_seconds: number;
    rationale: string[];
  };
  fault_hypotheses: Array<{
    rank: number;
    suspect_id: string;
    suspect_kind: string;
    confidence: string;
    confidence_score?: number;
    supporting_alarm_ids: string[];
    topology_evidence: string[];
    summary: string;
  }>;
  anomalies: Array<{
    entity_id: string;
    anomaly_score: number;
    is_anomalous: boolean;
    metrics: Array<{
      metric: string;
      normal?: number;
      current?: number;
      unit: string;
    }>;
    notes: string;
  }>;
  service_impact?: {
    affected_devices: string[];
    unconfirmed_devices: string[];
    affected_links: string[];
    services: Array<{
      service_id: string;
      state: string;
      confirmed: boolean;
      redundancy_available: boolean;
      reason: string;
    }>;
    customer_count?: number | null;
    summary: string;
  };
  historical_matches: Array<{
    incident_id: string;
    similarity: number;
    root_cause_category: string;
    caveat: string;
  }>;
  rca_hypotheses: Array<{
    rank: number;
    category: string;
    description: string;
    confidence: string;
    confidence_score?: number;
    supporting_evidence: Array<{ source: string; reference: string; statement: string }>;
    required_verification: string[];
  }>;
  confirmed_root_cause?: string;
  confirmed_root_cause_note?: string;
  confirmed_by?: string;
  actions: RestorationAction[];
  reviewer_findings: Array<{
    check: string;
    passed: boolean;
    message: string;
  }>;
  validation?: {
    performed_at: string;
    all_passed: boolean;
    checks: Array<{
      name: string;
      passed: boolean;
      before?: any;
      after?: any;
      detail: string;
    }>;
  };
  trace: AgentTraceEntry[];
}

export const api = {
  getTopology: async (): Promise<TopologyData> => {
    const res = await fetch(`${API_BASE}/topology`);
    return res.json();
  },
  getScenarios: async () => {
    const res = await fetch(`${API_BASE}/alarms/scenarios`);
    return res.json();
  },
  runScenario: async (filename: string): Promise<IncidentState> => {
    const res = await fetch(`${API_BASE}/incidents/run-scenario/${filename}`, { method: 'POST' });
    return res.json();
  },
  getIncidents: async () => {
    const res = await fetch(`${API_BASE}/incidents`);
    return res.json();
  },
  getIncident: async (id: string): Promise<IncidentState> => {
    const res = await fetch(`${API_BASE}/incidents/${id}`);
    return res.json();
  },
  approveAction: async (incidentId: string, actionId: string, engineerName: string, explicit: boolean) => {
    const res = await fetch(`${API_BASE}/incidents/${incidentId}/actions/${actionId}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ engineer_name: engineerName, explicit_authorization: explicit })
    });
    return res.json();
  },
  startAction: async (incidentId: string, actionId: string, engineerName: string) => {
    const res = await fetch(`${API_BASE}/incidents/${incidentId}/actions/${actionId}/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ engineer_name: engineerName })
    });
    return res.json();
  },
  completeAction: async (incidentId: string, actionId: string, engineerName: string, result: string) => {
    const res = await fetch(`${API_BASE}/incidents/${incidentId}/actions/${actionId}/complete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ engineer_name: engineerName, result })
    });
    return res.json();
  },
  validateRestoration: async (incidentId: string) => {
    const res = await fetch(`${API_BASE}/incidents/${incidentId}/validate`, { method: 'POST' });
    return res.json();
  },
  getTelemetry: async (entityId?: string, limit: number = 50) => {
    const url = entityId ? `${API_BASE}/telemetry?entity_id=${entityId}&limit=${limit}` : `${API_BASE}/telemetry?limit=${limit}`;
    const res = await fetch(url);
    return res.json();
  },
  getSOPs: async () => {
    const res = await fetch(`${API_BASE}/knowledge/sops`);
    return res.json();
  },
  getHistoricalIncidents: async () => {
    const res = await fetch(`${API_BASE}/knowledge/incidents`);
    return res.json();
  }
};
