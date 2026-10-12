from typing import List, Dict

import networkx as nx

from app.models.enums import Confidence, EventRole, EventType
from app.models.network import NormalizedEvent, Topology
from app.models.incident import CorrelationResult, FaultLocationHypothesis

class LocalizationAgent:
    """Agent 3 - Network Topology & Fault Localization Agent
    Uses network topology to determine the most likely location of a network fault.
    """
    
    def __init__(self, topology: Topology):
        self.topology = topology
        self.graph = nx.DiGraph()
        self.interface_to_link = {}
        
        # Build interface to link mapping
        for link in topology.links:
            self.interface_to_link[(link.endpoint_a.device, link.endpoint_a.interface)] = link.link_id
            self.interface_to_link[(link.endpoint_b.device, link.endpoint_b.interface)] = link.link_id
            
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
                if d_tier < peer_tier:
                    self.graph.add_edge(d.name, peer)
                elif peer_tier < d_tier:
                    self.graph.add_edge(peer, d.name)

    def localize(self, events: List[NormalizedEvent], correlation: CorrelationResult) -> List[FaultLocationHypothesis]:
        if not events or not correlation:
            return []
            
        hypotheses = []
        event_by_id = {e.event_id: e for e in events}
        
        primary_events = [event_by_id[eid] for eid in correlation.primary_event_ids if eid in event_by_id]
        consequential_events = [e for e in events if correlation.roles.get(e.event_id) == EventRole.CONSEQUENTIAL]
        
        # Strategy 1: We have an explicit primary alarm (e.g. Interface Down)
        # This points directly to a link or device component.
        rank = 1
        for e in primary_events:
            suspect_id = e.device
            suspect_kind = "device"
            topo_evidence = []
            
            if e.interface:
                link_id = self.interface_to_link.get((e.device, e.interface))
                if link_id:
                    suspect_id = link_id
                    suspect_kind = "link"
                    topo_evidence.append(f"Primary alarm on interface {e.interface} corresponds to link {link_id}.")
                else:
                    suspect_id = f"{e.device}:{e.interface}"
                    suspect_kind = "interface"
                    topo_evidence.append(f"Primary alarm on interface {e.interface} of device {e.device}.")
            else:
                topo_evidence.append(f"Primary alarm explicitly flags device {e.device}.")
                
            # Add downstream evidence if any
            downstream_alarms = []
            downstream_devices = []
            for ce in consequential_events:
                if e.device in self.graph and ce.device in self.graph:
                    if nx.has_path(self.graph, e.device, ce.device):
                        downstream_alarms.append(ce.event_id)
                        downstream_devices.append(ce.device)
                    
            if downstream_alarms:
                topo_evidence.append(f"Confirmed downstream impact on: {', '.join(set(downstream_devices))}.")
                
            hypotheses.append(
                FaultLocationHypothesis(
                    rank=rank,
                    suspect_id=suspect_id,
                    suspect_kind=suspect_kind,
                    confidence=Confidence.HIGH if downstream_alarms else Confidence.MEDIUM,
                    confidence_score=0.9 if downstream_alarms else 0.7,
                    supporting_alarm_ids=[e.event_id] + downstream_alarms,
                    topology_evidence=topo_evidence,
                    summary=f"Fault at {suspect_kind} {suspect_id} caused by primary event {e.event_id}."
                )
            )
            rank += 1
            
        # Strategy 2: We have multiple primary alarms (e.g., Backhaul Lost on BS-101 and BS-102)
        # with no upstream alarm. We must infer the shared parent.
        if len(primary_events) > 1:
            devices = {e.device for e in primary_events if e.device in self.graph}
            if len(devices) > 1:
                # Find common ancestors
                ancestors_per_device = {d: set(nx.ancestors(self.graph, d)) for d in devices}
                common_ancestors = set.intersection(*ancestors_per_device.values())
                
                if common_ancestors:
                    # Pick the deepest common ancestor (highest tier)
                    deepest_ancestor = max(common_ancestors, key=lambda x: self.graph.nodes[x]['tier'])
                    
                    # See if other children of this ancestor are healthy
                    all_children = set(self.graph.successors(deepest_ancestor))
                    affected_children = set()
                    for d in devices:
                        if d in all_children:
                            affected_children.add(d)
                        else:
                            # trace back to child of deepest_ancestor
                            path = nx.shortest_path(self.graph, deepest_ancestor, d)
                            if len(path) > 1:
                                affected_children.add(path[1])
                                
                    healthy_children = all_children - affected_children
                    
                    topo_evidence = [f"Multiple downstream devices ({', '.join(devices)}) failed simultaneously.",
                                     f"They share a common upstream dependency: {deepest_ancestor}."]
                    
                    if healthy_children:
                        topo_evidence.append(f"However, other paths via {deepest_ancestor} (to {', '.join(healthy_children)}) appear healthy, suggesting a partial failure or link issue rather than total device failure.")
                    
                    # Deduplicate hypothesis if it overlaps with Strategy 1
                    existing_suspects = {h.suspect_id for h in hypotheses}
                    if deepest_ancestor not in existing_suspects:
                        hypotheses.append(
                            FaultLocationHypothesis(
                                rank=rank,
                                suspect_id=deepest_ancestor,
                                suspect_kind="device",
                                confidence=Confidence.HIGH if not healthy_children else Confidence.MEDIUM,
                                confidence_score=0.85,
                                supporting_alarm_ids=[e.event_id for e in primary_events],
                                topology_evidence=topo_evidence,
                                summary=f"Inferred fault domain at {deepest_ancestor} based on shared downstream failures."
                            )
                        )
                        rank += 1

        # Re-rank by confidence
        hypotheses.sort(key=lambda x: x.confidence_score or 0.0, reverse=True)
        for i, h in enumerate(hypotheses):
            h.rank = i + 1
            
        return hypotheses
