from utils import *
import sys

client_or_server = sys.argv[1]
arg_addr = sys.argv[2]
arg_input = sys.argv[3]
arg_output = sys.argv[4]

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    if client_or_server == "-c":
        input_ = open(arg_input, "rb")

        addr_str = arg_addr.split(":")
        if len(addr_str) != 2:
            print("Client address format should be <address>:<port>")
            exit(-1)

        s = socket.socket(get_ip_type(addr_str[0], addr_str[1]), socket.SOCK_STREAM)

        s.settimeout(1)
        s.connect((addr_str[0], int(addr_str[1])))
        in_bytes = bytearray(input_.read(MAX_FRAME_SIZE))
        if len(in_bytes) >= MAX_FRAME_SIZE:
            print("Maximum frame size is 65535")
            exit(-1)

        frame, check = write_frame(in_bytes, 0, True)
        # exit(0)
        attempts = 0
        data = None

        while attempts < 60 and data is None:
            try:
                s.sendall(frame)
                data = s.recv(HEADER_SIZE + SYNC_SIZE)
                print("received ack " + str(len(data)))
            except socket.timeout:
                attempts += 1

    else:
        output = open(arg_output, "wb")
        s.bind(("127.0.0.1", int(arg_addr)))
        s.listen()
        conn, addr = s.accept()

        with conn:
            print(f"Connected by {addr}")
            _, data, _ = read_frame(conn,conn.recv)
            output.write(data)
            frame, _ = write_frame(bytearray(), 0, True)
            conn.sendall(frame)

finally:
    s.close()
