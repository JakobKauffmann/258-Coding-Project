"""
TCP Sliding Window Server
CS 258 - Computer Communication Networks
Author: Zhuoqun Wei

Receives packets from the client, tracks sequence numbers using cumulative
acknowledgments, handles out-of-order delivery, and calculates goodput.
Keeps running after a client disconnects and waits for the next connection.
Sequence numbers wrap at 2^16 (65536).

Usage: python server.py
"""

import socket
import struct
import csv

PORT = 9999
MAX_SEQ = 65536           # 2^16 — sequence numbers wrap at this value
WINDOW_SIZE = 500         # must match client's window size for unwrapping
GOODPUT_INTERVAL = 1000   # record goodput every N packets received
LOG_INTERVAL = 10000      # sample data for graphs every N packets
TIMEOUT = 60              # seconds idle before giving up on current client

def unwrap_seq(wrapped_seq, cum_ack):
    """Convert a wrapped sequence number (0..65535) back to a logical (unbounded)
    value using cum_ack as reference. Handles wrap-around correctly since
    the window size (500) is much smaller than the sequence space (65536)."""
    logical = cum_ack - (cum_ack % MAX_SEQ) + wrapped_seq
    if logical < cum_ack - WINDOW_SIZE:
        logical += MAX_SEQ
    return logical

def write_server_logs(receiver_window_log, seq_received_log, goodput_log):
    """Write CSV log files for graph generation."""
    with open('receiver_window_log.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['packets_received', 'out_of_order_size'])
        w.writerows(receiver_window_log)
    print(f"[server] Wrote receiver_window_log.csv ({len(receiver_window_log)} rows)")

    with open('seq_received_log.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['packets_received', 'wrapped_seq'])
        w.writerows(seq_received_log)
    print(f"[server] Wrote seq_received_log.csv ({len(seq_received_log)} rows)")

    with open('goodput_log.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['packets_received', 'goodput'])
        w.writerows(goodput_log)
    print(f"[server] Wrote goodput_log.csv ({len(goodput_log)} rows)")

def handle_client(conn, addr):
    """Handle one client connection — receive packets, send ACKs, save logs.
    Returns when the client disconnects (cleanly or by crash)."""
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    conn.settimeout(TIMEOUT)

    # Handshake — expect initial string, respond with "success"
    data = conn.recv(1024).decode()
    print(f"[server] Handshake received: '{data}'")
    conn.sendall(b"success")

    # Cumulative ACK tracking:
    # cum_ack = next expected logical sequence number
    # out_of_order = received packets ahead of cum_ack
    cum_ack = 0
    out_of_order = set()
    total_received = 0
    last_goodput_report = 0
    total_sent_by_client = None

    receiver_window_log = []
    seq_received_log = []
    goodput_log = []

    print("[server] Receiving packets...")

    try:
        buf = b""
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                print("[server] Client disconnected cleanly.")
                break
            buf += chunk

            done = False
            last_cum_ack = cum_ack
            while len(buf) >= 4:
                raw, buf = buf[:4], buf[4:]
                wrapped_seq = struct.unpack('!I', raw)[0]

                # Control message: end of run (0xFFFFFFFF cannot be a valid wrapped seq)
                if wrapped_seq == 0xFFFFFFFF:
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

                seq = unwrap_seq(wrapped_seq, cum_ack)
                total_received += 1

                if seq == cum_ack:
                    cum_ack += 1
                    while cum_ack in out_of_order:
                        out_of_order.discard(cum_ack)
                        cum_ack += 1
                elif seq > cum_ack:
                    out_of_order.add(seq)

                if total_received % LOG_INTERVAL == 0:
                    receiver_window_log.append((total_received, len(out_of_order)))
                    seq_received_log.append((total_received, wrapped_seq))

                if total_received - last_goodput_report >= GOODPUT_INTERVAL:
                    last_goodput_report = total_received
                    unique_received = cum_ack + len(out_of_order)
                    gp = unique_received / total_received
                    goodput_log.append((total_received, gp))
                    if total_received % (GOODPUT_INTERVAL * 1000) == 0:
                        print(f"[server] Goodput at {total_received} pkts: "
                              f"{unique_received}/{total_received} = {gp:.6f}")

            # Send cumulative ACK if cum_ack advanced
            if cum_ack != last_cum_ack:
                conn.sendall(struct.pack('!I', cum_ack % MAX_SEQ))

            if done:
                break

    except socket.timeout:
        print(f"[server] Timeout — no data for {TIMEOUT}s. Client may have crashed.")
    except ConnectionResetError:
        print(f"[server] Client crashed after {total_received} packets.")
    except ConnectionError as e:
        print(f"[server] Connection error: {e}")
    finally:
        print(f"\n[server] Session summary — packets received: {total_received}")
        if total_sent_by_client:
            gp = total_received / total_sent_by_client
            print(f"[server] FINAL Goodput: {total_received}/{total_sent_by_client} = {gp:.6f}")
        elif total_received > 0:
            print(f"[server] Run incomplete — no end-of-run signal received.")
        if goodput_log:
            avg_gp = sum(g for _, g in goodput_log) / len(goodput_log)
            print(f"[server] AVERAGE Goodput (over {len(goodput_log)} samples): {avg_gp:.6f}")
        write_server_logs(receiver_window_log, seq_received_log, goodput_log)
        conn.close()

def main():
    """Start the server and keep accepting new clients indefinitely."""
    server_sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(('::', PORT))
    server_sock.listen(1)
    print(f"[server] Server IP: {socket.getfqdn()}")
    print(f"[server] Listening on [::]:{PORT} (IPv4 + IPv6)\n")

    while True:
        print(f"[server] Waiting for connection...")
        conn, addr = server_sock.accept()
        print(f"[server] Connection from {addr[0]}:{addr[1]}")
        handle_client(conn, addr)
        print(f"\n[server] Ready for next connection.\n")

if __name__ == '__main__':
    main()
