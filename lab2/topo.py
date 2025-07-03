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

# Class for an edge in the graph
class Edge:
	def __init__(self):
		self.lnode = None
		self.rnode = None
	
	def remove(self):
		self.lnode.edges.remove(self)
		self.rnode.edges.remove(self)
		self.lnode = None
		self.rnode = None

# Class for a node in the graph
class Node:
	def __init__(self, id, type):
		self.edges = []
		self.id = id
		self.type = type

	# Add an edge connected to another node
	def add_edge(self, node):
		edge = Edge()
		edge.lnode = self
		edge.rnode = node
		self.edges.append(edge)
		node.edges.append(edge)
		return edge

	# Remove an edge from the node
	def remove_edge(self, edge):
		self.edges.remove(edge)

	# Decide if another node is a neighbor
	def is_neighbor(self, node):
		for edge in self.edges:
			if edge.lnode == node or edge.rnode == node:
				return True
		return False


class Fattree:

	def __init__(self, num_ports):
		self.servers = []
		self.switches = []
		self.generate(num_ports)

	def generate(self, num_ports):

		# TODO: code for generating the fat-tree topology
		k = num_ports
		num_pods = k
		num_edge_per_pod = k//2
		num_agg_per_pod  = k//2
		num_core = (k//2)*(k//2)
		num_hosts_per_edge = k//2

		# Create core switches
		core_nodes = []
		for i in range(k//2):
			row = []
			for j in range(k//2):
				node_id = f"core_{i}_{j}"
				core_switch = Node(node_id, type="core")
				self.switches.append(core_switch)
				row.append(core_switch)
			core_nodes.append(row)
   
		# Create pods
		pod_agg = []
		pod_edge = []
		for p in range(num_pods):
			# aggregation switches in pod p
			agg_list = []
			for j in range(num_agg_per_pod):
				node_id = f"agg_{p}_{j}"
				agg_sw = Node(node_id, type="agg")
				self.switches.append(agg_sw)
				agg_list.append(agg_sw)
			pod_agg.append(agg_list)

			# edge switches in pod p
			edge_list = []
			for i in range(num_edge_per_pod):
				node_id = f"edge_{p}_{i}"
				edge_sw = Node(node_id, type="edge")
				self.switches.append(edge_sw)
				edge_list.append(edge_sw)
			pod_edge.append(edge_list)
   
		# Connect each edge switch to every aggregation switch in the same pod
		for p in range(num_pods):
			for edge_sw in pod_edge[p]:
				for agg_sw in pod_agg[p]:
					edge = edge_sw.add_edge(agg_sw)
     
     
		# Connect aggregation switches to core switches
		for p in range(num_pods):
			for j in range(num_agg_per_pod):
				agg_sw = pod_agg[p][j]
				# Get the core switch for this aggregation switch by getting the row
				for i in range(k//2):
					core_sw = core_nodes[i][j]
					agg_sw.add_edge(core_sw)
     
		# Create and attach hosts (servers) to each edge switch
		for p in range(num_pods):
			for i in range(num_edge_per_pod):
				edge_sw = pod_edge[p][i]
				# For each edge switch, create its hosts
				for h_idx in range(num_hosts_per_edge):
					node_id = f"host_{p}_{i}_{h_idx}"
					host = Node(node_id, type="host")
					self.servers.append(host)
					host.add_edge(edge_sw)
     
     
if __name__ == "__main__":
    # 1) Choose a small k to test, e.g. k = 4
    k = 4
    ft = Fattree(k)

    # 2) Check total counts of switches and hosts
    expected_switches = k*k + (k//2)*(k//2)
    expected_hosts    = k*k

    print(f"=== Testing fat-tree with k = {k} ===")
    print("Expected # switches:", expected_switches)
    print("Actual   # switches:", len(ft.switches))
    print("Expected # hosts:   ", expected_hosts)
    print("Actual   # hosts:   ", len(ft.servers))

    # Optionally assert that they match:
    assert len(ft.switches) == expected_switches, "Switch count mismatch!"
    assert len(ft.servers)  == expected_hosts,    "Host count mismatch!"

    # 3) Pick one representative edge switch, aggregation switch, and core switch.
    #    Print their neighbor lists so you can eyeball if the connections look correct.

    # Find one edge switch in pod 0 (say edge_0_0)
    edge_node = next(node for node in ft.switches if node.id == "edge_0_0")
    # Gather its neighbor IDs:
    edge_neighbors = []
    for e in edge_node.edges:
        # Each Edge object has two endpoints; pick the other endpoint
        other = e.rnode if e.lnode is edge_node else e.lnode
        edge_neighbors.append(other.id)
    print("\nNeighbors of edge_0_0:", sorted(edge_neighbors))
    # You should see exactly (k/2) hosts (host_0_0_0, ..., host_0_0_{(k/2)-1})
    # plus (k/2) aggregation switches (agg_0_0, agg_0_1) when k=4.

    # 4) Pick one aggregation switch, e.g. agg_0_1
    agg_node = next(node for node in ft.switches if node.id == "agg_0_1")
    agg_neighbors = []
    for e in agg_node.edges:
        other = e.rnode if e.lnode is agg_node else e.lnode
        agg_neighbors.append(other.id)
    print("Neighbors of agg_0_1:", sorted(agg_neighbors))
    # You should see: 
    #   - (k/2) edge switches in pod 0: ["edge_0_0","edge_0_1"] 
    #   - (k/2) core switches in column j=1: ["core_0_1","core_1_1"]

    # 5) Pick one core switch, say core_1_1 (row=1, col=1 for k=4)
    core_node = next(node for node in ft.switches if node.id == "core_1_1")
    core_neighbors = []
    for e in core_node.edges:
        other = e.rnode if e.lnode is core_node else e.lnode
        core_neighbors.append(other.id)
    print("Neighbors of core_1_1:", sorted(core_neighbors))
    # You should see exactly one aggregation switch per pod, each of the form "agg_{pod}_1".
    # For k=4, that is: ["agg_0_1", "agg_1_1", "agg_2_1", "agg_3_1"].

    # 6) Finally, pick one host, e.g. host_2_1_0
    host_node = next(node for node in ft.servers if node.id == "host_2_1_0")
    host_neighbors = []
    for e in host_node.edges:
        other = e.rnode if e.lnode is host_node else e.lnode
        host_neighbors.append(other.id)
    print("Neighbors of host_2_1_0:", host_neighbors)
    # You should see exactly one neighbor: "edge_2_1".

    print("\nAll adjacency checks passed: your topology looks correct!")

     


               

		


