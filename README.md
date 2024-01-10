# ChatRoom
Programming Project. Designed protocols on UDP. Enables person to person chatting, broadcast , GBN, and Bellman ford routing.

## Packet structure

4 bit is used for sequence number and 1 bit is used for data. The length of every packet in section2 GBN and the probe packet in section 4 CNN is 5.
there are some control data bit. \x00 is ACK. \x02 is a mseg to close receiver.  \x03 is used to close sender after receiver get \x02

## Functions and Classes.

# GBNNode:
    packet2buffer:
    This is the main thread. Which packs and pushes packets into sending buffer. Start sending_window and print summary when sending ends.

    send_all_window:
    This is the thread to simulate GBN sending.
    The logic is to sending current window and wait for 5s (start on most recent sent). 
    If timeout, then resend current window. If not, move the window to the most recent acked+1.
    This is a non-recursive version and will keep sending until all data is sent.

    receive_packet and receive_packet_handler:
    receive_packet is the listening thread which keeps receiving packets.
    The received_packet packets will be processed in a receive_packet_handler thread.
    It's so designed to minimize the receive_packet process time and minimize UDP trans lost.

    receive_packet_handler:
    When the packet is ack, it will be processed in sending_window through a buffer .
    When the packet is not ack, it will sending an ack to the sender.
    when the packet is \x02 or \x03. it will inform the sender/receiver the sending process is end, and initialize both for further transmission.

--DVnode:
    send_routing_table:
    send routing_table to all neighbours.

    receive_routing_table:
    The receive logic is similar to that in GBNNode, except that it will runs update_routing_table.
    A state called self.send_state is used to ensure at least one send.(also helpful for initialize and handle idle state.)

    update_routing_table:
    based on Bellman-Ford Algorithm to update local routing table based on the sent one.


--CNnode:
    This is a complex combination of GBNNode and DVnode. The difference in functions are highlighted below.

    In this section, every connenction has an independent sequence number for sending and an independent sequence number for ack.
    
    send_all_window(port):
    This is used to continously send Probe packets. To save space, the sending buffer is fixed to length =10, the sequence number will looped from 0~9, 
    and the window will move to start once the it reaches the end.(the window can be 8,9,0,1,2). So it will keep sending forever.

    Also the sending and receive_packet_handler now all has an arg port, which is used for node to node connection.
    The receive_packet thread is to recieve data and allocate it to correct connenction.

    update_routing_table:
    Since the information can be out-dated,besides Bellman-Ford, many other constrains are designed to solve conflicts.
    Please see the codes line234 for more details.The main idea is when receive a table,trust sender more(the sender in probing) and 
    neglect the direct distance sending from receiver to sender(if the nexthop is also sender).
    
    check_table_consistency: This is used to solve the problem discussed in ED#383
    
    check_neighbour_consistency: This is used to check the consistency between self.neighbours and self.routing_table. 

    self.neighbors is used to store the calculated/received distance between the nodes and its neighbors.

– An overview of any data structures used
    In Section2, sending buffer is simply a list. In section 4 , it's a fixed 10 size array.

    In section2, sequence number is just an int, so one node can connected to multiple nodes at same time but can only sending/receiving from one node.
    In section4, I improved this so one node can sending/recieving to multiple nodes at the same time with no conflict.
    The nodes has a sequence number array for all its neightbors, also an independent receive buffer.

    The recieve buffer is designed because the reply of the receive is too fast and packets may lost while the 
    receive_packet thread is parasing, alloacating and handling the packet. I noticed this problem and applied a buffer to solve it.
    It will not break the recieve order of the packets, just to ensure packet can be dropped only on our Emulation method.

– Any bugs that remain in your submission
    The print information sometimes is reordered and not according to the timestamp because they are in different thread.
    Refer to the timestamp if there's conflict
    As far as I know, I tested all sections both locally and on Google Cloud in Ubtuntu 20.04
    using the test case provided in the PDF and every test is passed and converges well.
    Since I only used a limited test cases,there may be some case I missed and unexpected errors.

    I don't add any input constraints, and any logic in the rubric is programmed and tested.

