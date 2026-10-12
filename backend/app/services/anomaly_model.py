import os
import pickle
import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

class AnomalyModel:
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.model_path = self.data_dir / "anomaly_model.pkl"
        
        self.link_features = ['latency_ms', 'packet_loss_pct', 'jitter_ms', 'utilization_pct', 'interface_errors']
        self.device_features = ['cpu_pct', 'memory_pct']
        
        self.link_model = None
        self.device_model = None
        
        self.link_scaler = None
        self.device_scaler = None
        
        # Baselines for explainability (entity_id -> metric -> mean, std)
        self.baselines = {}
        
        if self.model_path.exists():
            self.load()
        else:
            self.train()
            
    def train(self):
        train_file = self.data_dir / "telemetry_train_normal.csv"
        if not train_file.exists():
            raise FileNotFoundError(f"Training data not found at {train_file}")
            
        df = pd.read_csv(train_file)
        
        # Calculate baselines per entity
        for entity, group in df.groupby("entity_id"):
            self.baselines[entity] = {}
            features = self.link_features if group.iloc[0]["entity_type"] == "link" else self.device_features
            for f in features:
                self.baselines[entity][f] = {
                    "mean": float(group[f].mean()),
                    "std": float(group[f].std())
                }
                
        # Train Link Model
        links_df = df[df["entity_type"] == "link"][self.link_features].fillna(0)
        self.link_scaler = StandardScaler()
        links_scaled = self.link_scaler.fit_transform(links_df)
        self.link_model = IsolationForest(contamination=0.01, random_state=42)
        self.link_model.fit(links_scaled)
        
        # Train Device Model
        devices_df = df[df["entity_type"] == "device"][self.device_features].fillna(0)
        self.device_scaler = StandardScaler()
        devices_scaled = self.device_scaler.fit_transform(devices_df)
        self.device_model = IsolationForest(contamination=0.01, random_state=42)
        self.device_model.fit(devices_scaled)
        
        self.save()
        
    def save(self):
        with open(self.model_path, "wb") as f:
            pickle.dump({
                "link_model": self.link_model,
                "device_model": self.device_model,
                "link_scaler": self.link_scaler,
                "device_scaler": self.device_scaler,
                "baselines": self.baselines
            }, f)
            
    def load(self):
        with open(self.model_path, "rb") as f:
            data = pickle.load(f)
            self.link_model = data["link_model"]
            self.device_model = data["device_model"]
            self.link_scaler = data["link_scaler"]
            self.device_scaler = data["device_scaler"]
            self.baselines = data["baselines"]

    def predict(self, entity_type: str, data: dict) -> dict:
        """Predicts anomaly score and returns explanations."""
        if entity_type == "link":
            features = self.link_features
            model = self.link_model
            scaler = self.link_scaler
        else:
            features = self.device_features
            model = self.device_model
            scaler = self.device_scaler
            
        # Extract features
        x = np.array([[float(data.get(f, 0) or 0) for f in features]])
        
        # Isolation Forest prediction
        x_scaled = scaler.transform(x)
        score = -model.score_samples(x_scaled)[0] # negative so higher = more anomalous
        is_anomaly = model.predict(x_scaled)[0] == -1
        
        return {
            "score": float(score),
            "is_anomaly": bool(is_anomaly),
            "features_used": features
        }
