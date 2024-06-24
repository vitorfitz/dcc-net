from utils import *
import sys
import socket

arg_addr = sys.argv[1]
arg_gas = sys.argv[2]

addr_str = arg_addr.split(":")
if len(addr_str) != 2:
    print("Client address format should be <address>:<port>")
    exit(-1)

s = socket.socket(get_ip_type(addr_str[0], addr_str[1]), socket.SOCK_STREAM)

s.settimeout(1)
s.connect((addr_str[0], int(addr_str[1])))

print(f"connecting to address {addr_str[0]}:{addr_str[1]}")

msg = arg_gas + '\n'

frame = make_frame(msg, 0, 0)

print(f"sending GAS on frame:\t{frame}")

send_frame(s, frame, 0)

run = True
buff = ""
current_id = 1
while run:
    data, is_ack, is_end, is_rst = recv_frame(s)
    
    if is_ack: continue
    if is_end: run = False
    if is_rst: break

    if data == None:
        print(is_ack, is_end, is_rst)
        continue
    
    lines = frame_to_ascii(data)
    
    for line in lines:
        l = buff + line
        
        is_end = int(line==lines[-1]) * END_FLAG
        
        current_id += 1
        
        frame = make_frame(l, current_id, is_end)
        
        send_frame(socket, frame, current_id)

s.close()
