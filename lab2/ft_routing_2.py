"""
 Copyright (c) 2025 Computer Networks Group @ UPB

 Permission is hereby granted, free of charge, to any person obtaining a copy of
 this software and associated documentation files (the "Software"), to deal in
 the Software without restriction, including without limitation the rights to
 use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
 the Software, and to permit persons to whom the Software is furnished to do so,
 subject to the following conditions:

 The above copyright notice and this permission notice shall be included in all
 copies or substantial portions of the Software.

 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
 FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
 COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
 IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
 CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 """

#!/usr/bin/env python3

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, arp, ether_types
from ryu.topology.api import get_switch, get_link
from ryu.lib import hub
import time

class FTRouter(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(FTRouter, self).__init__(*args, **kwargs)
        self.k = 4  # Number of ports per switch
        self.arp_table = {}
        self.rules_installed = False
        self.host_locations = {} 
        self.last_log_time = {}
        self.monitor_thread = hub.spawn(self._monitor)

    def _monitor(self):
        """Monitor topology and install rules when ready."""
        while not self.rules_installed:
            hub.sleep(4)
            switches = get_switch(self, None)
            links = get_link(self, None)
            
            num_switches_expected = (self.k**2 // 4) + self.k**2  
            num_links_expected = self.k**3 

            if len(switches) < num_switches_expected or len(links) < num_links_expected:
                continue

            self.logger.info("Full topology discovered. Installing two-level routing rules.")
            if self.install_two_level_rules(switches, links):
                self.rules_installed = True
                self.logger.info("Two-level routing rules installed successfully.")
            else:
                self.logger.error("Failed to install two-level routing rules. Retrying...")

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        """Install default flow to send packets to controller."""
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Install table-miss flow entry
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                        ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        """Add a flow entry to the switch."""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                  priority=priority, match=match, instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                  match=match, instructions=inst)
        datapath.send_msg(mod)

    def get_switch_info(self, dpid):
        """Get switch type and position info from dpid."""
        k = self.k
        edge_start = 1
        agg_start = 1 + (k**2 // 2)
        core_start = 1 + k**2

        if dpid >= core_start:
            # Core switch
            core_index = dpid - core_start
            return "core", -1, core_index
        elif dpid >= agg_start:
            # Aggregation switch
            agg_index = dpid - agg_start
            pod = agg_index // (k // 2)
            index = agg_index % (k // 2)
            return "aggregation", pod, index
        else:
            # Edge switch
            edge_index = dpid - edge_start
            pod = edge_index // (k // 2)
            index = edge_index % (k // 2)
            return "edge", pod, index

    def install_two_level_rules(self, switches, link_list):
        """Install two-level routing rules according to the paper."""
        try:
            links = {s.dp.id: {} for s in switches}
            for link in link_list:
                links[link.src.dpid][link.dst.dpid] = link.src.port_no

            for switch in switches:
                datapath = switch.dp
                dpid = datapath.id
                ofproto = datapath.ofproto
                parser = datapath.ofproto_parser
                
                switch_type, pod_info, index_info = self.get_switch_info(dpid)
                
                if switch_type == "core":
                    self.install_core_rules(datapath, dpid, links, parser)
                elif switch_type == "aggregation":
                    self.install_aggregation_rules(datapath, dpid, links, parser, pod_info, index_info)
                elif switch_type == "edge":
                    self.install_edge_rules(datapath, dpid, links, parser, pod_info, index_info)

            return True
        except Exception as e:
            self.logger.error(f"Error installing two-level rules: {e}")
            return False

    def install_core_rules(self, datapath, dpid, links, parser):
        """Install core switch rules - terminating prefixes for pods."""
        for pod in range(self.k):
            pod_prefix = f"10.{pod}.0.0"
            pod_mask = "255.255.0.0" 
            
            # Find port connected to this pod
            for neighbor_dpid, port in links[dpid].items():
                neighbor_info = self.get_switch_info(neighbor_dpid)
                if neighbor_info[0] == "aggregation" and neighbor_info[1] == pod:
                    match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP,
                                          ipv4_dst=(pod_prefix, pod_mask))
                    actions = [parser.OFPActionOutput(port)]
                    self.add_flow(datapath, priority=1, match=match, actions=actions)
                    self.logger.info(f"Core s{dpid}: Route to pod {pod} via port {port}")
                    break

    def install_aggregation_rules(self, datapath, dpid, links, parser, pod, index):
        """Install aggregation switch rules - prefix for intra-pod, suffix for inter-pod."""
        
        for subnet in range(self.k // 2):
            subnet_prefix = f"10.{pod}.{subnet}.0"
            subnet_mask = "255.255.255.0" 
            
            edge_dpid = 1 + (pod * (self.k // 2) + subnet)
            if edge_dpid in links[dpid]:
                port = links[dpid][edge_dpid]
                match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP,
                                      ipv4_dst=(subnet_prefix, subnet_mask))
                actions = [parser.OFPActionOutput(port)]
                self.add_flow(datapath, priority=2, match=match, actions=actions)
                self.logger.info(f"Agg s{dpid}: Intra-pod route to {subnet_prefix}/24 via port {port}")

        core_ports = []
        for neighbor_dpid, port in links[dpid].items():
            if self.get_switch_info(neighbor_dpid)[0] == "core":
                core_ports.append(port)
        
        core_ports.sort()
        
        for host_id in range(2, self.k//2 + 2):
            if core_ports:
                port_index = (host_id - 2 + index) % (self.k // 2)
                if port_index < len(core_ports):
                    match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP,
                                          ipv4_dst=('0.0.0.' + str(host_id), '0.0.0.255'))
                    actions = [parser.OFPActionOutput(core_ports[port_index])]
                    self.add_flow(datapath, priority=1, match=match, actions=actions)
                    self.logger.info(f"Agg s{dpid}: Inter-pod suffix .{host_id} via core port {core_ports[port_index]}")

    def install_edge_rules(self, datapath, dpid, links, parser, pod, index):
        """Install edge switch rules - suffix matching for inter-pod traffic."""
        agg_ports = []
        for neighbor_dpid, port in links[dpid].items():
            if self.get_switch_info(neighbor_dpid)[0] == "aggregation":
                agg_ports.append(port)
        
        agg_ports.sort()
        
        for host_id in range(2, self.k//2 + 2): 
            if agg_ports:
                port_index = (host_id - 2 + index) % (self.k // 2)
                if port_index < len(agg_ports):
                    match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP,
                                          ipv4_dst=('0.0.0.' + str(host_id), '0.0.0.255'))
                    actions = [parser.OFPActionOutput(agg_ports[port_index])]
                    self.add_flow(datapath, priority=1, match=match, actions=actions)
                    self.logger.info(f"Edge s{dpid}: Inter-pod suffix .{host_id} via agg port {agg_ports[port_index]}")

    def should_log(self, message_key):
        """Rate limit logging to reduce spam."""
        current_time = time.time()
        if message_key in self.last_log_time:
            if current_time - self.last_log_time[message_key] < 2.0: 
                return False
        self.last_log_time[message_key] = current_time
        return True

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        """Handle packets sent to controller (mainly ARP)."""
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        arp_pkt = pkt.get_protocol(arp.arp)

        if not arp_pkt:
            return

        if arp_pkt.src_ip not in self.host_locations:
            self.host_locations[arp_pkt.src_ip] = (datapath.id, in_port)
            self.arp_table[arp_pkt.src_ip] = eth.src
            
            match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP, 
                                  ipv4_dst=arp_pkt.src_ip)
            actions = [parser.OFPActionOutput(in_port)]
            self.add_flow(datapath, priority=3, match=match, actions=actions)
            if self.should_log(f"host_learned_{arp_pkt.src_ip}"):
                self.logger.info(f"Host learned: {arp_pkt.src_ip} at s{datapath.id} port {in_port}")

        if arp_pkt.opcode == arp.ARP_REQUEST:
            dst_ip = arp_pkt.dst_ip
            
            if dst_ip in self.arp_table:
                src_mac = self.arp_table[dst_ip]
                
                # Create ARP reply
                reply_pkt = packet.Packet()
                reply_pkt.add_protocol(ethernet.ethernet(
                    dst=eth.src, src=src_mac, ethertype=ether_types.ETH_TYPE_ARP))
                reply_pkt.add_protocol(arp.arp(
                    opcode=arp.ARP_REPLY, src_mac=src_mac, src_ip=dst_ip,
                    dst_mac=eth.src, dst_ip=arp_pkt.src_ip))
                reply_pkt.serialize()
                
                actions = [parser.OFPActionOutput(in_port)]
                out = parser.OFPPacketOut(
                    datapath=datapath, buffer_id=ofproto.OFP_NO_BUFFER,
                    in_port=ofproto.OFPP_CONTROLLER, actions=actions, data=reply_pkt.data)
                datapath.send_msg(out)
                if self.should_log(f"arp_reply_{dst_ip}"):
                    self.logger.info(f"ARP reply sent: {dst_ip} is at {src_mac}")
            else:
                # Flood ARP request
                actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
                out = parser.OFPPacketOut(
                    datapath=datapath, buffer_id=msg.buffer_id,
                    in_port=in_port, actions=actions, data=msg.data)
                datapath.send_msg(out)
                if self.should_log(f"arp_flood_{dst_ip}"):
                    self.logger.info(f"ARP request flooded for {dst_ip}")