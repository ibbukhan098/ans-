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

from lib import config # do not import anything before this
from p4app import P4Mininet
from mininet.topo import Topo
from mininet.cli import CLI
import os

# Make sure this matches the #define in your p4/main.p4
NUM_WORKERS = 2

class SMLTopo(Topo):
    def __init__(self, **opts):
        Topo.__init__(self, **opts)

        # Create the switch
        sw = self.addSwitch('s1')

        # Create the workers and link them to the switch
        # Worker 'w_i' will be connected to the switch's port 'i'
        for i in range(NUM_WORKERS):
            worker = self.addHost('w%d' % i)
            self.addLink(worker, sw, port2=i)

def RunWorkers(net):
    """
    Starts the workers and waits for their completion.
    Redirects output to logs/<worker_name>.log (see lib/worker.py, Log())
    This function assumes worker i is named 'w<i>'.
    """
    worker = lambda rank: "w%i" % rank
    log_file = lambda rank: os.path.join(os.environ['APP_LOGS'], "%s.log" % worker(rank))
    for i in range(NUM_WORKERS):
        net.get(worker(i)).sendCmd('python worker.py %d > %s' % (i, log_file(i)))
        print("Started worker %d" % i)

    print("Waiting for workers to complete...")
    for i in range(NUM_WORKERS):
        net.get(worker(i)).waitOutput()
    print("All workers finished.")


def RunControlPlane(net):
    """
    One-time control plane configuration
    """
    print("--- Inside RunControlPlane function ---")
    sw = net.get('s1')

    # This is the rule for broadcasting that you already have. It's correct.
    # It tells the switch that multicast group 1 includes all worker ports.
    sw.addMulticastGroup(mgid=1, ports=range(NUM_WORKERS))
    print("--- Configured multicast group 1 on switch s1 ---")

    # --- NEW: Add rules to the aggregation_table ---
    # The P4 program reads the counter BEFORE this table is applied.
    # So, we need to decide what to do based on the number of packets
    # already received.
    
    # Rule 1: This is the LAST packet needed for aggregation.
    # If the counter is NUM_WORKERS - 1 (i.e., 1), the incoming packet is the
    # second and final one. We should broadcast the result.
    sw.insertTableEntry(
        table_name='TheIngress.aggregation_table',
        match_fields={'meta.current_count': NUM_WORKERS - 1},
        action_name='TheIngress.broadcast_and_reset'
    )
    print("--- Inserted table rule: if count==1, then broadcast and reset ---")

    # The default action is 'aggregate_and_increment', which handles all other
    # cases (i.e., when count is 0). So we don't need to add another rule.
    print("--- Control plane setup finished ---")


# Create an instance of our topology
topo = SMLTopo()

# Create the P4Mininet network instance
net = P4Mininet(program="p4/main.p4", topo=topo)

# Assign our control plane and worker functions
net.run_control_plane = lambda: RunControlPlane(net)
net.run_workers = lambda: RunWorkers(net)

# Start the network
net.start()

# Run the one-time control plane configuration
net.run_control_plane()

# You can now run commands in the Mininet CLI.
# To run the workers, type: py net.run_workers()
# To exit, type: exit
CLI(net)

# Stop the network when the CLI exits
net.stop()