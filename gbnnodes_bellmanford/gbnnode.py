import sys
import socket
import threading
import time
import random

import struct

# Constants

HEADER_FORMAT = "I" 
DATA_PACKET = 0
ACK_PACKET = 1
ACK_DATA_BYTE = b'\x00'  # ACK data Byte
END_DATA_BYTE = b'\x03'  # transmission finished

def create_packet(sequence_number, data, is_ack=False):
    header = struct.pack(HEADER_FORMAT, sequence_number)
    if is_ack:
        return header + ACK_DATA_BYTE  # Use a special value for ACK packets
    else:
        return header + data.encode()  # Use the actual data for data packets
def create_end_packet(sequence_number):
    header = struct.pack(HEADER_FORMAT, sequence_number)
    return header + END_DATA_BYTE  # Use a special value for ACK packets

def parse_packet(packet):
    header_size = struct.calcsize(HEADER_FORMAT)
    header, data = packet[:header_size], packet[header_size:]
    sequence_number,= struct.unpack(HEADER_FORMAT, header)
    is_ack = data == ACK_DATA_BYTE
  
    if is_ack:
        data = None  # No meaningful data in ACK packets
    else:
        data = data.decode()
    return sequence_number, is_ack, data

class GBNNode:
    def __init__(self, self_port, peer_port, window_size, drop_mode, drop_value):
        # Initialize the node with given parameters
        # self_port: The port number for this node
        # peer_port: The port number of the peer node
        # window_size: The size of the Go-Back-N window
        # drop_mode: 'd' for deterministic or 'p' for probabilistic
        # drop_value: The value of n (deterministic) or p (probabilistic)s
        self.port = self_port
        self.peer_port = peer_port
        self.window_size = window_size
        self.drop_mode = drop_mode
        self.drop_value = drop_value

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('', self.port)) 
        self.sequence_number = 0
        self.sending_buffer = []
        self.sending_buffer_size = 20 * window_size  # 20 times window size, this is a virtual limit
        self.sending_buffer_start = 0
        self.base=0 #base of window

        self.send_amount = 0
        self.dropped_amount = 0 
        self.sent_amount = 0
        self.received_amount = 0
        self.allinbuffer = False

        self.paused = True
        self.largest_no_ack = -1 #index of the largest sent but not acked data.

        self.receive_buffer=[]

    def start(self):
        # Start the node operations (sending, receiving, etc.)
        thread = threading.Thread(target=self.receive_packet)
        thread.daemon = True# end when server ends
        thread.start()
        while True:
            command = input("node>")
            if command :
                threading.Thread(target=self.packet2buffer(command), args=(command)).start()
            
            continue

    def packet2buffer(self,command):
        split_parts = command.split("send")
        message = list(split_parts[1].strip() if len(split_parts) > 1 else "")
        if len(message) == 0:
            print("Error: message cannot be empty, use command send abc")
            return  
        
        self.send_amount += len(message)
        self.paused = False
    
        for m in message:
            packet = create_packet(self.sequence_number, m)
            self.sequence_number += 1 #increase sequence number
            self.sending_buffer.append(packet)
           
        
        self.allinbuffer = True
        if self.allinbuffer and self.base == 0:#less than window, force start
            self.send_all_window()
        
        while True:
            if self.largest_no_ack == self.send_amount:
                loss_rate = self.dropped_amount / self.received_amount
                print(f"[Summary] {self.dropped_amount}/{self.received_amount} packets dropped, loss rate = {loss_rate:.3f}")
                current_time = time.time()
                while self.paused==False and time.time() - current_time < 0.5:
                    packet=create_packet(self.sequence_number,b'\x02'.decode())
                    self.send_packet(packet)
                    time.sleep(0.2)
                # packet=create_packet(self.sequence_number,b'\x02'.decode())
                # self.socket.sendto(packet, ('', self.peer_port))
                self.initialize()
                return     
            time.sleep(0.01)
    def send_all_window(self):
        while self.largest_no_ack != self.send_amount:
            self.receive_buffer.clear()
            pre_ack = self.largest_no_ack - 1

            for i in range(self.base, min(self.base + self.window_size, len(self.sending_buffer))):
                self.send_packet(self.sending_buffer[i])
                self.largest_no_ack = i
                _, _, data = parse_packet(self.sending_buffer[i])
                print(f"[{time.time():.3f}] packet{i} {data} sent")
                time.sleep(0.02)

            time.sleep(0.5)

            if len(self.receive_buffer) == 0:
                print(f"[{time.time():.3f}] packet{self.largest_no_ack} timeout")
                continue  # Continue the loop, effectively re-sending the window

            mostrecentack = self.base - 1
            for i in range(len(self.receive_buffer)):
                tm, ack = self.receive_buffer[i]
                if ack > mostrecentack:
                    mostrecentack = ack
                    print(f"{tm} ACK{mostrecentack} received, move window to", min(mostrecentack + 1, self.send_amount-1))
                else:
                    print(f"{tm} ACK{ack} received, move window to", min(mostrecentack + 1, self.send_amount-1))
                    #self.dropped_amount += 1
                time.sleep(0.02)

            self.base = mostrecentack + 1
            self.sending_buffer_start = self.base
            self.largest_no_ack = max(self.base, self.largest_no_ack)

    # def send_all_window_recur(self):
    #     self.receive_buffer.clear()
    #     pre_ack=self.largest_no_ack-1
    #     if(self.largest_no_ack==self.send_amount):
    #         return
    #     for i in range(self.base, min(self.base + self.window_size,len(self.sending_buffer))):
    #         self.send_packet(self.sending_buffer[i])
    #         self.largest_no_ack = i
    #         _,_,data=parse_packet(self.sending_buffer[i])
    #         print(f"[{time.time():.3f}] packet{i} {data} sent")
    #         #print("send packet",i)
    #         time.sleep(0.02)
    #     time.sleep(0.5)
    #     if len(self.receive_buffer) == 0:
    #         print(f"[{time.time():.3f}] packet{self.largest_no_ack} timeout")
    #         self.send_all_window_recur()
    #         return
    #     else:
    #         mostrecentack=self.base-1
    #         for i in range(len(self.receive_buffer)):
    #             tm,ack=self.receive_buffer[i]
    #             if ack>mostrecentack:
    #                 mostrecentack=ack
    #                 print(f"{tm} ACK{mostrecentack} received,move window to",min(mostrecentack+1,self.send_amount))
    #             else:
    #                 print(f"{tm} ACK{self.receive_buffer[i]} discarded")
    #                 self.dropped_amount+=1
    #             time.sleep(0.02)
    #         self.base = mostrecentack+1
    #         self.sending_buffer_start = self.base
    #         self.largest_no_ack = max(self.base,self.largest_no_ack)
    #         self.receive_buffer.clear()
    #         self.send_all_window_recur()
    #     self.receive_buffer.clear()
            
    def send_packet(self, packet):
        self.sent_amount += 1
        self.socket.sendto(packet, ('', self.peer_port))
           

    def receive_packet(self):
        while True:
            packet, sender_address = self.socket.recvfrom(2048)
            threading.Thread(target=self.receive_packet_handler, args=(packet,sender_address)).start()

    def receive_packet_handler(self, packet,sender_address):
        # Method to handle a received packet
        parsed_seq_num, is_ack, parsed_data = parse_packet(packet)
        if parsed_data == b'\x02'.decode(): #close receiver
            self.paused = True
            packet=create_end_packet(self.sequence_number)
            #print("send end packet",packet)
            self.socket.sendto(packet, sender_address)
            
            loss_rate = self.dropped_amount / self.received_amount
            print(f"[Summary] {self.dropped_amount}/{self.received_amount} packets dropped, loss rate = {loss_rate:.3f}")
            self.initialize()
            return
        
        elif parsed_data == b'\x03'.decode(): #close sender
            self.paused = True
            
            return

        self.received_amount+= 1
        # time.sleep(0.1)
        if is_ack:#sender receive ack
            if self.drop_mode == '-d': 
                if (self.received_amount+1) % self.drop_value == 0:
                    print(f"[{time.time():.3f}] ACK{parsed_seq_num } discarded")
                    self.dropped_amount+=1
                    return
            elif self.drop_mode == '-p':
                if random.random() < self.drop_value:
                    print(f"[{time.time():.3f}] ACK{parsed_seq_num } discarded")
                    self.dropped_amount+=1
                    return  
            self.receive_buffer.append((f"[{time.time():.3f}]",parsed_seq_num))
            # if parsed_seq_num == self.base:
            #     self.base += 1
            #     self.sending_buffer_start += 1 #drop the acked one  
            #     self.sent_amount+=1 #increase sent amount
            #     print(self.sent_amount)
            #     print(f"[{time.time():.3f}] ACK{self.base-1} received,move window to",min(self.base,self.send_amount))
            # elif parsed_seq_num > self.base:
            #     print("jumped!")
            #     self.sent_amount+=parsed_seq_num-self.base+1 #increase sent amount
            #     self.base = parsed_seq_num + 1
            #     self.sending_buffer_start = self.base
            #     print(self.sent_amount)
            #     print(f"[{time.time():.3f}] ACK{self.base-1} received,move window to",min(self.base,self.send_amount))
           
            # else:
            #     print(f"[{time.time():.3f}] ACK{parsed_seq_num } discarded")
            #     return

        else:#receiver receive data
            if self.drop_mode == '-d': 
                if (self.received_amount+1) % self.drop_value == 0:
                    print(f"[{time.time():.3f}] packet{parsed_seq_num} {parsed_data} discarded")
                    self.dropped_amount+=1
                    return
            elif self.drop_mode == '-p':
                if random.random() < self.drop_value:
                    print(f"[{time.time():.3f}] packet{parsed_seq_num} {parsed_data} discarded")
                    self.dropped_amount+=1
                    return
                  
            print(f"[{time.time():.3f}] packet{parsed_seq_num} {parsed_data} received")
            if parsed_data == b'\x03'.decode():
                return


                
            
            
            if parsed_seq_num == self.sequence_number:
                threading.Thread(target=self.send_ack, args=(parsed_data, self.sequence_number, sender_address)).start()
                self.sequence_number += 1
            else:
                threading.Thread(target=self.send_ack, args=(parsed_data, self.sequence_number-1, sender_address)).start()

    def send_ack(self,parsed_data,sequence,sender_address):
        if sequence == -1:#meaningless ack
            return
        packet = create_packet(sequence,parsed_data,is_ack=True)
        self.socket.sendto(packet, sender_address)
        print(f"[{time.time():.3f}] ACK{sequence} sent, expecting {sequence+1}")
    
    def initialize(self):
        self.sequence_number = 0
        self.sending_buffer = []
        self.sending_buffer_size = 20 * window_size  # 2 times window size, this is a virtual limit
        self.sending_buffer_start = 0
        self.base=0 #base of window

        self.send_amount = 0
        self.sent_amount = 0
        self.paused = True
        self.largest_no_ack = -1 #index of the largest sent but not acked data.

        self.send_amount = 0
        self.discarded_amount = 0
        self.received_amount=0  
        self.sent_amount = 0    
        self.dropped_amount = 0 
# Example usage
if __name__ == "__main__":
    if len(sys.argv) != 6:
        print("Usage: python gbnnode.py self_port peer_port window_size drop_mode drop_value")
        sys.exit(1)

    # Extract arguments
    self_port = int(sys.argv[1])
    peer_port = int(sys.argv[2])
    window_size = int(sys.argv[3])
    drop_mode = sys.argv[4]
    drop_value = float(sys.argv[5])

    # Validate drop_mode
    if drop_mode not in ['-p', '-d']:
        print("Error: drop_mode must be '-p' for probabilistic or '-d' for deterministic")
        sys.exit(1)

    # Instantiate and start a GBNNode
    node = GBNNode(self_port=self_port, peer_port=peer_port, window_size=window_size, drop_mode=drop_mode, drop_value=drop_value)
    node.start()