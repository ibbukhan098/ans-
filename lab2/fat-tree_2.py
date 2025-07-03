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
import topo
from mininet.net import Mininet
from mininet.topo import Topo
from mininet.log import setLogLevel, info
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.node import RemoteController

class FattreeNet(Topo):
    """
    Creates a Mininet network instance based on the logical fat-tree topology.
    """
    def __init__(self, k, **opts):
        super(FattreeNet, self).__init__(**opts)
        
        ft_topo = topo.Fattree(k)
        
        self.host_map = {}
        self.switch_map = {}
        
        self.create_hosts(ft_topo.get_hosts())
        self.create_switches(ft_topo.get_all_switches())
        self.create_links(ft_topo)

    def create_hosts(self, hosts):
        info('*** Adding hosts\n')
        for i, host_node in enumerate(hosts):
            # Use simple naming h1, h2...
            host_name = f'h{i+1}'
            mn_host = self.addHost(
                host_name,
                ip=host_node.ip,
                mac=host_node.mac,
                defaultRoute=None
            )
            self.host_map[host_node.id] = mn_host
            info(f'Added host {host_name} ({host_node.ip})\n')

    def create_switches(self, switches):
        info('*** Adding switches\n')
        for i, switch_node in enumerate(switches):
            switch_name = f's{i+1}'
            mn_switch = self.addSwitch(
                switch_name,
                dpid=f"{switch_node.dpid:016x}" 
            )
            self.switch_map[switch_node.id] = mn_switch
            info(f'Added {switch_node.type} switch {switch_name} (dpid: {switch_node.dpid})\n')

    def create_links(self, ft_topo):
        info('*** Adding links\n')
        for host_node in ft_topo.get_hosts():
            for edge in host_node.edges:
                neighbor_node = edge.rnode if edge.lnode == host_node else edge.lnode
                self.add_link_to_mininet(host_node, neighbor_node)

        for edge_switch_node in ft_topo.edge_switches:
            for edge in edge_switch_node.edges:
                neighbor_node = edge.rnode if edge.lnode == edge_switch_node else edge.lnode
                if neighbor_node.type == "aggregation":
                    self.add_link_to_mininet(edge_switch_node, neighbor_node)

        for agg_switch_node in ft_topo.agg_switches:
            for edge in agg_switch_node.edges:
                neighbor_node = edge.rnode if edge.lnode == agg_switch_node else edge.lnode
                if neighbor_node.type == "core":
                    self.add_link_to_mininet(agg_switch_node, neighbor_node)

    def add_link_to_mininet(self, node1, node2):
        mn_node1 = self.host_map.get(node1.id) or self.switch_map.get(node1.id)
        mn_node2 = self.switch_map.get(node2.id) 
        
        if mn_node1 and mn_node2:
            self.addLink(
                mn_node1,
                mn_node2,
                bw=15,      
                delay='5ms'    
            )
            info(f'Added link: {mn_node1} <-> {mn_node2}\n')

def run():
    
    k = 4
    net_topo = FattreeNet(k=k)
    
    net = Mininet(
        topo=net_topo,
        link=TCLink,
        controller=None,
        autoSetMacs=False
    )
    
    net.addController(
        'c0',
        controller=RemoteController,
        ip='127.0.0.1',
        port=6653
    )
    
    info('*** Starting network\n')
    net.start()
    
    info('*** Running CLI\n')
    CLI(net)
    
    info('*** Stopping network\n')
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    run()