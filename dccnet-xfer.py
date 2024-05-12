import socket
import struct
import sys

client_or_server=sys.argv[1]
arg_addr=sys.argv[2]
arg_input=sys.argv[3]
arg_output=sys.argv[4]

def calculate_checksum(data):
	checksum = 0
	# Sum up 16-bit words
	for i in range(0, len(data), 2):
		# If data has odd length, pad with zero byte
		if i + 1 < len(data):
			word = (data[i] << 8) + data[i + 1]
			checksum += word
		else:
			word = (data[i] << 8)
			checksum += word

	# Add carry to the result
	while checksum >> 16:
		checksum = (checksum & 0xFFFF) + (checksum >> 16)

	# One's complement
	checksum = ~checksum & 0xFFFF

	return checksum


header_size=6
sync_string=2*bytearray((0xDCC023C2).to_bytes(4,byteorder="big"))
sync_size=len(sync_string)

def write_frame(data,id,is_last):
	flags=(len(data)==0)<<7 | is_last<<6
	header=bytearray(struct.pack(">IIHHBB",0xDCC023C2,0xDCC023C2,0,len(data),id,flags))
	frame=header+data
	# print(list(frame[8:]))
	checksum=calculate_checksum(frame[sync_size:])
	frame[sync_size:sync_size+2]=checksum.to_bytes(2,byteorder="big")
	return frame,checksum

def read_frame(conn):
	while True:
		read=bytearray(conn.recv(sync_size))
		if not read or len(read)<sync_size: return None

		while True:
			last_8=read[-sync_size:]
			if last_8==sync_string:
				break
			
			if len(read)>1000:
				read=last_8
			
			byte=conn.recv(1)
			if not byte: return None
			read.append(byte[0])

		header = bytearray(conn.recv(header_size))
		if not header or len(header)!=header_size: return None

		unpacked=struct.unpack(">HHBB",header)
		expected_check=unpacked[0]
		size=unpacked[1]

		data=bytearray(conn.recv(size))
		if not data: return None
		if len(data)!=size: continue

		frame=header+data
		frame[:2]=(0).to_bytes(2,byteorder="big")
		checksum=calculate_checksum(frame)
		if checksum!=expected_check: continue

		return unpacked,data

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
	if client_or_server=="-c":
		input=open(arg_input,"rb")

		addr_str=arg_addr.split(":")
		if len(addr_str)!=2:
			print("Client address format should be <address>:<port>")
			exit(-1)

		s.settimeout(1)
		s.connect((addr_str[0], int(addr_str[1])))
		in_bytes=bytearray(input.read(2**16))
		if(len(in_bytes)>=2**16):
			print("Maximum frame size is 65535")
			exit(-1)

		frame,check=write_frame(in_bytes,0,True)
		# exit(0)
		attempts=0
		data=None
		
		while attempts<60 and data==None:
			try:
				s.sendall(frame)
				data = s.recv(header_size+sync_size)
				print("received ack "+str(len(data)))
			except socket.timeout:
				attempts+=1

	else:
		output=open(arg_output,"wb")
		s.bind(("127.0.0.1",int(arg_addr)))
		s.listen()
		conn, addr = s.accept()
		
		with conn:
			print(f"Connected by {addr}")
			_,data=read_frame(conn)
			output.write(data)
			frame,_=write_frame(bytearray(),0,True)
			conn.sendall(frame)
		
finally:
	s.close()