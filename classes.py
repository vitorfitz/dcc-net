import socket
from threading import Lock, Thread
import queue
import utils
import struct
import time


class Connection:
    conn: socket.socket
    mutex: Lock

    def __init__(self, addr: str):
        addr_str = addr.split(":")
        if len(addr_str) != 2:
            print("Client address format should be <address>:<port>")
            exit(-1)
        self.conn = socket.socket(utils.get_ip_type(addr_str[0], addr_str[1]), socket.SOCK_STREAM)
        self.conn.settimeout(1)
        self.conn.connect((addr_str[0], int(addr_str[1])))
        self.mutex = Lock()

    def close(self):
        self.conn.close()

    def lock(self):
        self.mutex.acquire()

    def release(self):
        self.mutex.release()

    def recv(self, bufsize: int) -> bytes:
        return self.conn.recv(bufsize)

    def send(self, data: bytes) -> int:
        return self.conn.send(data)


class FrameQueue(queue.Queue):
    def __init__(self):
        self.mutex = Lock()
        super().__init__()


class Receiver:
    conn: Connection
    queue: FrameQueue
    th: Thread

    def __init__(self, conn: Connection, fq: FrameQueue):
        self.conn = conn
        self.queue = fq

    def start(self):
        self.th = Thread(target=self.__run)
        self.th.start()

    def __run(self):
        while True:
            try:
                self.conn.lock()

                header = self.conn.recv(utils.SYNC_SIZE + utils.HEADER_SIZE)

                sync0, sync1, expected_chksum, length, recv_id, flags = struct.unpack("!IIHHHB", header)

                if sync0 != utils.SYNC_SEQUENCE or sync1 != utils.SYNC_SEQUENCE:
                    self.conn.release()
                    time.sleep(0.05)
                    continue

                data = self.conn.recv(length)

                frame_tmp = header[:utils.SYNC_SIZE] + (0).to_bytes(2, 'big') + header[utils.SYNC_SIZE + 2:] + data
                chksum = utils.calculate_checksum(frame_tmp)

                if chksum != expected_chksum:
                    self.conn.release()
                    time.sleep(0.05)
                    continue
                
                decoded_data = data.decode("ASCII")
                print(f"received message:\t{decoded_data}")
                
                if flags & utils.ACK_FLAG: pass

                self.queue.put(Frame(recv_id, utils.ACK_FLAG, ""))

                self.conn.release()
                time.sleep(0.05)
                
            except socket.timeout:
                self.conn.release()
                time.sleep(0.05)


class Sender:
    conn: Connection
    queue: FrameQueue
    th: Thread

    def __init__(self, conn: Connection, fq: FrameQueue):
        self.conn = conn
        self.queue = fq
        self.th = Thread(target=self.__run)
        self.th.start()

    def start(self):
        self.th = Thread(target=self.__run)
        self.th.start()

    def __run(self):
        while True:
            if self.queue.empty():
                time.sleep(0.05)
                continue

            frame = self.queue.get_nowait()

            encoded_frame = bytearray(struct.pack("!IIHHHB",
                                                  utils.SYNC_SEQUENCE,
                                                  utils.SYNC_SEQUENCE,
                                                  0,
                                                  len(frame.data),
                                                  frame.frame_id,
                                                  frame.is_ack*utils.ACK_FLAG |
                                                  frame.is_end*utils.END_FLAG |
                                                  frame.is_rst*utils.RST_FLAG
                                                  )) + frame.data.encode("ASCII")

            chk = utils.calculate_checksum(encoded_frame)
            encoded_frame[utils.SYNC_SIZE:utils.SYNC_SIZE+2] = chk.to_bytes(2, byteorder='big')

            self.conn.lock()
            self.conn.send(encoded_frame)
            self.conn.release()

            time.sleep(0.05)

class Frame:
    def __init__(self, frame_id: int, flags: int, data: str):
        self.frame_id = frame_id
        self.is_ack = flags & utils.ACK_FLAG == utils.ACK_FLAG
        self.is_end = flags & utils.END_FLAG == utils.END_FLAG
        self.is_rst = flags & utils.RST_FLAG == utils.RST_FLAG
        self.data = data

    def __str__(self):
        return f"{self.frame_id}:{self.data}:{self.is_ack}:{self.is_end}:{self.is_rst}"
