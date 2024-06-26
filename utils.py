import struct
import socket
import time
from typing import List

HEADER_SIZE = 7
SYNC_SEQUENCE = 0xDCC023C2
SYNC_STRING = 2 * bytearray(SYNC_SEQUENCE.to_bytes(4, byteorder="big"))
SYNC_SIZE = len(SYNC_STRING)
MAX_FRAME_SIZE = 2 ** 16

ACK_FLAG = 0x80
END_FLAG = 0x40
RST_FLAG = 0x20


def get_ip_type(hostname, port_):
	addr = socket.getaddrinfo(hostname, port_, 0, 0, socket.SOL_SOCKET)[0][4][0]
	try:
		socket.inet_pton(socket.AF_INET6, addr)
		return socket.AF_INET6
	except:
		pass

	try:
		socket.inet_pton(socket.AF_INET, addr)
		return socket.AF_INET
	except:
		pass

	return None


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


def write_frame(data: bytes, id_: int, is_last: bool):
	flags = (len(data) == 0) << 7 | is_last << 6
	header = bytearray(struct.pack("!IIHHHB", 0xDCC023C2, 0xDCC023C2, 0, len(data), id_, flags))
	frame = header + data
	checksum = calculate_checksum(frame)
	frame[SYNC_SIZE:SYNC_SIZE + 2] = checksum.to_bytes(2, byteorder="big")
	return frame, checksum


def read_frame(conn: socket.socket):
	while True:
		read = bytearray(conn.recv(SYNC_SIZE))
		if not read or len(read) < SYNC_SIZE:
			return None

		while True:
			last_8 = read[-SYNC_SIZE:]
			if last_8 == SYNC_STRING:
				break

			if len(read) > 1000:
				read = last_8

			byte = conn.recv(1)
			if not byte:
				return None

			read.append(byte[0])

		header = bytearray(conn.recv(HEADER_SIZE))
		if not header or len(header) != HEADER_SIZE:
			return None

		unpacked = struct.unpack("!HHHB", header)
		expected_check = unpacked[0]
		size = unpacked[1]

		data = bytearray(conn.recv(size))
		if len(data) != size:
			continue

		frame = SYNC_STRING + header + data
		frame[8:10] = (0).to_bytes(2, byteorder="big")
		checksum = calculate_checksum(frame)
		if checksum != expected_check:
			continue

		return unpacked, data


def frame_to_ascii(bytes_data: bytes):
	str_data = bytes_data.decode("ASCII")

	lines = str_data.split("\n")

	for line in lines:
		line += '\n'

	if str_data.endswith('\n'):
		lines[-1] = lines[-1][:len(lines[-1]) - 1]

	return lines


def make_frame(data: str, id_: int, flags: int) -> bytearray:
	if len(data) >= MAX_FRAME_SIZE:
		print("Maximum frame size is 65535")
		exit(-1)
	
	data_bytes = data.encode("ASCII")

	msg = bytearray(struct.pack("!IIHHHB", SYNC_SEQUENCE, SYNC_SEQUENCE, 0, len(data_bytes), id_, flags))
 
	msg += data_bytes

	checksum = calculate_checksum(msg)
	msg[SYNC_SIZE:SYNC_SIZE+2] = checksum.to_bytes(2, byteorder='big')

	return msg


def send_frame(conn: socket.socket, frame: bytearray, id_: int) -> int:
	attemps = 0

	while attemps < 16:
		try:
			conn.sendall(frame)

			frame_received = conn.recv(SYNC_SIZE+HEADER_SIZE)

			sync0, sync1, expected_check, length, received_id, flags = struct.unpack("!IIHHHB", frame_received)

			if SYNC_SEQUENCE != sync0 or SYNC_SEQUENCE != sync1:
				attemps += 1
				continue

			data = conn.recv(length)

			tmp_frame = bytearray(frame_received+data)
			tmp_frame[SYNC_SIZE:SYNC_SIZE+2] = (0).to_bytes(2, 'big')

			check = calculate_checksum(tmp_frame)
   
			print(f"checksum\t|{check} == {expected_check}")
			print(f"flags", end="\t\t|")
			if (flags & ACK_FLAG) >> 7: print(f"ACK", end="\t")
			if (flags & END_FLAG) >> 6: print(f"END", end="\t")
			if (flags & RST_FLAG) >> 5: print(f"RST", end="\t")
			print()
   
			print(f"data\t\t|{data.decode('ASCII')}")
   
			if check != expected_check:
				time.sleep(1)

			if END_FLAG & flags == END_FLAG:
				return END_FLAG

			if RST_FLAG & flags == RST_FLAG:
				return RST_FLAG

			if received_id == id_:
				time.sleep(1)

			if ACK_FLAG & flags == ACK_FLAG:
				return ACK_FLAG

		except socket.timeout:
			attemps += 1

	print("failed to send message id: ", id_)
	return 0

def recv_frame(conn: socket.socket) -> bytes:
	try:
		frame_received = conn.recv(SYNC_SIZE+HEADER_SIZE)
		
		sync0, sync1, expected_check, length, received_id, flags = struct.unpack("!IIHHHB", frame_received)

		if SYNC_SEQUENCE != sync0 or SYNC_SEQUENCE != sync1:
			raise Exception("Synchronization sequence not found")

		data = conn.recv(length)

		tmp_frame = bytearray(frame_received+data)
		tmp_frame[SYNC_SIZE:SYNC_SIZE+2] = (0).to_bytes(2, 'big')

		check = calculate_checksum(tmp_frame)

		if check != expected_check:
			raise Exception("Checksum does not match")

		ack_frame = make_frame("", received_id, ACK_FLAG)
		conn.sendall(ack_frame)

		is_ack = False
		is_end = False
		is_rst = False

		if (flags & ACK_FLAG) >> 7: is_ack = True
		if (flags & END_FLAG) >> 6: is_end = True
		if (flags & RST_FLAG) >> 5: is_rst = True

		return data, is_ack, is_end, is_rst

	except:
		return None, False, False, False

def send_frame_wrapper(s: socket.socket , frame: bytes, current_id: List[int] , last_sent: List[bytes|int]):
    send_frame(s, frame, current_id[0])
    last_sent = [frame, current_id]
    current_id[0] = int(not(bool(current_id[0])))
