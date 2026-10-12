import networkx as nx
from datetime import timedelta
from typing import Dict, List, Set, Tuple

from app.models.enums import EventRole, EventType
from app.models.network import NormalizedEvent, Topology
from app.models.incident import CorrelationResult

class CorrelationAgent:
    """Agent 2 - Alarm Correlation Agent
    Groups related network alarms into meaningful incidents, detecting primary vs consequential events and storms.
    """
    
    TOPOLOGY_CORRELATABLE_ALARMS = {
        EventType.INTERFACE_DOWN,
        EventType.LINK_FLAP,
        EventType.BACKHAUL_CONNECTIVITY_LOST,
        EventType.SERVICE_UNAVAILABLE,
        EventType.DEVICE_UNREACHABLE,
        EventType.POWER_SUPPLY_FAILURE,
        EventType.PROCESS_RESTART,
    }

    def __init__(self, topology: Topology):
        self.topology = topology
        self.graph = nx.DiGraph()
        
        # Build topology hierarchy
        tiers = {
            "transit_gateway": 0,
            "core_router": 1,
            "aggregation_router": 2,
            "switch": 3,
            "base_station": 4,
            "enterprise_link": 4
        }
        
        for d in topology.devices:
            self.graph.add_node(d.name, type=d.device_type, tier=tiers.get(d.device_type.value, 99))
            
        for d in topology.devices:
            d_tier = tiers.get(d.device_type.value, 99)
            for peer in d.connected_devices:
                peer_node = topology.device(peer)
                peer_tier = tiers.get(peer_node.device_type.value, 99)
                
                # Directed edge from upstream to downstream (lower tier to higher tier)
                if d_tier < peer_tier:
                    self.graph.add_edge(d.name, peer)
                elif peer_tier < d_tier:
                    self.graph.add_edge(peer, d.name)

    def is_ancestor(self, u: str, v: str) -> bool:
        """Check if device u is upstream of device v."""
        if u not in self.graph or v not in self.graph:
            return False
        return nx.has_path(self.graph, u, v)

    def share_direct_parent(self, u: str, v: str) -> bool:
        """Check if device u and v share the same upstream device."""
        if u not in self.graph or v not in self.graph:
            return False
        u_preds = set(self.graph.predecessors(u))
        v_preds = set(self.graph.predecessors(v))
        return bool(u_preds & v_preds)

    def are_events_related(self, e1: NormalizedEvent, e2: NormalizedEvent) -> bool:
        # Check time window (e.g., 120 seconds)
        if abs((e1.timestamp - e2.timestamp).total_seconds()) > 120:
            return False
            
        # Duplicates / same device
        if e1.device == e2.device:
            return True
            
        # Topologically related (parent/child or siblings)
        if e1.event_type in self.TOPOLOGY_CORRELATABLE_ALARMS and e2.event_type in self.TOPOLOGY_CORRELATABLE_ALARMS:
            if self.is_ancestor(e1.device, e2.device) or self.is_ancestor(e2.device, e1.device):
                return True
            if self.share_direct_parent(e1.device, e2.device):
                return True
                
        return False

    def group_events(self, events: List[NormalizedEvent]) -> List[List[NormalizedEvent]]:
        """Group events into clusters based on relationships."""
        if not events:
            return []
            
        # Build relation graph
        G = nx.Graph()
        for e in events:
            G.add_node(e.event_id, event=e)
            
        for i in range(len(events)):
            for j in range(i + 1, len(events)):
                if self.are_events_related(events[i], events[j]):
                    G.add_edge(events[i].event_id, events[j].event_id)
                    
        # Connected components form our incidents
        clusters = []
        for comp in nx.connected_components(G):
            cluster_events = [G.nodes[eid]["event"] for eid in comp]
            # Sort by timestamp
            cluster_events.sort(key=lambda x: x.timestamp)
            clusters.append(cluster_events)
            
        return clusters

    def correlate(self, events: List[NormalizedEvent]) -> CorrelationResult:
        """Assign roles to a cluster of events and return a CorrelationResult."""
        if not events:
            raise ValueError("Cannot correlate empty event list")
            
        roles: Dict[str, EventRole] = {}
        primary_ids: List[str] = []
        duplicate_of: Dict[str, str] = {}
        rationale: List[str] = []
        
        # Deduplication
        # Signature: (device, event_type, interface)
        seen_signatures: Dict[Tuple[str, EventType, str], str] = {}
        
        unique_events = []
        
        for e in events:
            sig = (e.device, e.event_type, e.interface or "")
            if sig in seen_signatures:
                roles[e.event_id] = EventRole.DUPLICATE
                duplicate_of[e.event_id] = seen_signatures[sig]
            else:
                seen_signatures[sig] = e.event_id
                unique_events.append(e)

        if len(unique_events) == 1:
            roles[unique_events[0].event_id] = EventRole.PRIMARY
            primary_ids.append(unique_events[0].event_id)
            rationale.append(f"{unique_events[0].event_id} is an independent event.")
        else:
            # Find primary vs consequential among unique_events
            # Primary: Highest up in the topology tree (lowest tier), earliest timestamp.
            # We can score them.
            
            # 1. Identify "root" devices in this cluster.
            # A root device in a cluster is one that has no ancestor also present in the cluster.
            cluster_devices = {e.device for e in unique_events}
            roots = set()
            for d in cluster_devices:
                has_ancestor = False
                for other_d in cluster_devices:
                    if d != other_d and self.is_ancestor(other_d, d):
                        has_ancestor = True
                        break
                if not has_ancestor:
                    roots.add(d)
                    
            # 2. Assign roles
            for e in unique_events:
                if e.device in roots:
                    roles[e.event_id] = EventRole.PRIMARY
                    primary_ids.append(e.event_id)
                else:
                    roles[e.event_id] = EventRole.CONSEQUENTIAL
                    
            if roots:
                rationale.append(f"Primary events identified on root topology devices: {', '.join(roots)}.")
            else:
                # Fallback if there are cycles or no clear root (shouldn't happen in a tree)
                roles[unique_events[0].event_id] = EventRole.PRIMARY
                primary_ids.append(unique_events[0].event_id)
                rationale.append(f"Fallback: designated earliest event {unique_events[0].event_id} as primary.")

        # Detect storm
        storm_detected = len(events) > 50  # Arbitrary threshold, can be tuned
        if storm_detected:
            rationale.append(f"Alarm storm detected: {len(events)} related events within a short time window.")
            
        # Calculate time window
        time_window = 0
        if events:
            time_window = int((events[-1].timestamp - events[0].timestamp).total_seconds())

        return CorrelationResult(
            roles=roles,
            primary_event_ids=primary_ids,
            duplicate_of=duplicate_of,
            storm_detected=storm_detected,
            time_window_seconds=time_window,
            rationale=rationale
        )
