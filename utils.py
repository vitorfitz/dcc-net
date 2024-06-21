import struct
import socket

HEADER_SIZE = 6
SYNC_STRING = 2 * bytearray((0xDCC023C2).to_bytes(4, byteorder="big"))
SYNC_SIZE = len(SYNC_STRING)
MAX_FRAME_SIZE = 2 ** 16


def get_ip_type(hostname, port_):
	addr = socket.getaddrinfo(hostname, port_, 0, 0, socket.SOL_UDP)[0][4][0]
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


def write_frame(data, id_, is_last):
	flags = (len(data) == 0) << 7 | is_last << 6
	header = bytearray(struct.pack(">IIHHBB", 0xDCC023C2, 0xDCC023C2, 0, len(data), id_, flags))
	frame = header + data
	# print(list(frame[8:]))
	checksum = calculate_checksum(frame[SYNC_SIZE:])
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

		unpacked = struct.unpack(">HHBB", header)
		expected_check = unpacked[0]
		size = unpacked[1]

		data = bytearray(conn.recv(size))
		if len(data) != size:
			continue

		frame = header + data
		frame[:2] = (0).to_bytes(2, byteorder="big")
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
		lines[-1] = lines[-1][:len(lines[-1])-1]

	return lines
