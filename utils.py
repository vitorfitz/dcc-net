import hashlib
import struct
import socket
import time
from typing import List

HEADER_SIZE = 7
SYNC_SEQUENCE = 0xDCC023C2
SYNC_STRING = 2 * bytearray(SYNC_SEQUENCE.to_bytes(4, byteorder="big"))
SYNC_SIZE = len(SYNC_STRING)
MAX_FRAME_SIZE = 2**16

ACK_FLAG = 0x80
END_FLAG = 0x40
RST_FLAG = 0x20


class Buffer:
    def __init__(self, conn):
        self.ba = bytearray()
        self.pos = 0
        self.conn = conn

    def recv(self, bytes):
        avail = len(self.ba) - self.pos
        if bytes >= avail:
            msg = self.ba[self.pos :]
            if bytes > avail:
                msg += self.conn.recv(bytes - avail)
            self.pos = 0
            self.ba = bytearray()
            return msg
        else:
            old_pos = self.pos
            self.pos += bytes
            return self.ba[old_pos : self.pos]

    def send(self, msg):
        self.ba.extend(msg)


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
            word = data[i] << 8
            checksum += word

    # Add carry to the result
    while checksum >> 16:
        checksum = (checksum & 0xFFFF) + (checksum >> 16)

    # One's complement
    checksum = ~checksum & 0xFFFF

    return checksum


def write_frame(data: bytes, id_: int, is_last: bool):
    flags = (len(data) == 0) << 7 | is_last << 6
    header = bytearray(
        struct.pack("!IIHHHB", 0xDCC023C2, 0xDCC023C2, 0, len(data), id_, flags)
    )
    frame = header + data
    checksum = calculate_checksum(frame)
    frame[SYNC_SIZE : SYNC_SIZE + 2] = checksum.to_bytes(2, byteorder="big")
    return frame, checksum


lastID = -1
lastCHK = -1


def read_frame(conn: socket.socket, recv):
    global lastID, lastCHK
    while True:
        read = bytearray(recv(SYNC_SIZE))

        if not read or len(read) < SYNC_SIZE:
            print("none here 95")
            return None

        while True:
            last_8 = read[-SYNC_SIZE:]
            if last_8 == SYNC_STRING:
                break

            if len(read) > 1000:
                read = last_8

            byte = recv(1)
            if not byte:
                print("none here 108")
                return None

            read.append(byte[0])

        header = bytearray(recv(HEADER_SIZE))
        if not header or len(header) != HEADER_SIZE:
            print("none here 115")
            return None

        unpacked = struct.unpack("!HHHB", header)
        expected_check = unpacked[0]
        size = unpacked[1]

        data = bytearray(recv(size))
        if len(data) != size:
            print("Size does not match\n")
            continue

        frame = SYNC_STRING + header + data
        frame[8:10] = (0).to_bytes(2, byteorder="big")
        checksum = calculate_checksum(frame)
        if checksum != expected_check:
            print("Checksum does not match\n")
            continue

        if checksum == lastCHK and unpacked[2] == lastID:
            print("Duplicate frame\n")
            ack_frame = make_frame("", lastID, ACK_FLAG)
            conn.sendall(ack_frame)
            continue
        lastCHK = checksum
        lastID = unpacked[2]
        frame[8:10] = checksum.to_bytes(2, byteorder="big")

        return unpacked, data, frame


def frame_to_ascii(bytes_data: bytes):
    str_data = bytes_data.decode("ASCII")

    lines = []

    line = ""
    for i in range(len(str_data)):
        line += str_data[i]

        if str_data[i] == "\n":
            lines.append(line)
            line = ""

    return lines, line


def make_frame(data: str, id_: int, flags: int) -> bytearray:
    if len(data) >= MAX_FRAME_SIZE:
        print("Maximum frame size is 65535")
        exit(-1)

    data_bytes = data.encode("ASCII")

    msg = bytearray(
        struct.pack(
            "!IIHHHB", SYNC_SEQUENCE, SYNC_SEQUENCE, 0, len(data_bytes), id_, flags
        )
    )

    msg += data_bytes

    checksum = calculate_checksum(msg)
    msg[SYNC_SIZE : SYNC_SIZE + 2] = checksum.to_bytes(2, byteorder="big")

    return msg


def send_frame(conn: socket.socket, frame: bytearray, id_: int, b: Buffer) -> int:
    attemps = 0

    while attemps < 16:
        try:
            conn.sendall(frame)
            print(str(attemps) + f" sent frame\t|{frame}\n")

            unpacked, data, frame2 = read_frame(conn, conn.recv)
            check, length, received_id, flags = unpacked

            print(f"received frame")
            print(f"checksum\t|{check}")
            print(f"flags", end="\t\t|")
            if (flags & ACK_FLAG) >> 7:
                print(f"ACK", end="\t")
            if (flags & END_FLAG) >> 6:
                print(f"END", end="\t")
            if (flags & RST_FLAG) >> 5:
                print(f"RST", end="\t")
            print()

            print(f"data\t\t|{data.decode('ASCII')}\n")

            if END_FLAG & flags == END_FLAG:
                return END_FLAG

            if RST_FLAG & flags == RST_FLAG:
                return RST_FLAG

            if ACK_FLAG & flags == ACK_FLAG:
                if received_id != id_:
                    attemps += 1
                    continue
                return ACK_FLAG

            b.send(frame2)

        except socket.timeout:
            attemps += 1

    print("failed to send message id: ", id_)
    return 0


def recv_frame(conn: socket.socket, b: Buffer) -> bytes:
    attempts = 16
    while True:
        try:
            unpacked, data, _ = read_frame(conn, b.recv)
            break
        except TimeoutError as e:
            if attempts == 0:
                raise e
            attempts -= 1
            continue
    check, length, received_id, flags = unpacked

    is_ack = False
    is_end = False
    is_rst = False

    if (flags & ACK_FLAG) == ACK_FLAG:
        is_ack = True
    if (flags & END_FLAG) == END_FLAG:
        is_end = True
    if (flags & RST_FLAG) == RST_FLAG:
        is_rst = True

    print(f"received data")
    print(f"checksum\t|{check}")
    print(f"flags", end="\t\t|")
    if (flags & ACK_FLAG) == ACK_FLAG:
        print(f"ACK", end="\t")
    if (flags & END_FLAG) == END_FLAG:
        print(f"END", end="\t")
    if (flags & RST_FLAG) == RST_FLAG:
        print(f"RST", end="\t")
    print()
    print(f"data\t\t|{data.decode('ASCII')}\n")

    ack_frame = make_frame("", received_id, ACK_FLAG)
    conn.sendall(ack_frame)
    print(f"sent ack frame\t|{ack_frame}\n")

    return data, is_ack, is_end, is_rst
