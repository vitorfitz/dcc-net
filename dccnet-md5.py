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

res = send_frame(s, frame, 0)
if res == RST_FLAG:
    print("received RST")
    exit(-1)

if res == END_FLAG:
    print("received END")
    exit(-1)

run = True
buff = ""
current_id = 1
while run:
    data, is_ack, is_end, is_rst = recv_frame(s)
    
    if data == None:
        print(is_ack, is_end, is_rst)
        continue

    if is_ack: continue
    if is_end: run = False
    if is_rst: break

    lines = frame_to_ascii(data)
    
    for line in lines:
        l = buff + line
        
        chk = hashlib.md5(l[:-1].encode('ASCII')).hexdigest()+"\n"

        frame = make_frame(chk, current_id, False)
        
        send_frame(s, frame, current_id)#AQUI ELE TA RETORNANDO UM TREM QUE NAO É ACK NO CASO DE RETRANSMISSÃO
        '''received data
            checksum        |61163 == 61163
            flags           |
            data            |entering phase 2 retransmission test


            sent ack frame  |bytearray(b'\xdc\xc0#\xc2\xdc\xc0#\xc2~\xf8\x00\x00\x00\x01\x80')

            sent frame      |bytearray(b'\xdc\xc0#\xc2\xdc\xc0#\xc24\xf3\x00!\x00\x00\x000e30c4436289108150c5679f4531ff30\n')

            sent frame      |bytearray(b'\xdc\xc0#\xc2\xdc\xc0#\xc24\xf3\x00!\x00\x00\x000e30c4436289108150c5679f4531ff30\n')

            received frame
            checksum        |54972 == 54972
            flags           |
            data            |second message cannot be answered immediately due to missing ack
            
            ISSO NAO TA SENDO TRATADO NO CODIGO, E IMAGINO QUE TENHA Q MANDAR UM ACK NESSES CASOS.
            '''
        
        current_id = int(not(bool(current_id)))
        print()

s.close()
