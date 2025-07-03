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

import os
import subprocess
import time

import mininet
import mininet.clean
from mininet.net import Mininet
from mininet.cli import CLI
from mininet.log import lg, info
from mininet.link import TCLink
from mininet.node import Node, OVSKernelSwitch, RemoteController
from mininet.topo import Topo
from mininet.util import waitListening, custom

from topo import Fattree


class FattreeNet(Topo):
    """
    Create a fat-tree network in Mininet
    """

    def __init__(self, ft_topo):

        Topo.__init__(self)

        # TODO: please complete the network generation logic here 
        # Create Mininet switches for every graph switch
        self.node_map = {}  #  map each graph‐node.id → the Mininet name you use (e.g. "s1" or "h1")
        switch_counter = 1
        for sw_node in ft_topo.switches:
            mn_name = f"s{switch_counter}"    # only letters+digits
            self.node_map[sw_node.id] = mn_name
            self.addSwitch(mn_name)
            switch_counter += 1
           
        # Create all host‐nodes with simple names: h1, h2, …
        host_counter = 1
        for host_node in ft_topo.servers:
            # host_node.id is something like "host_2_1_0"
            parts = host_node.id.split('_')
            p = int(parts[1])      # pod number
            i = int(parts[2])      # index of the edge switch within that pod
            h_idx = int(parts[3])  # host‐index under that edge

            #  Compute the actual host ID (starts at .2)
            actual_idx = h_idx + 2

            # (3) Build the string "10.p.i.actual_idx/24"
            ip_addr = f"10.{p}.{i}.{actual_idx}/24"

            # (4) Create a simple Mininet host name, e.g. "h1", "h2", ...
            mn_name = f"h{host_counter}"
            self.node_map[host_node.id] = mn_name

            # (5) Pass that IP to addHost()
            self.addHost(mn_name, ip=ip_addr)

            host_counter += 1
            
        # Wire up links between every pair of graph‐nodes that share an Edge
        # We iterate over each Edge exactly once to avoid duplicate addLink calls.
        seen_edges = set()
        for node in ft_topo.switches + ft_topo.servers:
            for edge in node.edges:
                if edge in seen_edges:
                    continue
                seen_edges.add(edge)

                u_id = edge.lnode.id
                v_id = edge.rnode.id
                mn_u = self.node_map[u_id]
                mn_v = self.node_map[v_id]

                # Use exactly the same bw/delay as the lab requires
                self.addLink(mn_u, mn_v, bw=15, delay="5ms")


def make_mininet_instance(graph_topo):

    net_topo = FattreeNet(graph_topo)
    net = Mininet(topo=net_topo, controller=None, autoSetMacs=True)
    net.addController('c0', controller=RemoteController,
                      ip="127.0.0.1", port=6653)
    return net


def run(graph_topo):

    # Run the Mininet CLI with a given topology
    lg.setLogLevel('info')
    mininet.clean.cleanup()
    net = make_mininet_instance(graph_topo)

    info('*** Starting network ***\n')
    net.start()
    info('*** Running CLI ***\n')
    CLI(net)
    info('*** Stopping network ***\n')
    net.stop()


if __name__ == '__main__':
    ft_topo = Fattree(4)
    run(ft_topo)
