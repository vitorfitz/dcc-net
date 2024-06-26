import struct
import socket
from queue import Queue
import time
from typing import List

HEADER_SIZE = 7
SYNC_SEQUENCE = 0xDCC023C2
SYNC_STRING = 2 * bytearray(SYNC_SEQUENCE.to_bytes(4, byteorder="big"))
SYNC_SIZE = 8
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


def calculate_checksum(data: bytes) -> int:
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


class DCCNETFrame:
    def __init__(self, data: str, fid: int, is_ack: bool = False, is_end: bool = False, is_rst: bool = False) -> None:
        self.data = data
        self.fid = fid
        self.is_ack = is_ack
        self.is_end = is_end
        self.is_rst = is_rst
        
    def encode(self) -> bytearray:
        flags = 0
        flags = flags | (self.is_ack * ACK_FLAG)
        flags = flags | (self.is_end * END_FLAG)
        flags = flags | (self.is_rst * RST_FLAG)
        
        package = struct.pack("!IIHHHB", SYNC_SEQUENCE, SYNC_SEQUENCE, 0, len(self.data), self.fid, flags)
        package = bytearray(package)
        package += bytearray(self.data.encode("ASCII"))
        
        chk = calculate_checksum(package)
        
        package[SYNC_SIZE:SYNC_SIZE+2] = chk.to_bytes(2, 'big')
        
        return package


def receiver(conn: socket.socket, fq: Queue, rst: List[bool], end: List[bool], last_sent: List[int], pq: Queue) -> None:
    pq.put("started receiving")
    
    while True:
        time.sleep(0.01)
        try:
            sync_recvd = conn.recv(SYNC_SIZE)
            
            sync0, sync1 = struct.unpack("!II", sync_recvd)
            
            if sync0 != SYNC_SEQUENCE or sync1 != SYNC_SEQUENCE:
                continue
            
            header_recvd = conn.recv(HEADER_SIZE)
            
            chksum_recvd, len_recvd, id_recvd, flags_recvd = struct.unpack("!HHHB", header_recvd)
            
            data_recvd = conn.recv(len_recvd)
            
            tmp_frame_recvd = SYNC_STRING+bytearray((0).to_bytes(2, 'big'))+bytearray(header_recvd[2:])+bytearray(data_recvd)
            chksum = calculate_checksum(tmp_frame_recvd)
            
            if chksum != chksum_recvd:
                continue
            
            is_ack = (ACK_FLAG & flags_recvd) == ACK_FLAG
            is_end = (END_FLAG & flags_recvd) == END_FLAG
            is_rst = (RST_FLAG & flags_recvd) == RST_FLAG

            pq.put(f"data recvd:\t{data_recvd.decode('ASCII')}, flags:\t{bin(flags_recvd)}")
            
            end[0] = is_end
            rst[0] = is_rst
            
            if rst[0]: return
            
            # if received a non ack frame, send an ack
            if not(is_ack):
                fq.put(DCCNETFrame("", id_recvd, True, False, False))
            
            if is_ack:
                last_sent[0] = None
        
        except:
            continue
            
        
def sender(conn: socket.socket, fq: Queue, last_sent: List[int], rst: List[bool], pq: Queue) -> None:
    pq.put("started sending")
    
    while True:
        while last_sent[0] != None: time.sleep(0.01)
        
        frame = fq.get()
        fid = frame.fid
        
        frame = frame.encode()
        
        pq.put(frame)
        
        attempts = 0
        last_sent[0] = fid
        while attempts < 16 and last_sent[0] != None:
            try:
                conn.send(frame)
        
            except socket.timeout:
                continue
        
        if attempts >= 16:
            rst = True
        else: pq.put("sent frame")
