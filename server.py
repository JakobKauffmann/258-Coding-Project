import socket
import struct

HOST = '0.0.0.0'
PORT = 9999
TOTAL_PACKETS = 10_000_000
GOODPUT_INTERVAL = 1000
TIMEOUT = 60  # seconds idle before giving up

def main():
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((HOST, PORT))
    server_sock.listen(1)
    print(f"[server] Listening on {HOST}:{PORT}")

    conn, addr = server_sock.accept()
    print(f"[server] Connection from {addr}")
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)  # disable Nagle
    conn.settimeout(TIMEOUT)

    # Handshake
    data = conn.recv(1024).decode()
    print(f"[server] Handshake received: '{data}'")
    conn.sendall(b"success")

    # Cumulative ACK tracking with a proper sliding window:
    # cum_ack = next expected full sequence number
    # out_of_order = set of received packets ahead of cum_ack
    cum_ack = 0
    out_of_order = set()
    total_received = 0
    last_goodput_report = 0
    total_sent_by_client = None

    print("[server] Entering main receive loop...")

    try:
        buf = b""
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                raise ConnectionError("Client disconnected")
            buf += chunk

            done = False
            last_cum_ack = cum_ack
            while len(buf) >= 4:
                raw, buf = buf[:4], buf[4:]
                seq = struct.unpack('!I', raw)[0]

                # Control message: end of run
                if seq == 0xFFFFFFFF:
                    while len(buf) < 4:
                        more = conn.recv(4 - len(buf))
                        if not more:
                            break
                        buf += more
                    if len(buf) >= 4:
                        total_sent_by_client = struct.unpack('!I', buf[:4])[0]
                        buf = buf[4:]
                    print(f"[server] End-of-run signal. Client total sent: {total_sent_by_client}")
                    done = True
                    break

                total_received += 1

                # Advance cumulative ACK
                if seq == cum_ack:
                    cum_ack += 1
                    while cum_ack in out_of_order:
                        out_of_order.discard(cum_ack)
                        cum_ack += 1
                elif seq > cum_ack:
                    out_of_order.add(seq)
                # seq < cum_ack: duplicate/already ACKed, ignore

                # Goodput reporting
                if total_received - last_goodput_report >= GOODPUT_INTERVAL:
                    last_goodput_report = total_received
                    if total_sent_by_client:
                        gp = total_received / total_sent_by_client
                        print(f"[server] Goodput: {total_received}/{total_sent_by_client} = {gp:.4f}")
                    else:
                        print(f"[server] Received {total_received} packets")

            # Send one ACK per chunk (only if cum_ack advanced)
            if cum_ack != last_cum_ack:
                conn.sendall(struct.pack('!I', cum_ack))

            if done:
                break

    except socket.timeout:
        print("[server] Timeout — no data received for too long.")
    except ConnectionError as e:
        print(f"[server] Connection closed: {e}")
    finally:
        if total_sent_by_client:
            gp = total_received / total_sent_by_client
            print(f"[server] FINAL Goodput: {total_received}/{total_sent_by_client} = {gp:.4f}")
        else:
            print(f"[server] FINAL: Received {total_received} packets total")
        conn.close()
        server_sock.close()
        print("[server] Done.")

if __name__ == '__main__':
    main()
