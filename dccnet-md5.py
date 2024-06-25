from utils import *
import sys
from classes import *

arg_addr = sys.argv[1]
arg_gas = sys.argv[2]

conn = Connection(arg_addr)
fq = FrameQueue()

msg = arg_gas + '\n'

fq.put(Frame(0, 0, msg))

rth = Receiver(conn, fq)
sth = Sender(conn, fq)

rth.start()
# sth.start()

while True:
	pass

conn.close()
