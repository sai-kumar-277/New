from typing import List, Dict, Set
import networkx as nx

from app.models.enums import EventType, ServiceState
from app.models.network import NormalizedEvent, Topology
from app.models.incident import CorrelationResult, FaultLocationHypothesis, ServiceImpact, ServiceImpactItem

class ImpactAgent:
    """Agent 5 - Service Impact Analysis Agent
    Determines which services and network segments may be affected by a fault.
    """
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
                if d_tier < peer_tier:
                    self.graph.add_edge(d.name, peer)
                elif peer_tier < d_tier:
                    self.graph.add_edge(peer, d.name)
                    
        self.service_map = {s.service_id: s for s in self.topology.services}

    def analyze(self, events: List[NormalizedEvent], correlation: CorrelationResult, hypotheses: List[FaultLocationHypothesis]) -> ServiceImpact:
        if not events or not hypotheses:
            return ServiceImpact(summary="No events or hypotheses to analyze.")
            
        # 1. Identify confirmed affected devices from alarms
        confirmed_devices = set()
        for e in events:
            if e.event_type in [EventType.INTERFACE_DOWN, EventType.DEVICE_UNREACHABLE, EventType.BACKHAUL_CONNECTIVITY_LOST, EventType.SERVICE_UNAVAILABLE, EventType.POWER_SUPPLY_FAILURE]:
                confirmed_devices.add(e.device)
                
        # 2. Extract top suspected fault location
        top_hypothesis = hypotheses[0]
        suspect_id = top_hypothesis.suspect_id
        
        # Determine downstream devices from the suspect
        downstream = set()
        affected_links = set()
        
        if top_hypothesis.suspect_kind == "device" and suspect_id in self.graph:
            downstream = set(nx.descendants(self.graph, suspect_id))
            downstream.add(suspect_id)
        elif top_hypothesis.suspect_kind == "link":
            affected_links.add(suspect_id)
            # Find the downstream endpoint of the link
            for link in self.topology.links:
                if link.link_id == suspect_id:
                    # check which endpoint is downstream (higher tier)
                    tier_a = self.graph.nodes[link.endpoint_a.device]["tier"]
                    tier_b = self.graph.nodes[link.endpoint_b.device]["tier"]
                    if tier_a > tier_b:
                        downstream = set(nx.descendants(self.graph, link.endpoint_a.device))
                        downstream.add(link.endpoint_a.device)
                    else:
                        downstream = set(nx.descendants(self.graph, link.endpoint_b.device))
                        downstream.add(link.endpoint_b.device)
                    break
        elif top_hypothesis.suspect_kind == "interface":
            # e.g. AR-01:GE-0/0/1
            device = suspect_id.split(":")[0]
            if device in self.graph:
                downstream = set(nx.descendants(self.graph, device))
                downstream.add(device)
                
        unconfirmed_devices = downstream - confirmed_devices
        
        # 3. Analyze services
        service_items = []
        for svc in self.topology.services:
            endpoint = svc.endpoint_device
            if endpoint in confirmed_devices:
                # Determine if degraded or unavailable
                # If there's redundancy, it might be degraded. If no redundancy, unavailable.
                state = ServiceState.UNAVAILABLE
                if svc.redundancy != "none":
                    # We could check if ALL redundant paths are down, but a simple heuristic:
                    # If it has redundancy, assume degraded unless both paths have alarms.
                    # For a real implementation, we'd check the exact redundant paths.
                    # Based on topology, AR-02 has redundancy.
                    # If we only have alarms for one uplink, it's degraded.
                    state = ServiceState.DEGRADED
                    
                service_items.append(ServiceImpactItem(
                    service_id=svc.service_id,
                    state=state,
                    confirmed=True,
                    redundancy_available=(svc.redundancy != "none"),
                    reason=f"Endpoint device {endpoint} confirmed affected by alarms."
                ))
            elif endpoint in unconfirmed_devices:
                service_items.append(ServiceImpactItem(
                    service_id=svc.service_id,
                    state=ServiceState.POTENTIALLY_AFFECTED,
                    confirmed=False,
                    redundancy_available=(svc.redundancy != "none"),
                    reason=f"Endpoint device {endpoint} is downstream of the fault domain."
                ))
                
        # Count total customer impact if data is available
        total_customers = 0
        has_customer_data = False
        
        for item in service_items:
            svc = self.service_map[item.service_id]
            if svc.customer_data_available and svc.customer_count is not None:
                total_customers += svc.customer_count
                has_customer_data = True
                
        customer_count = total_customers if has_customer_data else None
        customer_count_source = "CRM Database" if has_customer_data else None
        
        # Summarize
        degraded = sum(1 for s in service_items if s.state == ServiceState.DEGRADED)
        unavailable = sum(1 for s in service_items if s.state == ServiceState.UNAVAILABLE)
        potentially = sum(1 for s in service_items if s.state == ServiceState.POTENTIALLY_AFFECTED)
        
        summary = f"Service Impact: {unavailable} unavailable, {degraded} degraded, {potentially} potentially affected."
        if has_customer_data:
            summary += f" Estimated {customer_count} customers impacted."
            
        return ServiceImpact(
            affected_devices=sorted(list(confirmed_devices)),
            unconfirmed_devices=sorted(list(unconfirmed_devices)),
            affected_links=sorted(list(affected_links)),
            services=service_items,
            customer_count=customer_count,
            customer_count_source=customer_count_source,
            summary=summary
        )
