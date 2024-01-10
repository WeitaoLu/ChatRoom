import socket
import threading
import json
import time
import sys

class Dvnode:
    def __init__(self, local_port, neighbors):
        self.local_port = local_port
        self.neighbors = neighbors  # format: {port: distance}
        self.routing_table = {local_port: (0, local_port)}  # format: {destination: (distance, next_hop)}
        for neighbor_port, distance in self.neighbors.items():
            self.routing_table[neighbor_port] = (distance, neighbor_port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('', local_port))
        self.stable = False
        self.send_state = False # True if the node has sent its routing table at least once
        self.print_routing_table()

    def send_routing_table(self):
        self.send_state =True # True if the node has sent its routing table at least once
        data = json.dumps(self.routing_table).encode('utf-8')
       
        for neighbor in self.neighbors:
            self.socket.sendto(data, ('localhost', neighbor))
            print(f"[{time.time()}] Message sent from Node {self.local_port} to Node {neighbor}")

    def receive_routing_table(self):
        while True:
            data, addr = self.socket.recvfrom(1024)
            if self.send_state == False and addr:#received and not send any message yet
                self.send_routing_table()
            print(f"[{time.time()}] Message received at Node {self.local_port} from Node {addr[1]}")
            received_table = json.loads(data.decode('utf-8'))
            self.update_routing_table(received_table, addr[1])


    def update_routing_table(self, received_table, sender_port):
        changed = False
        for node, (dist, _) in received_table.items():
            node = int(node)
            dist = float(dist)
            if node != self.local_port and (node not in self.routing_table or self.routing_table[node][0] > dist +  self.routing_table[sender_port][0]):
                self.routing_table[node] = (round(dist + self.routing_table[sender_port][0],4), sender_port)
                changed = True
        if changed:
            self.print_routing_table()
            self.send_routing_table()
        else:
            self.print_routing_table()
      
        
    def print_routing_table(self):
        print(f"Routing Table for Node {self.local_port}:")
        for dest, (dist, next_hop) in self.routing_table.items():
            if dest != self.local_port and next_hop != dest:
                print(f"- ({str(dist).lstrip('0')}) -> Node {dest} ; Next hop -> Node {next_hop}")
            elif dest != self.local_port and next_hop == dest:
                print(f"- ({str(dist).lstrip('0')}) -> Node {dest} ")
            

def start_node(port, neighbor_info, start_signal):
    node = Dvnode(port, neighbor_info)
    threading.Thread(target=node.receive_routing_table, daemon=True).start()
    if start_signal:
        node.send_routing_table()
    return node

def parse_arguments(args):
    local_port = int(args[1])
    neighbor_info = {}
    i = 2
    while i < len(args) and args[i] != 'last':
        neighbor_port = int(args[i])
        neighbor_distance = float(args[i + 1])
        neighbor_info[neighbor_port] = neighbor_distance
        i += 2
    start_signal = i < len(args) and args[i] == 'last'
    return local_port, neighbor_info, start_signal

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python dvnode.py <local-port> <neighbor1-port> <loss-rate-1> ... [last]")
        sys.exit(1)

    local_port, neighbors, start_signal = parse_arguments(sys.argv)
    node = start_node(local_port, neighbors, start_signal)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"Node {local_port} terminated.")
