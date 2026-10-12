from datetime import datetime
from typing import Any, Dict, List, Optional
from langgraph.graph import StateGraph, END

from app.models.enums import AgentName, IncidentStatus
from app.models.incident import AgentTraceEntry, IncidentState, ToolCall
from app.models.network import Topology
from app.agents.intake import IntakeAgent
from app.agents.correlation import CorrelationAgent
from app.agents.localization import LocalizationAgent
from app.agents.anomaly import AnomalyAgent
from app.agents.impact import ImpactAgent
from app.agents.rca import RCAAgent
from app.agents.restoration import RestorationAgent
from app.agents.reviewer import ReviewerAgent


class NetworkNOCWorkflow:
    """End-to-end multi-agent orchestration for network incident diagnosis and restoration."""

    def __init__(self, topology: Topology, data_dir: str):
        self.topology = topology
        self.data_dir = data_dir

        self.intake_agent = IntakeAgent(topology)
        self.correlation_agent = CorrelationAgent(topology)
        self.localization_agent = LocalizationAgent(topology)
        self.anomaly_agent = AnomalyAgent(topology, f"{data_dir}/telemetry" if not data_dir.endswith("telemetry") else data_dir)
        self.impact_agent = ImpactAgent(topology)
        self.rca_agent = RCAAgent(topology, data_dir)
        self.restoration_agent = RestorationAgent(data_dir)
        self.reviewer_agent = ReviewerAgent()

        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(IncidentState)

        builder.add_node("correlate_alarms", self._correlation_node)
        builder.add_node("localize_fault", self._localization_node)
        builder.add_node("detect_anomalies", self._anomaly_node)
        builder.add_node("analyze_service_impact", self._impact_node)
        builder.add_node("analyze_root_cause", self._rca_node)
        builder.add_node("plan_restoration", self._restoration_node)
        builder.add_node("review_safety", self._reviewer_node)

        builder.set_entry_point("correlate_alarms")
        builder.add_edge("correlate_alarms", "localize_fault")
        builder.add_edge("localize_fault", "detect_anomalies")
        builder.add_edge("detect_anomalies", "analyze_service_impact")
        builder.add_edge("analyze_service_impact", "analyze_root_cause")
        builder.add_edge("analyze_root_cause", "plan_restoration")
        builder.add_edge("plan_restoration", "review_safety")
        builder.add_edge("review_safety", END)

        return builder.compile()

    def _correlation_node(self, state: IncidentState) -> Dict[str, Any]:
        start = datetime.now()
        corr_res = self.correlation_agent.correlate(state.events)
        
        trace = AgentTraceEntry(
            agent=AgentName.CORRELATION,
            started_at=start,
            finished_at=datetime.now(),
            input_summary=f"Correlating {len(state.events)} alarms",
            output_summary=f"Identified {len(corr_res.primary_event_ids)} primary, {corr_res.count(corr_res.roles.get('consequential', 'consequential'))} consequential events. Storm: {corr_res.storm_detected}"
        )
        return {
            "correlation": corr_res,
            "status": IncidentStatus.DIAGNOSING,
            "current_agent": AgentName.CORRELATION,
            "trace": state.trace + [trace]
        }

    def _localization_node(self, state: IncidentState) -> Dict[str, Any]:
        start = datetime.now()
        hypotheses = self.localization_agent.localize(state.events, state.correlation)

        trace = AgentTraceEntry(
            agent=AgentName.LOCALIZATION,
            started_at=start,
            finished_at=datetime.now(),
            input_summary=f"Localizing fault for {len(state.correlation.primary_event_ids)} primary alarms",
            output_summary=f"Formulated {len(hypotheses)} hypotheses. Top suspect: {hypotheses[0].suspect_id if hypotheses else 'None'}"
        )
        return {
            "fault_hypotheses": hypotheses,
            "current_agent": AgentName.LOCALIZATION,
            "trace": state.trace + [trace]
        }

    def _anomaly_node(self, state: IncidentState) -> Dict[str, Any]:
        start = datetime.now()
        findings = self.anomaly_agent.analyze(state.events, state.correlation)

        trace = AgentTraceEntry(
            agent=AgentName.ANOMALY,
            started_at=start,
            finished_at=datetime.now(),
            input_summary=f"Running Isolation Forest on telemetry for {len(state.events)} events",
            output_summary=f"Detected {len(findings)} anomalous entities"
        )
        return {
            "anomalies": findings,
            "current_agent": AgentName.ANOMALY,
            "trace": state.trace + [trace]
        }

    def _impact_node(self, state: IncidentState) -> Dict[str, Any]:
        start = datetime.now()
        impact = self.impact_agent.analyze(state.events, state.correlation, state.fault_hypotheses)

        trace = AgentTraceEntry(
            agent=AgentName.SERVICE_IMPACT,
            started_at=start,
            finished_at=datetime.now(),
            input_summary="Analyzing topological service dependencies",
            output_summary=impact.summary
        )
        return {
            "service_impact": impact,
            "current_agent": AgentName.SERVICE_IMPACT,
            "trace": state.trace + [trace]
        }

    def _rca_node(self, state: IncidentState) -> Dict[str, Any]:
        start = datetime.now()
        matches, rca_hypotheses = self.rca_agent.analyze(
            state.events, state.correlation, state.fault_hypotheses, state.anomalies
        )

        trace = AgentTraceEntry(
            agent=AgentName.ROOT_CAUSE,
            started_at=start,
            finished_at=datetime.now(),
            input_summary="Executing TF-IDF RAG over historical incidents database",
            output_summary=f"Retrieved {len(matches)} historical matches. Top RCA: {rca_hypotheses[0].category.value if rca_hypotheses else 'None'}"
        )
        return {
            "historical_matches": matches,
            "rca_hypotheses": rca_hypotheses,
            "current_agent": AgentName.ROOT_CAUSE,
            "trace": state.trace + [trace]
        }

    def _restoration_node(self, state: IncidentState) -> Dict[str, Any]:
        start = datetime.now()
        actions = self.restoration_agent.plan(state.incident_id, state.rca_hypotheses, state.service_impact)

        trace = AgentTraceEntry(
            agent=AgentName.RESTORATION,
            started_at=start,
            finished_at=datetime.now(),
            input_summary=f"Retrieving standard operating procedures (SOPs) for RCA {state.rca_hypotheses[0].category.value if state.rca_hypotheses else 'None'}",
            output_summary=f"Proposed {len(actions)} restoration actions across risk categories"
        )
        return {
            "actions": actions,
            "current_agent": AgentName.RESTORATION,
            "trace": state.trace + [trace]
        }

    def _reviewer_node(self, state: IncidentState) -> Dict[str, Any]:
        start = datetime.now()
        findings = self.reviewer_agent.review(state)

        trace = AgentTraceEntry(
            agent=AgentName.REVIEWER,
            started_at=start,
            finished_at=datetime.now(),
            input_summary="Verifying evidence alignment, policy gates, and hallucination checks",
            output_summary=f"{sum(1 for f in findings if f.passed)}/{len(findings)} checks passed"
        )
        return {
            "reviewer_findings": findings,
            "status": IncidentStatus.AWAITING_APPROVAL,
            "current_agent": AgentName.REVIEWER,
            "trace": state.trace + [trace]
        }

    def run(self, state: IncidentState) -> IncidentState:
        """Run the end-to-end workflow on an incident."""
        result_dict = self.graph.invoke(state)
        if isinstance(result_dict, IncidentState):
            return result_dict
        return IncidentState.model_validate(result_dict)
