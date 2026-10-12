import json
from pathlib import Path
from typing import List, Dict, Any, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.models.enums import RootCauseCategory, Confidence, EvidenceSource, EventType
from app.models.network import Topology, NormalizedEvent, HistoricalIncidentRecord
from app.models.incident import CorrelationResult, FaultLocationHypothesis, ServiceImpact, HistoricalMatch, RCAHypothesis, Evidence

class RCAAgent:
    """Agent 6 - Root Cause Analysis & Troubleshooting Agent
    Investigates the probable cause of the network incident by retrieving historical matches (RAG)
    and synthesizing hypotheses from alarms, telemetry, and topology.
    """
    def __init__(self, topology: Topology, data_dir: str):
        self.topology = topology
        self.data_dir = Path(data_dir)
        self.historical_incidents = self._load_historical()
        
        # Build TF-IDF for RAG
        if self.historical_incidents:
            corpus = [
                f"{inc.root_cause_category.value} {' '.join(inc.alarm_pattern)} {inc.topology_pattern} {inc.precursors}"
                for inc in self.historical_incidents
            ]
            self.vectorizer = TfidfVectorizer(stop_words='english')
            self.tfidf_matrix = self.vectorizer.fit_transform(corpus)
        else:
            self.vectorizer = None
            self.tfidf_matrix = None

    def _load_historical(self) -> List[HistoricalIncidentRecord]:
        path = self.data_dir / "incidents.json"
        if not path.exists():
            return []
        data = json.loads(path.read_text())
        return [HistoricalIncidentRecord.model_validate(i) for i in data["incidents"]]

    def retrieve_historical_matches(self, query_text: str, top_k: int = 2) -> List[HistoricalMatch]:
        if not self.vectorizer or not query_text.strip():
            return []
            
        query_vec = self.vectorizer.transform([query_text])
        similarities = cosine_similarity(query_vec, self.tfidf_matrix)[0]
        
        matches = []
        for idx in similarities.argsort()[::-1][:top_k]:
            sim = float(similarities[idx])
            if sim > 0.1:  # threshold
                inc = self.historical_incidents[idx]
                matches.append(HistoricalMatch(
                    incident_id=inc.incident_id,
                    similarity=round(sim, 3),
                    matched_on=["Alarm pattern and topology similarity via TF-IDF"],
                    root_cause_category=inc.root_cause_category,
                    caveat="Historical evidence only; it does not establish the current root cause."
                ))
        return matches

    def analyze(self, 
                events: List[NormalizedEvent], 
                correlation: CorrelationResult, 
                hypotheses: List[FaultLocationHypothesis], 
                anomalies: list) -> Tuple[List[HistoricalMatch], List[RCAHypothesis]]:
                    
        if not hypotheses:
            return [], []
            
        # 1. Build query text for RAG
        top_loc = hypotheses[0]
        primary_events = [e for e in events if e.event_id in correlation.primary_event_ids]
        
        alarm_types = " ".join(e.event_type.value for e in primary_events)
        conseq_types = " ".join(e.event_type.value for e in events if e.event_id not in correlation.primary_event_ids)
        topo_desc = f"{top_loc.suspect_kind} failure"
        
        query_text = f"{alarm_types} {conseq_types} {topo_desc}"
        
        # Extract anomalies context
        has_congestion = False
        has_sensor_issue = False
        for a in anomalies:
            if "congestion" in a.notes.lower() or a.metrics:
                for m in a.metrics:
                    if "utilization" in m.metric:
                        has_congestion = True
            if a.suspected_sensor_issue:
                has_sensor_issue = True
                
        if has_congestion:
            query_text += " utilization_high packet_loss_high network_congestion"
        if has_sensor_issue:
            query_text += " cpu_high telemetry_sensor_issue"
            
        # 2. Retrieve history
        matches = self.retrieve_historical_matches(query_text)
        
        # 3. Generate RCA hypotheses
        rca_hypotheses = []
        rank = 1
        
        primary_event_types = {e.event_type for e in primary_events}
        
        # Rule-based fallback mimicking LLM reasoning
        if has_sensor_issue:
            rca_hypotheses.append(RCAHypothesis(
                rank=rank,
                category=RootCauseCategory.TELEMETRY_SENSOR_ISSUE,
                description="The monitoring agent or sensor is stuck, sending artificial metric values.",
                supporting_evidence=[
                    Evidence(source=EvidenceSource.TELEMETRY, reference="AnomalyAgent", statement="Metrics flatlined at 100% or 0% with no corresponding traffic impact.")
                ],
                contradicting_evidence=[],
                confidence=Confidence.HIGH,
                confidence_score=0.9,
                required_verification=["Log into the device directly to check real CPU/Memory", "Restart the SNMP/telemetry agent"]
            ))
            rank += 1
            
        if has_congestion:
            rca_hypotheses.append(RCAHypothesis(
                rank=rank,
                category=RootCauseCategory.NETWORK_CONGESTION,
                description="Traffic shifted to a redundant link causing severe congestion and packet loss.",
                supporting_evidence=[
                    Evidence(source=EvidenceSource.TELEMETRY, reference="AnomalyAgent", statement="High utilization and packet loss detected on the link."),
                    Evidence(source=EvidenceSource.TOPOLOGY, reference="Topology", statement="The degraded link is part of a redundancy group where another link recently failed.")
                ],
                contradicting_evidence=[],
                confidence=Confidence.HIGH,
                confidence_score=0.95,
                required_verification=["Verify interface traffic counters", "Check routing tables to confirm traffic shift"]
            ))
            rank += 1
            
        if EventType.INTERFACE_DOWN in primary_event_types or EventType.LINK_FLAP in primary_event_types:
            # Could be physical or hardware
            rca_hypotheses.append(RCAHypothesis(
                rank=rank,
                category=RootCauseCategory.PHYSICAL_LINK_FAILURE,
                description="Physical fiber cut, unplugged cable, or optical failure.",
                supporting_evidence=[
                    Evidence(source=EvidenceSource.ALARM, reference=primary_events[0].event_id, statement="Interface transitioned to down state."),
                    Evidence(source=EvidenceSource.TOPOLOGY, reference=top_loc.suspect_id, statement="The topology confirms this link is the single point of failure for downstream devices.")
                ],
                contradicting_evidence=[],
                confidence=Confidence.HIGH if not has_congestion else Confidence.MEDIUM, # High confidence unless it's just congestion
                confidence_score=0.85,
                required_verification=["Check optical receive power levels (DOM/DDM)", "Perform OTDR test on fiber"]
            ))
            rank += 1
            
        if EventType.POWER_SUPPLY_FAILURE in primary_event_types or EventType.DEVICE_UNREACHABLE in primary_event_types:
            rca_hypotheses.append(RCAHypothesis(
                rank=rank,
                category=RootCauseCategory.POWER_FAILURE,
                description="Complete site power failure or device power supply failure.",
                supporting_evidence=[
                    Evidence(source=EvidenceSource.ALARM, reference=primary_events[0].event_id, statement="Device unreachable or explicit power supply alarm.")
                ],
                contradicting_evidence=[],
                confidence=Confidence.HIGH,
                confidence_score=0.9,
                required_verification=["Verify site mains power status", "Check remote console access"]
            ))
            rank += 1

        # Use historical match to boost or add a hypothesis
        if matches:
            top_match = matches[0]
            # Check if we already have this category
            existing = [h for h in rca_hypotheses if h.category == top_match.root_cause_category]
            if existing:
                existing[0].supporting_evidence.append(
                    Evidence(source=EvidenceSource.HISTORICAL_INCIDENT, reference=top_match.incident_id, statement=f"Matches past incident {top_match.incident_id} ({top_match.similarity*100:.0f}% similar)")
                )
            else:
                rca_hypotheses.append(RCAHypothesis(
                    rank=rank,
                    category=top_match.root_cause_category,
                    description=f"Inferred from historical incident {top_match.incident_id}.",
                    supporting_evidence=[
                        Evidence(source=EvidenceSource.HISTORICAL_INCIDENT, reference=top_match.incident_id, statement=f"Matches past incident {top_match.incident_id} ({top_match.similarity*100:.0f}% similar)")
                    ],
                    contradicting_evidence=[],
                    confidence=Confidence.MEDIUM,
                    confidence_score=0.6,
                    required_verification=["Verify via standard diagnostic procedures for this category"]
                ))
                
        if not rca_hypotheses:
            rca_hypotheses.append(RCAHypothesis(
                rank=1,
                category=RootCauseCategory.UNKNOWN,
                description="No definitive root cause identified from available evidence.",
                supporting_evidence=[],
                contradicting_evidence=[],
                confidence=Confidence.LOW,
                confidence_score=0.1,
                required_verification=["Escalate to Tier 3 engineering for deep log analysis"]
            ))
            
        # Re-sort and re-rank
        rca_hypotheses.sort(key=lambda x: x.confidence_score or 0.0, reverse=True)
        for i, h in enumerate(rca_hypotheses):
            h.rank = i + 1
            
        return matches, rca_hypotheses
