import { useState, useEffect } from 'react';
import {
  Activity, AlertTriangle, CheckCircle, ShieldCheck, FileText,
  Network, Server, Cpu, Database, Play, Check, Download,
  Layers, ChevronRight, Terminal, BarChart2, Radio
} from 'lucide-react';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend
} from 'recharts';
import { api } from './api';
import type { TopologyData, IncidentState } from './api';

export default function App() {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'topology' | 'incidents' | 'approvals' | 'telemetry' | 'knowledge'>('dashboard');
  const [topology, setTopology] = useState<TopologyData | null>(null);
  const [selectedIncident, setSelectedIncident] = useState<IncidentState | null>(null);
  const [incidents, setIncidents] = useState<any[]>([]);
  const [scenarios, setScenarios] = useState<any[]>([]);
  const [telemetryData, setTelemetryData] = useState<any[]>([]);
  const [sops, setSops] = useState<any[]>([]);
  const [historicalIncidents, setHistoricalIncidents] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [engineerName, setEngineerName] = useState<string>('NOC Engineer Lead');
  const [selectedDevice, setSelectedDevice] = useState<any | null>(null);

  const getDev = (id: string) => topology?.devices.find(d => d.device_id === id);

  // Load initial data
  useEffect(() => {
    loadInitialData();
  }, []);

  const loadInitialData = async () => {
    try {
      const [topo, scens, incs, tele, sopList, histList] = await Promise.all([
        api.getTopology(),
        api.getScenarios(),
        api.getIncidents(),
        api.getTelemetry('LNK-CR01-AR02-B', 40),
        api.getSOPs(),
        api.getHistoricalIncidents()
      ]);
      setTopology(topo);
      setScenarios(scens);
      setIncidents(incs);
      setTelemetryData(tele);
      setSops(sopList);
      setHistoricalIncidents(histList);

      if (incs.length > 0) {
        const fullInc = await api.getIncident(incs[0].incident_id);
        setSelectedIncident(fullInc);
      }
    } catch (e) {
      console.error("Error loading NOC data", e);
    }
  };

  const handleRunScenario = async (filename: string) => {
    setLoading(true);
    try {
      const inc = await api.runScenario(filename);
      setSelectedIncident(inc);
      const incList = await api.getIncidents();
      setIncidents(incList);
      setActiveTab('incidents');
    } catch (e) {
      alert("Error triggering scenario: " + e);
    } finally {
      setLoading(false);
    }
  };

  const handleApproveAction = async (actionId: string, explicit: boolean) => {
    if (!selectedIncident) return;
    try {
      const updated = await api.approveAction(selectedIncident.incident_id, actionId, engineerName, explicit);
      setSelectedIncident(updated);
    } catch (e: any) {
      alert("Action approval error: " + e.message);
    }
  };

  const handleStartAction = async (actionId: string) => {
    if (!selectedIncident) return;
    try {
      const updated = await api.startAction(selectedIncident.incident_id, actionId, engineerName);
      setSelectedIncident(updated);
    } catch (e: any) {
      alert("Error starting action: " + e.message);
    }
  };

  const handleCompleteAction = async (actionId: string) => {
    if (!selectedIncident) return;
    const res = prompt("Enter completion findings / remarks:", "Replaced SFP module and cleaned fiber connection");
    if (!res) return;
    try {
      const updated = await api.completeAction(selectedIncident.incident_id, actionId, engineerName, res);
      setSelectedIncident(updated);
    } catch (e: any) {
      alert("Error completing action: " + e.message);
    }
  };

  const handleRunValidation = async () => {
    if (!selectedIncident) return;
    setLoading(true);
    try {
      const res = await api.validateRestoration(selectedIncident.incident_id);
      setSelectedIncident(res.incident);
      alert("Post-restoration validation completed! All metric checks passed.");
    } catch (e: any) {
      alert("Validation failed: " + e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 font-sans">
      {/* Sidebar Navigation */}
      <aside className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col justify-between">
        <div>
          {/* Header */}
          <div className="p-5 border-b border-slate-800 flex items-center space-x-3">
            <Radio className="w-6 h-6 text-cyan-400 animate-pulse" />
            <div>
              <h1 className="text-sm font-bold tracking-wider text-slate-100">ANTIGRAVITY NOC</h1>
              <p className="text-xs text-slate-400">Autonomous Telco Restoration</p>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="p-3 space-y-1">
            <button
              onClick={() => setActiveTab('dashboard')}
              className={`w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${activeTab === 'dashboard' ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20' : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'}`}
            >
              <Activity className="w-4 h-4" />
              <span>NOC Dashboard</span>
            </button>

            <button
              onClick={() => setActiveTab('topology')}
              className={`w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${activeTab === 'topology' ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20' : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'}`}
            >
              <Network className="w-4 h-4" />
              <span>Network Topology</span>
            </button>

            <button
              onClick={() => setActiveTab('incidents')}
              className={`w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${activeTab === 'incidents' ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20' : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'}`}
            >
              <AlertTriangle className="w-4 h-4" />
              <span>Incident Center</span>
              {incidents.length > 0 && (
                <span className="ml-auto bg-amber-500/20 text-amber-400 text-xs px-2 py-0.5 rounded-full border border-amber-500/30">
                  {incidents.length}
                </span>
              )}
            </button>

            <button
              onClick={() => setActiveTab('approvals')}
              className={`w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${activeTab === 'approvals' ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20' : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'}`}
            >
              <ShieldCheck className="w-4 h-4" />
              <span>Approval Center</span>
              {selectedIncident && selectedIncident.actions.filter(a => a.status === 'proposed').length > 0 && (
                <span className="ml-auto bg-rose-500/20 text-rose-400 text-xs px-2 py-0.5 rounded-full border border-rose-500/30">
                  {selectedIncident.actions.filter(a => a.status === 'proposed').length}
                </span>
              )}
            </button>

            <button
              onClick={() => setActiveTab('telemetry')}
              className={`w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${activeTab === 'telemetry' ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20' : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'}`}
            >
              <BarChart2 className="w-4 h-4" />
              <span>Telemetry & Anomaly</span>
            </button>

            <button
              onClick={() => setActiveTab('knowledge')}
              className={`w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${activeTab === 'knowledge' ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20' : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'}`}
            >
              <Database className="w-4 h-4" />
              <span>Knowledge Base & SOPs</span>
            </button>
          </nav>
        </div>

        {/* User Identity / Role */}
        <div className="p-4 border-t border-slate-800 bg-slate-900/50">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-full bg-cyan-500/20 border border-cyan-500/30 flex items-center justify-center text-cyan-400 font-bold text-xs">
              ENG
            </div>
            <div className="overflow-hidden">
              <input
                type="text"
                value={engineerName}
                onChange={(e) => setEngineerName(e.target.value)}
                className="bg-transparent text-xs font-semibold text-slate-200 border-none focus:outline-none focus:ring-1 focus:ring-cyan-500 rounded px-1 w-full"
                title="Current Engineer"
              />
              <p className="text-[10px] text-slate-500 uppercase tracking-wider">Level-3 Controller</p>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content Pane */}
      <main className="flex-1 overflow-y-auto bg-slate-950 p-6">
        {/* Top Header / Status Banner */}
        <div className="flex items-center justify-between pb-6 border-b border-slate-800">
          <div>
            <h2 className="text-xl font-bold text-white capitalize">{activeTab}</h2>
            <p className="text-xs text-slate-400">Autonomous Network Operations Center Platform</p>
          </div>

          {/* Quick Scenario Injector */}
          <div className="flex items-center space-x-2">
            <span className="text-xs text-slate-400 flex items-center space-x-1">
              <Play className="w-3 h-3 text-cyan-400" />
              <span>Inject Scenario:</span>
            </span>
            {scenarios.slice(0, 3).map((s) => (
              <button
                key={s.filename}
                disabled={loading}
                onClick={() => handleRunScenario(s.filename)}
                className="px-2.5 py-1 text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 rounded border border-slate-700 transition"
              >
                {s.scenario_id.replace('SC-', '')}
              </button>
            ))}
          </div>
        </div>

        {/* VIEW 1: NOC DASHBOARD */}
        {activeTab === 'dashboard' && (
          <div className="mt-6 space-y-6">
            {/* KPI Cards */}
            <div className="grid grid-cols-4 gap-4">
              <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl">
                <p className="text-xs text-slate-400">Network Health Score</p>
                <div className="flex items-baseline space-x-2 mt-1">
                  <span className="text-2xl font-black text-emerald-400">98.4%</span>
                  <span className="text-xs text-slate-500">Tier-1 Core Stable</span>
                </div>
              </div>
              <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl">
                <p className="text-xs text-slate-400">Active Correlated Incidents</p>
                <div className="flex items-baseline space-x-2 mt-1">
                  <span className="text-2xl font-black text-amber-400">{incidents.length}</span>
                  <span className="text-xs text-slate-500">In Diagnosis</span>
                </div>
              </div>
              <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl">
                <p className="text-xs text-slate-400">Managed Network Elements</p>
                <div className="flex items-baseline space-x-2 mt-1">
                  <span className="text-2xl font-black text-cyan-400">{topology?.devices.length || 11}</span>
                  <span className="text-xs text-slate-500">Routers & Base Stations</span>
                </div>
              </div>
              <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl">
                <p className="text-xs text-slate-400">Redundancy Health</p>
                <div className="flex items-baseline space-x-2 mt-1">
                  <span className="text-2xl font-black text-indigo-400">100%</span>
                  <span className="text-xs text-slate-500">Dual-Homed Uplinks Safe</span>
                </div>
              </div>
            </div>

            {/* Quick Actions & Scenarios */}
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-slate-200 mb-3 flex items-center space-x-2">
                <Server className="w-4 h-4 text-cyan-400" />
                <span>Simulated Network Failure Scenarios (Test Cases TC-01 to TC-08)</span>
              </h3>
              <div className="grid grid-cols-3 gap-3">
                {scenarios.map((scen) => (
                  <div key={scen.filename} className="p-3 bg-slate-800/50 border border-slate-700/50 rounded-lg flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-mono font-bold text-cyan-400">{scen.scenario_id}</span>
                        <span className="text-[10px] bg-slate-700 text-slate-300 px-1.5 py-0.5 rounded">{scen.alarm_count} Alarms</span>
                      </div>
                      <p className="text-xs text-slate-300 mt-1 line-clamp-2">{scen.description}</p>
                    </div>
                    <button
                      onClick={() => handleRunScenario(scen.filename)}
                      disabled={loading}
                      className="mt-3 w-full py-1.5 bg-cyan-600 hover:bg-cyan-500 text-white rounded text-xs font-medium transition flex items-center justify-center space-x-1"
                    >
                      <Play className="w-3 h-3" />
                      <span>Trigger Workflow</span>
                    </button>
                  </div>
                ))}
              </div>
            </div>

            {/* Active Incident Preview */}
            {selectedIncident && (
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center space-x-3">
                    <span className="px-2.5 py-1 bg-amber-500/20 text-amber-400 border border-amber-500/30 text-xs font-mono font-bold rounded">
                      {selectedIncident.incident_id}
                    </span>
                    <h4 className="text-sm font-bold text-white">Active Incident: {selectedIncident.fault_hypotheses[0]?.suspect_id || "Under Investigation"}</h4>
                  </div>
                  <button
                    onClick={() => setActiveTab('incidents')}
                    className="text-xs text-cyan-400 hover:text-cyan-300 flex items-center space-x-1 font-medium"
                  >
                    <span>Inspect Full Multi-Agent Trace</span>
                    <ChevronRight className="w-3 h-3" />
                  </button>
                </div>
                <div className="grid grid-cols-3 gap-4 text-xs">
                  <div className="p-3 bg-slate-800/40 rounded border border-slate-800">
                    <span className="text-slate-400 block mb-1">Suspected Fault Domain</span>
                    <span className="text-slate-100 font-semibold">{selectedIncident.fault_hypotheses[0]?.suspect_id}</span>
                    <p className="text-[11px] text-slate-500 mt-1">{selectedIncident.fault_hypotheses[0]?.summary}</p>
                  </div>
                  <div className="p-3 bg-slate-800/40 rounded border border-slate-800">
                    <span className="text-slate-400 block mb-1">Root Cause Hypothesis</span>
                    <span className="text-slate-100 font-semibold">{selectedIncident.rca_hypotheses[0]?.category.replace(/_/g, ' ').toUpperCase()}</span>
                    <p className="text-[11px] text-slate-500 mt-1">{selectedIncident.rca_hypotheses[0]?.description}</p>
                  </div>
                  <div className="p-3 bg-slate-800/40 rounded border border-slate-800">
                    <span className="text-slate-400 block mb-1">Service Outage Impact</span>
                    <span className="text-slate-100 font-semibold">{selectedIncident.service_impact?.summary}</span>
                    <p className="text-[11px] text-slate-500 mt-1">Confirmed elements: {selectedIncident.service_impact?.affected_devices.join(', ')}</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* VIEW 2: INTERACTIVE TOPOLOGY */}
        {activeTab === 'topology' && topology && (
          <div className="mt-6 grid grid-cols-3 gap-6">
            {/* Visual Topology Representation */}
            <div className="col-span-2 bg-slate-900 border border-slate-800 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-slate-200 mb-4 flex items-center space-x-2">
                <Network className="w-4 h-4 text-cyan-400" />
                <span>Interactive Network Topology (Core to Base Station Tree)</span>
              </h3>

              {/* Topology SVG Canvas */}
              <div className="w-full h-[520px] bg-slate-950/70 border border-slate-800 rounded-lg relative overflow-hidden flex items-center justify-center p-4">
                <svg className="w-full h-full" viewBox="0 0 700 500">
                  {/* Links */}
                  {/* GW-01 to CR-01 */}
                  <line x1="350" y1="50" x2="350" y2="130" stroke="#38BDF8" strokeWidth="3" />
                  {/* CR-01 to AR-01 */}
                  <line x1="350" y1="130" x2="200" y2="230" stroke={selectedIncident?.fault_hypotheses[0]?.suspect_id.includes('AR01') ? "#F43F5E" : "#38BDF8"} strokeWidth={selectedIncident?.fault_hypotheses[0]?.suspect_id.includes('AR01') ? "4" : "3"} strokeDasharray={selectedIncident?.fault_hypotheses[0]?.suspect_id.includes('AR01') ? "5,5" : "none"} />
                  {/* CR-01 to AR-02 (Dual links A & B) */}
                  <line x1="340" y1="130" x2="490" y2="230" stroke="#38BDF8" strokeWidth="2" />
                  <line x1="360" y1="130" x2="510" y2="230" stroke="#38BDF8" strokeWidth="2" />

                  {/* AR-01 to BS-101..103 & E-101 */}
                  <line x1="200" y1="230" x2="80" y2="380" stroke="#64748B" strokeWidth="2" />
                  <line x1="200" y1="230" x2="160" y2="380" stroke="#64748B" strokeWidth="2" />
                  <line x1="200" y1="230" x2="240" y2="380" stroke="#64748B" strokeWidth="2" />
                  <line x1="200" y1="230" x2="320" y2="380" stroke="#64748B" strokeWidth="2" />

                  {/* AR-02 to BS-201..203 */}
                  <line x1="500" y1="230" x2="430" y2="380" stroke="#64748B" strokeWidth="2" />
                  <line x1="500" y1="230" x2="500" y2="380" stroke="#64748B" strokeWidth="2" />
                  <line x1="500" y1="230" x2="570" y2="380" stroke="#64748B" strokeWidth="2" />

                  {/* Nodes */}
                  {/* Gateway */}
                  <g onClick={() => setSelectedDevice(getDev('GW-01'))} className="cursor-pointer">
                    <circle cx="350" cy="50" r="22" fill="#0F172A" stroke="#0284C7" strokeWidth="3" />
                    <text x="350" y="54" textAnchor="middle" fill="#FFFFFF" fontSize="10" fontWeight="bold">GW-01</text>
                  </g>

                  {/* Core Router */}
                  <g onClick={() => setSelectedDevice(getDev('CR-01'))} className="cursor-pointer">
                    <circle cx="350" cy="130" r="24" fill="#0F172A" stroke="#38BDF8" strokeWidth="3" />
                    <text x="350" y="134" textAnchor="middle" fill="#FFFFFF" fontSize="11" fontWeight="bold">CR-01</text>
                  </g>

                  {/* Aggregation Router 1 */}
                  <g onClick={() => setSelectedDevice(getDev('AR-01'))} className="cursor-pointer">
                    <circle cx="200" cy="230" r="22" fill="#0F172A" stroke={selectedIncident?.fault_hypotheses[0]?.suspect_id.includes('AR-01') ? "#F43F5E" : "#38BDF8"} strokeWidth="3" />
                    <text x="200" y="234" textAnchor="middle" fill="#FFFFFF" fontSize="10" fontWeight="bold">AR-01</text>
                  </g>

                  {/* Aggregation Router 2 */}
                  <g onClick={() => setSelectedDevice(getDev('AR-02'))} className="cursor-pointer">
                    <circle cx="500" cy="230" r="22" fill="#0F172A" stroke="#38BDF8" strokeWidth="3" />
                    <text x="500" y="234" textAnchor="middle" fill="#FFFFFF" fontSize="10" fontWeight="bold">AR-02</text>
                  </g>

                  {/* Base Stations under AR-01 */}
                  {['BS-101', 'BS-102', 'BS-103', 'E-101'].map((dev, i) => (
                    <g key={dev} onClick={() => setSelectedDevice(getDev(dev))} className="cursor-pointer">
                      <rect x={70 + i * 80 - 18} y="370" width="36" height="24" rx="4" fill="#0F172A" stroke={selectedIncident?.service_impact?.affected_devices.includes(dev) ? "#F43F5E" : (selectedIncident?.service_impact?.unconfirmed_devices.includes(dev) ? "#F59E0B" : "#10B981")} strokeWidth="2" />
                      <text x={70 + i * 80} y="386" textAnchor="middle" fill="#FFFFFF" fontSize="8" fontWeight="bold">{dev}</text>
                    </g>
                  ))}

                  {/* Base Stations under AR-02 */}
                  {['BS-201', 'BS-202', 'BS-203'].map((dev, i) => (
                    <g key={dev} onClick={() => setSelectedDevice(getDev(dev))} className="cursor-pointer">
                      <rect x={415 + i * 70} y="370" width="36" height="24" rx="4" fill="#0F172A" stroke="#10B981" strokeWidth="2" />
                      <text x={433 + i * 70} y="386" textAnchor="middle" fill="#FFFFFF" fontSize="8" fontWeight="bold">{dev}</text>
                    </g>
                  ))}
                </svg>
              </div>
            </div>

            {/* Device Detail Sidebar */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-slate-200 mb-3 flex items-center space-x-2">
                <Cpu className="w-4 h-4 text-cyan-400" />
                <span>Device Inspector</span>
              </h3>
              {selectedDevice ? (
                <div className="space-y-4 text-xs">
                  <div>
                    <span className="text-slate-400">Device ID:</span>
                    <p className="font-bold text-white text-base">{selectedDevice.device_id}</p>
                  </div>
                  <div>
                    <span className="text-slate-400">Type / Region:</span>
                    <p className="text-slate-200">{selectedDevice.device_type} · {selectedDevice.region}</p>
                  </div>
                  <div>
                    <span className="text-slate-400">Hardware Vendor & Model:</span>
                    <p className="text-slate-200">{selectedDevice.vendor} {selectedDevice.model}</p>
                  </div>
                  <div>
                    <span className="text-slate-400">IP Management Address:</span>
                    <p className="font-mono text-cyan-400">{selectedDevice.ip_address}</p>
                  </div>
                  <div>
                    <span className="text-slate-400">Operational Interfaces:</span>
                    <div className="mt-1 space-y-1">
                      {selectedDevice.interfaces.map((intf: any) => (
                        <div key={intf.name} className="p-1.5 bg-slate-800/60 rounded flex justify-between items-center text-[11px]">
                          <span className="font-mono text-slate-300">{intf.name}</span>
                          <span className="text-emerald-400 uppercase text-[9px] font-bold">{intf.oper_status}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div>
                    <span className="text-slate-400">Supported Business Services:</span>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {selectedDevice.supported_services.map((svc: string) => (
                        <span key={svc} className="px-2 py-0.5 bg-slate-800 text-slate-300 rounded text-[10px]">
                          {svc}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-xs text-slate-500 italic mt-10 text-center">Click on any node in the topology diagram to view its interfaces and operational telemetry.</p>
              )}
            </div>
          </div>
        )}

        {/* VIEW 3: INCIDENT CENTER & AGENT TRACE */}
        {activeTab === 'incidents' && selectedIncident && (
          <div className="mt-6 space-y-6">
            {/* Header Actions */}
            <div className="flex items-center justify-between bg-slate-900 border border-slate-800 p-4 rounded-xl">
              <div className="flex items-center space-x-4">
                <span className="px-3 py-1 bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 text-sm font-mono font-bold rounded">
                  {selectedIncident.incident_id}
                </span>
                <div>
                  <h3 className="text-sm font-bold text-white">Status: {selectedIncident.status.toUpperCase()}</h3>
                  <p className="text-xs text-slate-400">Revision #{selectedIncident.revision} · Created: {new Date(selectedIncident.created_at).toLocaleTimeString()}</p>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center space-x-2">
                <button
                  onClick={handleRunValidation}
                  disabled={loading}
                  className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-medium transition flex items-center space-x-1"
                >
                  <CheckCircle className="w-3.5 h-3.5" />
                  <span>Run Post-Validation</span>
                </button>
                <a
                  href={`/api/incidents/${selectedIncident.incident_id}/report.pdf`}
                  download
                  className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded text-xs font-medium transition flex items-center space-x-1"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Download PDF Report</span>
                </a>
              </div>
            </div>

            {/* Agent Execution Trace (Requirement 19) */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-slate-200 mb-4 flex items-center space-x-2">
                <Terminal className="w-4 h-4 text-cyan-400" />
                <span>Multi-Agent Workflow Execution Trace (LangGraph Engine)</span>
              </h3>
              <div className="space-y-3">
                {selectedIncident.trace.map((tr, idx) => (
                  <div key={idx} className="p-3 bg-slate-800/40 border border-slate-800 rounded-lg flex items-start space-x-3">
                    <div className="w-6 h-6 rounded-full bg-cyan-500/20 text-cyan-400 flex items-center justify-center text-xs font-bold mt-0.5">
                      {idx + 1}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-slate-200 uppercase tracking-wide">{tr.agent} Agent</span>
                        <span className="text-[10px] text-slate-500 font-mono">
                          {new Date(tr.started_at).toLocaleTimeString()}
                        </span>
                      </div>
                      <p className="text-xs text-slate-400 mt-0.5"><b>Input:</b> {tr.input_summary}</p>
                      <p className="text-xs text-slate-300 mt-0.5"><b>Findings:</b> {tr.output_summary}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Correlated Alarms List */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-slate-200 mb-3 flex items-center space-x-2">
                <Layers className="w-4 h-4 text-cyan-400" />
                <span>Correlated Alarms ({selectedIncident.events.length})</span>
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-800 text-slate-400 uppercase text-[10px]">
                    <tr>
                      <th className="p-2.5">Event ID</th>
                      <th className="p-2.5">Device</th>
                      <th className="p-2.5">Interface</th>
                      <th className="p-2.5">Alarm Type</th>
                      <th className="p-2.5">Correlation Role</th>
                      <th className="p-2.5">Severity</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {selectedIncident.events.map((evt) => {
                      const role = selectedIncident.correlation?.roles[evt.event_id] || 'independent';
                      return (
                        <tr key={evt.event_id} className="hover:bg-slate-800/50">
                          <td className="p-2.5 font-mono text-cyan-400">{evt.event_id}</td>
                          <td className="p-2.5 font-semibold text-white">{evt.device}</td>
                          <td className="p-2.5 text-slate-400">{evt.interface || '-'}</td>
                          <td className="p-2.5 text-slate-300">{evt.event_type}</td>
                          <td className="p-2.5">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${role === 'primary' ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30' : (role === 'duplicate' ? 'bg-slate-700 text-slate-400' : 'bg-amber-500/20 text-amber-400 border border-amber-500/30')}`}>
                              {role}
                            </span>
                          </td>
                          <td className="p-2.5 uppercase font-bold text-[10px] text-rose-400">{evt.severity}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* VIEW 4: APPROVAL CENTER & ACTION TRACKER */}
        {activeTab === 'approvals' && selectedIncident && (
          <div className="mt-6 space-y-6">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-slate-200 mb-2 flex items-center space-x-2">
                <ShieldCheck className="w-4 h-4 text-cyan-400" />
                <span>Restoration Actions & Guarded Approval Workflow (Requirements 14 & 15)</span>
              </h3>
              <p className="text-xs text-slate-400 mb-4">
                Safety Principle: All destructive and potentially disruptive actions require explicit human authorization before execution.
              </p>

              <div className="space-y-4">
                {selectedIncident.actions.map((act) => (
                  <div key={act.action_id} className="p-4 bg-slate-800/40 border border-slate-800 rounded-lg flex items-center justify-between">
                    <div className="space-y-1 max-w-xl">
                      <div className="flex items-center space-x-2">
                        <span className="font-mono text-xs text-cyan-400">{act.action_id}</span>
                        <span className={`px-2 py-0.5 text-[10px] uppercase font-bold rounded ${act.category === 'potentially_disruptive' ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30' : 'bg-slate-700 text-slate-300'}`}>
                          {act.category.replace('_', ' ')}
                        </span>
                        <span className="px-2 py-0.5 text-[10px] uppercase font-bold rounded bg-cyan-500/10 text-cyan-400">
                          {act.status}
                        </span>
                      </div>
                      <p className="text-xs text-slate-200 font-medium">{act.description}</p>
                      <p className="text-[11px] text-slate-400">{act.rationale}</p>
                      {act.approved_by && (
                        <p className="text-[10px] text-emerald-400">✓ Approved by: {act.approved_by}</p>
                      )}
                      {act.result && (
                        <p className="text-[10px] text-cyan-400">Execution Result: {act.result}</p>
                      )}
                    </div>

                    {/* State Transition Controls */}
                    <div className="flex items-center space-x-2">
                      {act.status === 'proposed' && (
                        <button
                          onClick={() => handleApproveAction(act.action_id, act.category === 'potentially_disruptive')}
                          className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-medium transition flex items-center space-x-1"
                        >
                          <Check className="w-3.5 h-3.5" />
                          <span>Approve {act.category === 'potentially_disruptive' ? '(Explicit)' : ''}</span>
                        </button>
                      )}

                      {act.status === 'approved' && (
                        <button
                          onClick={() => handleStartAction(act.action_id)}
                          className="px-3 py-1.5 bg-cyan-600 hover:bg-cyan-500 text-white rounded text-xs font-medium transition flex items-center space-x-1"
                        >
                          <Play className="w-3.5 h-3.5" />
                          <span>Start Action</span>
                        </button>
                      )}

                      {act.status === 'in_progress' && (
                        <button
                          onClick={() => handleCompleteAction(act.action_id)}
                          className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded text-xs font-medium transition flex items-center space-x-1"
                        >
                          <CheckCircle className="w-3.5 h-3.5" />
                          <span>Mark Completed</span>
                        </button>
                      )}

                      {act.status === 'completed' && (
                        <span className="text-xs text-amber-400 font-semibold px-2 py-1 bg-amber-500/10 rounded border border-amber-500/20">
                          Awaiting Post-Validation
                        </span>
                      )}

                      {act.status === 'verified' && (
                        <span className="text-xs text-emerald-400 font-semibold flex items-center space-x-1">
                          <CheckCircle className="w-4 h-4" />
                          <span>Verified Restored</span>
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* VIEW 5: TELEMETRY & PERFORMANCE MONITORING */}
        {activeTab === 'telemetry' && (
          <div className="mt-6 space-y-6">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-slate-200 mb-2 flex items-center space-x-2">
                <BarChart2 className="w-4 h-4 text-cyan-400" />
                <span>Telemetry Trends: LNK-CR01-AR02-B (Congestion Scenario Spike)</span>
              </h3>
              <p className="text-xs text-slate-400 mb-4">
                Real-time telemetry showing latency jump to 180ms and packet loss to 8.5% upon redundant link failover saturation.
              </p>

              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={telemetryData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="timestamp" stroke="#94A3B8" tickFormatter={(t) => t.substring(11, 16)} />
                    <YAxis stroke="#94A3B8" />
                    <Tooltip contentStyle={{ backgroundColor: '#0F172A', borderColor: '#334155' }} />
                    <Legend />
                    <Line type="monotone" dataKey="latency_ms" stroke="#38BDF8" name="Latency (ms)" strokeWidth={2} />
                    <Line type="monotone" dataKey="packet_loss_pct" stroke="#F43F5E" name="Packet Loss (%)" strokeWidth={2} />
                    <Line type="monotone" dataKey="utilization_pct" stroke="#F59E0B" name="Utilization (%)" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        )}

        {/* VIEW 6: KNOWLEDGE BASE & SOPS */}
        {activeTab === 'knowledge' && (
          <div className="mt-6 grid grid-cols-2 gap-6">
            {/* SOPs */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-slate-200 mb-3 flex items-center space-x-2">
                <FileText className="w-4 h-4 text-cyan-400" />
                <span>Approved Troubleshooting Procedures (SOPs)</span>
              </h3>
              <div className="space-y-3">
                {sops.map((sop) => (
                  <div key={sop.doc_id} className="p-3 bg-slate-800/40 rounded border border-slate-800">
                    <span className="text-xs font-bold text-cyan-400 font-mono">{sop.doc_id}</span>
                    <pre className="mt-2 text-[11px] text-slate-300 font-mono whitespace-pre-wrap max-h-40 overflow-y-auto bg-slate-950/60 p-2 rounded">
                      {sop.content}
                    </pre>
                  </div>
                ))}
              </div>
            </div>

            {/* Historical Incidents */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-slate-200 mb-3 flex items-center space-x-2">
                <Database className="w-4 h-4 text-cyan-400" />
                <span>Historical Incident Database (RAG Index)</span>
              </h3>
              <div className="space-y-3">
                {historicalIncidents.map((hist) => (
                  <div key={hist.incident_id} className="p-3 bg-slate-800/40 rounded border border-slate-800 text-xs">
                    <div className="flex justify-between items-center mb-1">
                      <span className="font-bold font-mono text-cyan-400">{hist.incident_id}</span>
                      <span className="text-[10px] text-slate-500">{hist.date}</span>
                    </div>
                    <p className="font-medium text-slate-200">{hist.title}</p>
                    <p className="text-[11px] text-slate-400 mt-1"><b>Root Cause:</b> {hist.confirmed_root_cause}</p>
                    <p className="text-[11px] text-emerald-400 mt-1"><b>Resolution:</b> {hist.resolution}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
