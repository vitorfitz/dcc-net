from utils import *
import sys
from threading import Thread

arg_addr = sys.argv[1]
arg_gas = sys.argv[2]

addr_str = arg_addr.split(":")
if len(addr_str) != 2:
    print("Client address format should be <address>:<port>")
    exit(-1)
conn = socket.socket(get_ip_type(addr_str[0], addr_str[1]), socket.SOCK_STREAM)
conn.settimeout(1)
conn.connect((addr_str[0], int(addr_str[1])))
print("connection stablished")

sender_queue = Queue()

sender_queue.put_nowait(DCCNETFrame(arg_gas+"\n", 0, 0, 0, 0))

end = False
rst = False

last_sent = None

rth = Thread(target=receiver, args=(conn, sender_queue, [rst], [end], [last_sent]))
sth = Thread(target=sender, args=(conn, sender_queue, [last_sent], [rst]))

rth.start()
sth.start()

while not(end) and not(rst):
    pass

if end:
    sender_queue.join()

conn.close()
