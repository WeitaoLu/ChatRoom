import sys
import socket
import threading
import time
import random
import json

import struct

# Constants

HEADER_FORMAT = "I" 
DATA_PACKET = 0
ACK_PACKET = 1
ACK_DATA_BYTE = b'\x00'  # ACK data Byte
END_DATA_BYTE = b'\x03'  # transmission finished

def create_packet(sequence_number, data, is_ack=False):
    """Create a packet with a given sequence number and data."""
    header = struct.pack(HEADER_FORMAT, sequence_number)
    if is_ack:
        return header + ACK_DATA_BYTE  # Use a special value for ACK packets
    else:
        return header + data.encode()  # Use the actual data for data packets
def create_end_packet(sequence_number):
    """Create a packet with a given sequence number and data."""
    header = struct.pack(HEADER_FORMAT, sequence_number)
    return header + END_DATA_BYTE  # Use a special value for ACK packets

def parse_packet(packet):
    """Parse a received packet into its components."""
    header_size = struct.calcsize(HEADER_FORMAT)
    header, data = packet[:header_size], packet[header_size:]
    sequence_number,= struct.unpack(HEADER_FORMAT, header)
    is_ack = data == ACK_DATA_BYTE
  
    if is_ack:
        data = None  # No meaningful data in ACK packets
    else:
        data = data.decode()
    return sequence_number, is_ack, data

class CNnode:
    def __init__(self, local_port,receive_port,send_port,neighbors,is_last=False):
        self.port = local_port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('', self.port)) 
        self.window_size = 5
        self.recseq={}
        self.drop_value={}
        self.sent_amount={}
        self.received_amount={}
        self.receive_port = receive_port
        self.send_port = send_port
        self.receive_buffer = {}
        for port,value in receive_port.items():
            self.recseq[port] = 0
            self.drop_value[port] = value

        for port in send_port:
            #print(port)
            self.sent_amount[port] = 0
            self.received_amount[port] = 0
            self.receive_buffer[port] = []
        self.sending_buffer=[]
        for i in range(10):
            self.sending_buffer.append(create_packet(i,str(i)))

        self.paused = not is_last #pause if not last node
        self.largest_no_ack = -1 #index of the largest sent but not acked data.
        
        self.update_interval = 5
        self.neighbors = neighbors  # format: {port: distance}
        self.routing_table = {self.port: (0, self.port)}  # format: {destination: (distance, next_hop)}
        for neighbor_port, distance in self.neighbors.items():
            self.routing_table[neighbor_port] = (distance, neighbor_port)
        self.send_state = False # True if the node has sent its routing table at least once
        self.print_routing_table()
    
    def start(self):
        # Start the node operations (sending, receiving, etc.)
        thread = threading.Thread(target=self.receive_packet)
        thread.daemon = True# end when server ends
        thread.start()
        if not self.paused:
            self.broadcastsender()
        for peer in self.send_port:
            thread = threading.Thread(target=lambda p=peer: self.send_all_window(p))
            #print("start send all window")
            thread.start()
        current_time=time.time()
        while True:
            if(self.paused):#idle
                continue
            if time.time()-current_time >= self.update_interval:
                #print("update")
                for peer in self.send_port:
                    if self.sent_amount[peer] == 0:
                        continue
                    loss_rate = round((self.sent_amount[peer]-self.received_amount[peer]) / self.sent_amount[peer],2)
                    print(f"[{time.time():.3f}] Link to {peer}: {self.sent_amount[peer]} packets sent,  {self.sent_amount[peer]-self.received_amount[peer]} packets lost, loss rate {loss_rate:.3f}")
                    self.neighbors[peer] = loss_rate
                    # print("neighbors",self.neighbors)
                    self.routing_table[peer] = (loss_rate, peer)
                    self.send_routing_table()
                current_time=time.time()  
            else: 
                 for peer in self.send_port:
                    if self.sent_amount[peer] == 0:
                        continue
                    loss_rate = round((self.sent_amount[peer]-self.received_amount[peer]) / self.sent_amount[peer],2)
                    print(f"[{time.time():.3f}] Link to {peer}: {self.sent_amount[peer]} packets sent,  {self.sent_amount[peer]-self.received_amount[peer]} packets lost, loss rate {loss_rate:.3f}")
                    time.sleep(1)
                 continue
            
    def send_all_window(self,port):
        base=0
        current_time=time.time()
        while True:  # Change to an infinite loop for continuous sending
            if(self.paused):#idle
                continue
            #print("send all window")
            self.receive_buffer[port].clear()
            for i in range(base, base + self.window_size):
                buffer_index = i % len(self.sending_buffer)  # Circular buffer index
                self.send_packet(self.sending_buffer[buffer_index], port)
                self.largest_no_ack = buffer_index
                time.sleep(0.02)

            time.sleep(0.5)  # Wait for ACKs to arrive
            if len(self.receive_buffer[port]) == 0:
                #print("Timeout")
                continue  # Continue the loop, effectively re-sending the window
            mostrecentack = (base - 1)%10
            for i in range(len(self.receive_buffer[port])):
                tm, ack = self.receive_buffer[port][i]
                if ack >= (mostrecentack+1)%10:
                    mostrecentack = ack
                    #print("ACKed")
                else:
                    #self.dropped_amount += 1
                    #print("Dropped,ack,mostrecentack",ack,mostrecentack)
                    continue
                time.sleep(0.02)

            # Update the base for the next window
            base = (mostrecentack + 1) % 10
            self.sending_buffer_start = base
            self.largest_no_ack = max(base, self.largest_no_ack) % 10

    def send_packet(self, packet,port):
        self.sent_amount[port] += 1
        #print("send packet",packet,port)
        self.socket.sendto(packet, ('', port))
           
    def receive_packet(self):
        while True:
            packet, sender_address = self.socket.recvfrom(2048)
            if packet and self.paused :
                self.paused = False #active
                self.broadcastsender()
                continue
            if packet == b'@':
                continue
            threading.Thread(target=self.receive_packet_handler, args=(packet,sender_address)).start()

    def receive_packet_handler(self, packet,sender_address):
        # Method to handle a received packet
        if len(packet) >5:
            if self.send_state == False and sender_address:#received and not send any message yet
                    self.send_routing_table()
            print(f"[{time.time()}] Message received at Node {self.port} from Node {sender_address[1]}")
            received_table = json.loads(packet.decode('utf-8'))
            self.update_routing_table(received_table, sender_address[1])
            return

        parsed_seq_num, is_ack, parsed_data = parse_packet(packet)
        sender_port = sender_address[1]
        #print("receive packet",parsed_seq_num,parsed_data,is_ack)
        # time.sleep(0.1)

        if is_ack:#sender receive ack
            #print(f"[{time.time():.3f}] ACK{parsed_seq_num} received")
            self.received_amount[sender_port]+= 1
            self.receive_buffer[sender_port].append((f"[{time.time():.3f}]",parsed_seq_num))

        else:#receiver receive data
            if random.random() < self.drop_value[sender_port]:
                #print(f"[{time.time():.3f}] packet{parsed_seq_num} discarded")
                return
            
           # print(f"[{time.time():.3f}] packet{parsed_seq_num} {parsed_data} received")
            if parsed_seq_num == self.recseq[sender_port]:
                threading.Thread(target=self.send_ack, args=(parsed_data, self.recseq[sender_port], sender_address)).start()
                self.recseq[sender_port] = (self.recseq[sender_port] + 1)%10    
            else:
                threading.Thread(target=self.send_ack, args=(parsed_data, (self.recseq[sender_port]-1)%10, sender_address)).start()

    def send_ack(self,parsed_data,sequence,sender_address):
        # if sequence == -1:#meaningless ack
        #     print("meaningless ack")
        #     return
        packet = create_packet(sequence,parsed_data,is_ack=True)
        self.socket.sendto(packet, sender_address)
        #print(f"[{time.time():.3f}] ACK{sequence} sent, expecting {(sequence+1)%10}")
    def broadcastsender(self):
        for port,value in self.receive_port.items():
            
            self.socket.sendto('@'.encode(), ('', port)) #This packet is to inform sender that the receiver is ready.
            #print(f"[{time.time():.3f}] ACK-1 sent, expecting {(self.recseq[port])%10}"
    def check_table(self,packet):
        if packet == b'@':
            return False
        parsed_seq_num, is_ack, parsed_data = parse_packet(packet)
        
    def send_routing_table(self):
        self.send_state =True # True if the node has sent its routing table at least once
        data = json.dumps(self.routing_table).encode('utf-8')
       
        for neighbor in self.neighbors:
            self.socket.sendto(data, ('localhost', neighbor))
            print(f"[{time.time()}] Message sent from Node {self.port} to Node {neighbor}")

    # def receive_routing_table(self):
    #     while True:
    #         data, addr = self.socket.recvfrom(1024)
    #         if self.send_state == False and addr:#received and not send any message yet
    #             self.send_routing_table()
    #         print(f"[{time.time()}] Message received at Node {self.port} from Node {addr[1]}")
    #         received_table = json.loads(data.decode('utf-8'))
    #         self.update_routing_table(received_table, addr[1])
    

    def update_routing_table(self, received_table, sender_port):
        changed = False
        # print(self.neighbors)
            
        for node, (dist, nexthop) in received_table.items():
            node = int(node)
            dist = float(dist)
            if dist == 1 :
                continue
            if node == self.port and sender_port in self.recseq.keys() and dist !=self.neighbors[sender_port] :#sender have the right to overwrite receiver's distance to sender.
                self.neighbors[sender_port]=dist
                # diff=dist-self.neighbors[sender_port]
                # for node2, (dist2, nexthop2) in self.routing_table.items():#update every path which use sender as nexthop
                #     if node2 != self.port and nexthop2 == sender_port:
                #         self.routing_table[node2] = (dist2+diff, sender_port)
                self.check_table_consistency(received_table,sender_port)#update the tahle based on new distance.
                if self.routing_table[node][1] == sender_port:#update the path from local to sender.
                    self.routing_table[sender_port] = (dist, sender_port)
                changed = True  
               
            if node == self.port and sender_port in self.send_port and nexthop==node and dist !=self.neighbors[sender_port]:#don't trust the distance of the table sent by receiver to sender beacuse it may be out-dated.
                dist=self.neighbors[sender_port]  
            
            if node in self.routing_table and self.routing_table[node][1] == sender_port and changed: #nexthop is sender ,then update any route  using sender as nexthop
                self.routing_table[node] = (round(dist + self.neighbors[sender_port],4), sender_port)
        
            if node != self.port and (node not in self.routing_table or self.routing_table[node][0] > dist +  self.neighbors[sender_port]): # Used self.neighbors[sender_port] instead routing table because it's more convincing.(calculate by sender to node)
                self.routing_table[node] = (round(dist + self.neighbors[sender_port],4), sender_port)
                changed = True
        if changed:
            self.print_routing_table()
            self.send_routing_table()
        else:
            self.print_routing_table()
        self.check_neighbour_consistency()

    def check_table_consistency(self,received_table,sender_port):
        time.sleep(0.01)
        for node, (dist, nexthop) in self.routing_table.items():
            if nexthop == sender_port and node != sender_port and sender_port in self.neighbors.keys() and node in received_table:
                self.routing_table[node] = ( received_table[node][0]+self.neighbors[sender_port], sender_port)


    def check_neighbour_consistency(self):
        for neighbor_port, distance in self.neighbors.items():
            if neighbor_port not in self.routing_table:
                self.routing_table[neighbor_port] = (distance, neighbor_port)
                self.print_routing_table()
                self.send_routing_table()

            elif self.routing_table[neighbor_port][0] != distance and self.routing_table[neighbor_port][1] == neighbor_port:
                self.routing_table[neighbor_port] = (distance, neighbor_port)
                self.print_routing_table()
                self.send_routing_table()

    def print_routing_table(self):
        print(f"Routing Table for Node {self.port}:")
        for dest, (dist, next_hop) in self.routing_table.items():
            if dest != self.port and next_hop != dest:
                print(f"- ({str(dist).lstrip('0')}) -> Node {dest} ; Next hop -> Node {next_hop}")
            elif dest != self.port and next_hop == dest:
                print(f"- ({str(dist).lstrip('0')}) -> Node {dest} ")

def parse_arguments(args):
    local_port = int(args[1])  # The local port for this node

    receivers_loss = {}  # Loss rates for receiving from neighbors
    senders = set()      # Set of ports this node will send to
    neighbors = {}       # Dictionary for both send and receive ports with default value 1
    is_last=False
    i = 2  # Start parsing from the 3rd argument
    while i < len(args):
        if args[i] == 'receive':
            i += 1
            while i < len(args) and args[i].isdigit():
                neighbor_port = int(args[i])
                loss_rate = float(args[i + 1])
                receivers_loss[neighbor_port] = loss_rate
                neighbors[neighbor_port] = 1  # Add to neighbors with default value
                i += 2
        elif args[i] == 'send':
            i += 1
            while i < len(args) and args[i].isdigit():
                neighbor_port = int(args[i])
                senders.add(neighbor_port)
                neighbors[neighbor_port] = 1  # Add to neighbors with default value
                i += 1
        elif args[i] == 'last':
            is_last=True
            break
        else:
            i += 1

    return local_port, neighbors, receivers_loss, senders,is_last

if __name__ == "__main__":
    local_port, neighbors, receivers_loss, senders,is_last = parse_arguments(sys.argv)

    # Create and start the node with parsed arguments
    node = CNnode(local_port, receivers_loss, senders, neighbors,is_last)
    node.start()
    print(f"Started node on port {local_port}")


if __name__ == "__main__":
    local_port, receivers_loss, senders = parse_arguments(sys.argv)

    # Create and start the node with parsed arguments
    node = CNnode(local_port, receivers_loss, senders)
    node.start()
    print(f"Started node on port {local_port}")


# if __name__ == "__main__":
#     # node=sys.argv[1] #for test only
#     # if node == 'node1':
#     #     node1 = GBNProbe(1111, {}, {2222,3333},{2222:1,3333:1})
#     #     node1.start()
#     #     print("start node1")
#     # elif node == 'node2':
#     #     node2 = GBNProbe(2222, {1111: 0.1}, {3333,4444},{1111:1,3333:1,4444:1})
#     #     node2.start()
#     #     print("start node2")
#     # elif node == 'node3':
#     #     node3 = GBNProbe(3333, {1111: 0.5,2222:0.2}, {4444},{1111:1,2222:1,4444:1})
#     #     node3.start()
#     #     print("start node3")
#     # elif node == 'node4':
#     #     node4 = GBNProbe(4444, {2222: 0.8,3333:0.5}, {},{2222:1,3333:1},True)
#     #     node4.start()
#     #     print("start node4")