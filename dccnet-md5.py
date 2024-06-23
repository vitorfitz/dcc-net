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

try:
    s.settimeout(1)
    s.connect((addr_str[0], int(addr_str[1])))
    out_bytes = bytearray((arg_gas + '\n').encode('ASCII'))

    if len(out_bytes) >= MAX_FRAME_SIZE:
        print("Maximum frame size is 65535")
        exit(-1)

    frame, check = write_frame(out_bytes, 0, False)

    attempts = 0
    ack = None

    while attempts < 60 and ack is None:
        try:
            s.sendall(frame)
            ack = s.recv(HEADER_SIZE + SYNC_SIZE)
            id_acked = int.from_bytes(ack[SYNC_SIZE+6:7])
            print("received ack (id: " + str(id_acked) + ")")
        except socket.timeout:
            attempts += 1

    buf = ""
    run = True
    id_ = 1
    while run:
        req = read_frame(s)

        if req is None:
            continue

        unpack, data = req

        is_ack = bool((unpack[3] & 0x80) >> 7)
        is_last = bool((unpack[3] & 0x40) >> 6)
        is_reset = bool((unpack[3] & 0x20) >> 5)

        if is_ack:
            id_ = not id_
            continue

        if is_reset:
            print("Reseting")
            run = False
            continue

        lines = frame_to_ascii(data)
        if len(lines) == 0:
            continue

        lines[0] = buf + lines[0]

        for line in lines:
            if line.endswith('\n'):
                check = calculate_checksum(line[:len(line)-1]).hexdigest()
                frame, _ = write_frame((str(check)+'\n').encode("ASCII"), id_, is_last)

                attempts = 0
                ack = None

                while attempts < 60 and ack is None:
                    try:
                        s.sendall(frame)
                        ack = s.recv(HEADER_SIZE + SYNC_SIZE)
                        id_acked = int.from_bytes(ack[SYNC_SIZE + 6:7])
                        print("received ack (id: " + str(id_acked) + ")")
                    except socket.timeout as e:
                        attempts += 1
            else:
                buf = line

        run = not is_last


finally:
    s.close()

