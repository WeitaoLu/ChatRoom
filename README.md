# ChatRoom
Programming Project. Designed protocols on UDP. Enables person to person chatting, broadcast , GBN, and Bellman ford routing.

## Packet structure

4 bit is used for sequence number and 1 bit is used for data. The length of every packet in section2 GBN and the probe packet in section 4 CNN is 5.
there are some control data bit. \x00 is ACK. \x02 is a mseg to close receiver.  \x03 is used to close sender after receiver get \x02

## Functions and Classes.

### GBNNode:
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

### DVnode:
    send_routing_table:
    send routing_table to all neighbours.

    receive_routing_table:
    The receive logic is similar to that in GBNNode, except that it will runs update_routing_table.
    A state called self.send_state is used to ensure at least one send.(also helpful for initialize and handle idle state.)

    update_routing_table:
    based on Bellman-Ford Algorithm to update local routing table based on the sent one.


### CNnode:
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
### HOW TO USE ChataAPP
Fllow the commands as shown in testexamples.

### HOW TO USE ChataAPP
Set up:
CD to root
Run Server:  ./ChatApp -s <port>
Run Client: ./ChatApp -c <name> <server-ip> <server-port> <client-port>

Ctrl+C: exit Server/Client

The following commands are for clients only:
Communicate Command:
send message to 1 clients: send <name> <message>
broadcast message to all clients: send_all <message>

De-register://only can be used when active,will turn the state to idle
dereg

Re-register://only can be used when idle
reg

## Function definitions

### Class ChatServer contains:
    
    _init_ : function to initiate basic settings including name,port,etc.
    start: main function. initiate receive thread and do forever while loop to keep server active.

### Thread Functions:
    receive_messages:thread to receive message and allocate it to other thread to response.
    handle_registration: thread to handle reg request of new client, old client ,and re-reg client.
    handle_deregistration: thread to handle dereg request
    handle_offline:thread to handle offline msgs sent to server and decide if need to store it.
    handle_groupchat:thread to handle send_all request.Send to all active users and store for all offline users.

### Tools Functions:(to be used in different threads and make programming easier)
    send_message_to_client_byaddress: given an address, send to client.
    send_message_to_client_byname: given a name, look up address and send to client.
    get_address_by_name:look up address using name.Useful in many functions.
    get_name_by_address:look up name using address.Useful in many functions.
    send_ACK:send ACK to 1 client.
    synstate_to_client:synchronize client table with one client.
    broadcastsyn:synchronize client table with all online client.

### Class ChatClient contains:

    _init_:function to initiate basic settings including name,port,etc.
    start: main function. initiate receive thread and do forever while loop to keep server active.
    There are two states in start, True means client is active and False means client is deregistered.
    The while loop in start also handles input. Once a input is typed by user,it will be checked and allocate to thread to solve it.

### Tool Functions:(to used in other threads and start function)
    check_command: a function to check Valid Commands.
    send_message: send message to a target address.
    send_ACK: send ACK to a a target address.

### Thread Functions:
    receive_messages:thread to receive , only active when client state is active(online).receive message then print outputs and send ACKs.
    process_sending_client_command:thread to send message to 1 client.If timeout send to server a offline_message.
    process_sending_all_command:thread to send message to server and let it send to all online and offline users in client table.
    process_sending_offline_command:tool to send offline message to server and check ack state.
    process_dereg_command:thread to solve dereg command,tell server and wait for ack.
    regagain:change state from dereg(offline) state to active(online) state. send reg to server.
    string_to_tuple:tool to change a 'tuple-like' string to tuple. 
    Useful in syn client tables because my key is tuple and when Server send it it becomes string.



