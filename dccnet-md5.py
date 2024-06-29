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
b = Buffer(s)

s.settimeout(1)
s.connect((addr_str[0], int(addr_str[1])))

print(f"connecting to address {addr_str[0]}:{addr_str[1]}")

msg = arg_gas + '\n'

frame = make_frame(msg, 0, 0)

res = send_frame(s, frame, 0, b)
if res == RST_FLAG:
    print("received RST")
    exit(-1)

if res == END_FLAG:
    print("received END")
    exit(-1)

run = True
buff = ""
unresolved = ""
current_id = 1

while run:
    data, is_ack, is_end, is_rst = recv_frame(s, b)

    if data == None:
        continue

    if is_ack: continue
    if is_end: run = False
    if is_rst: break

    lines, ur2 = frame_to_ascii(data)
    if len(lines)>0:
        lines[0] = unresolved + lines[0]
        unresolved = ur2
    else:
        unresolved = unresolved+ur2

    for line in lines:
        l = buff + line

        chk = hashlib.md5(l[:-1].encode('ASCII')).hexdigest()+"\n"

        frame = make_frame(chk, current_id, False)

        send_frame(s, frame, current_id, b)#AQUI ELE TA RETORNANDO UM TREM QUE NAO É ACK NO CASO DE RETRANSMISSÃO
        current_id = int(not(bool(current_id)))
        print()

s.close()
