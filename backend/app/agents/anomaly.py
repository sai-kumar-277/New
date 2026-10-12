import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any
from pathlib import Path

from app.models.enums import EventRole
from app.models.network import Topology
from app.models.incident import CorrelationResult, AnomalyFinding, MetricComparison
from app.services.anomaly_model import AnomalyModel

class AnomalyAgent:
    """Agent 4 - Network Performance & Anomaly Detection Agent
    Detects abnormal network behavior using telemetry and time-series data.
    """
    def __init__(self, topology: Topology, data_dir: str):
        self.topology = topology
        self.model = AnomalyModel(data_dir)
        
        # Load telemetry evaluation dataset to simulate live stream for the incidents
        eval_file = Path(data_dir) / "telemetry_eval.csv"
        if eval_file.exists():
            self.eval_df = pd.read_csv(eval_file)
            self.eval_df["timestamp"] = pd.to_datetime(self.eval_df["timestamp"])
        else:
            self.eval_df = pd.DataFrame()

    def analyze(self, incident_events: list, correlation: CorrelationResult) -> List[AnomalyFinding]:
        """Analyze affected devices and links for anomalies during the incident window."""
        if self.eval_df.empty or not incident_events:
            return []
            
        # Determine incident time window
        start_time = min(e.timestamp for e in incident_events)
        end_time = max(e.timestamp for e in incident_events)
        
        # Expand window slightly to catch precursors or ongoing effects
        window_start = start_time - timedelta(minutes=5)
        window_end = end_time + timedelta(minutes=15)
        
        # Identify entities of interest
        entities = set()
        for e in incident_events:
            entities.add(e.device)
            
            # Find ALL links connected to this device, not just the alarmed interface
            # This allows detecting congestion on redundant links after a failover
            for link in self.topology.links:
                if link.endpoint_a.device == e.device or link.endpoint_b.device == e.device:
                    entities.add(link.link_id)
        
        # We can also add peer devices or directly connected links
        # For simplicity, we just look at the flagged entities and their links
        
        findings = []
        
        # Filter telemetry for window and entities
        mask = (self.eval_df["timestamp"] >= window_start) & \
               (self.eval_df["timestamp"] <= window_end) & \
               (self.eval_df["entity_id"].isin(entities))
               
        relevant_data = self.eval_df[mask]
        
        for entity_id, group in relevant_data.groupby("entity_id"):
            # Aggregate or look for the peak anomaly in the window
            entity_type = group.iloc[0]["entity_type"]
            baselines = self.model.baselines.get(entity_id, {})
            
            worst_score = -1.0
            worst_row = None
            is_anomalous = False
            
            for _, row in group.iterrows():
                row_dict = row.to_dict()
                pred = self.model.predict(entity_type, row_dict)
                if pred["score"] > worst_score:
                    worst_score = pred["score"]
                    worst_row = row_dict
                    is_anomalous = pred["is_anomaly"] or is_anomalous
                    
            if is_anomalous and worst_row:
                metrics = []
                suspected_sensor_issue = False
                
                # Compare metrics to baseline
                features = self.model.link_features if entity_type == "link" else self.model.device_features
                
                for f in features:
                    val = worst_row.get(f)
                    if val is None or pd.isna(val):
                        val = 0.0
                    
                    normal_val = baselines.get(f, {}).get("mean", 0.0)
                    std_val = baselines.get(f, {}).get("std", 1.0)
                    if std_val == 0:
                        std_val = 1.0
                        
                    # If it's more than 3 standard deviations away, highlight it
                    z_score = abs((val - normal_val) / std_val)
                    if z_score > 3.0:
                        metrics.append(MetricComparison(
                            metric=f,
                            normal=round(normal_val, 2),
                            current=round(val, 2),
                            unit="%" if "pct" in f else "ms" if "ms" in f else "mbps" if "mbps" in f else "count"
                        ))
                        
                # Check for sensor issues (e.g., flat 100% or 0% with no other effect)
                if entity_type == "device":
                    cpu = worst_row.get("cpu_pct", 0)
                    mem = worst_row.get("memory_pct", 0)
                    if (cpu == 100.0 or cpu == 0.0) and (mem == 100.0 or mem == 0.0):
                        suspected_sensor_issue = True
                        
                notes = "Traffic shift / congestion detected." if "pct" in str(metrics) and entity_type == "link" else "Performance degraded."
                if suspected_sensor_issue:
                    notes = "Metrics appear artificial; suspected sensor fault."
                    
                findings.append(AnomalyFinding(
                    entity_id=entity_id,
                    window_start=window_start,
                    window_end=window_end,
                    method="IsolationForest+ZScore",
                    anomaly_score=round(worst_score, 3),
                    is_anomalous=True,
                    metrics=metrics,
                    suspected_sensor_issue=suspected_sensor_issue,
                    notes=notes
                ))
                
        return findings
