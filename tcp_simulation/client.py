"""
TCP Sliding Window Client
CS 258 - Computer Communication Networks

Simulates a TCP client that sends 10,000,000 packets using a sliding window
protocol. Sequence numbers wrap at 2^16 (65536). The client probabilistically
drops 1% of packets and retransmits them every 100 sequence numbers.

Usage: python client.py [server_ip]
"""

import socket
import struct
import threading
import random
import queue
import sys
import csv
from collections import Counter

SERVER_IP = sys.argv[1] if len(sys.argv) > 1 else '127.0.0.1'
PORT = 9999
TOTAL_PACKETS = 10_000_000
MAX_SEQ = 65536           # 2^16 — sequence numbers wrap at this value
DROP_PROB = 0.01          # 1% simulated drop
RETRANSMIT_INTERVAL = 100 # retransmit dropped every N new seq numbers sent
WINDOW_SIZE = 500         # max packets in flight
STALL_TIMEOUT = 2         # seconds before retransmitting on stall
LOG_INTERVAL = 10000      # sample data for graphs every N packets

lock = threading.Lock()
window_base = 0           # lowest unACKed logical (unbounded) sequence number
ack_queue = queue.Queue()

def unwrap_ack(wrapped_ack):
    """Convert a wrapped ACK (0..65535) back to a logical (unbounded) value
    using window_base as reference. The ACK must be advancing, so if the
    naive unwrap lands below window_base we add MAX_SEQ."""
    global window_base
    with lock:
        base = window_base
    logical = base - (base % MAX_SEQ) + wrapped_ack
    if logical < base:
        logical += MAX_SEQ
    return logical

def receiver_thread(sock):
    """Receive ACKs from the server and put them on ack_queue after unwrapping."""
    while True:
        try:
            raw = b""
            while len(raw) < 4:
                chunk = sock.recv(4 - len(raw))
                if not chunk:
                    print("[receiver] Server closed connection.")
                    ack_queue.put(None)
                    return
                raw += chunk
            wrapped_ack = struct.unpack('!I', raw)[0]
            logical_ack = unwrap_ack(wrapped_ack)
            ack_queue.put(logical_ack)
        except Exception as e:
            print(f"[receiver] Error: {e}")
            ack_queue.put(None)
            return

def sender_thread(sock):
    """Send packets using a sliding window protocol with simulated 1% drop.
    Returns (total_sent, sender_window_log, dropped_log, retransmit_counts)."""
    global window_base

    dropped = set()          # logical seq numbers simulated-dropped and not yet ACKed
    total_sent = 0
    next_seq = 0             # next new packet to send (logical, unbounded)

    # --- Logging data structures ---
    sender_window_log = []   # (packet_number, in_flight_count) sampled periodically
    dropped_log = []         # logical seq of every dropped packet
    retransmit_counts = {}   # logical_seq -> number of retransmission attempts

    def do_retransmit():
        """Retransmit all currently-dropped packets, each with the same 1% drop probability."""
        nonlocal total_sent
        batch = bytearray()
        for seq in list(dropped):
            retransmit_counts[seq] = retransmit_counts.get(seq, 0) + 1
            if random.random() >= DROP_PROB:
                # Retransmit succeeds — send wrapped seq on the wire
                batch += struct.pack('!I', seq % MAX_SEQ)
                total_sent += 1
                dropped.discard(seq)
            # else: retransmit itself was dropped, stays in dropped set
        if batch:
            sock.sendall(bytes(batch))

    def drain_acks():
        """Non-blocking drain of all available ACKs; returns True if receiver signaled done."""
        global window_base
        while True:
            try:
                ack = ack_queue.get_nowait()
                if ack is None:
                    return True  # receiver done
                with lock:
                    if ack > window_base:
                        window_base = ack
            except queue.Empty:
                break
        return False

    while next_seq < TOTAL_PACKETS or dropped:
        with lock:
            base = window_base

        # Send new packets within the window — batched into one write
        batch = bytearray()
        while next_seq < TOTAL_PACKETS and next_seq < base + WINDOW_SIZE:
            if random.random() < DROP_PROB:
                # Simulate packet drop
                dropped.add(next_seq)
                dropped_log.append(next_seq)
                retransmit_counts[next_seq] = 0
            else:
                # Send wrapped sequence number on the wire
                batch += struct.pack('!I', next_seq % MAX_SEQ)
                total_sent += 1
            next_seq += 1

            # Log sender window size periodically
            if next_seq % LOG_INTERVAL == 0:
                with lock:
                    current_base = window_base
                sender_window_log.append((next_seq, next_seq - current_base))

            # Periodic retransmit every RETRANSMIT_INTERVAL new packets sent
            if next_seq % RETRANSMIT_INTERVAL == 0:
                if batch:
                    sock.sendall(bytes(batch))
                    batch = bytearray()
                do_retransmit()

        if batch:
            sock.sendall(bytes(batch))

        # Drain all available ACKs (non-blocking)
        if drain_acks():
            break

        # Check if we need to wait (window full, or all sent but waiting on dropped)
        with lock:
            base = window_base
        window_full = next_seq >= base + WINDOW_SIZE and next_seq < TOTAL_PACKETS
        waiting_on_drops = next_seq >= TOTAL_PACKETS and dropped

        if window_full or waiting_on_drops:
            try:
                ack = ack_queue.get(timeout=STALL_TIMEOUT)
                if ack is None:
                    break
                with lock:
                    if ack > window_base:
                        window_base = ack
            except queue.Empty:
                # Stall: retransmit to unblock
                print(f"[sender] Stall — retransmitting {len(dropped)} dropped packets (next_seq={next_seq})")
                do_retransmit()

    return total_sent, sender_window_log, dropped_log, retransmit_counts

def write_client_logs(sender_window_log, dropped_log, retransmit_counts):
    """Write CSV log files for graph generation."""
    with open('sender_window_log.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['packet_number', 'window_size'])
        w.writerows(sender_window_log)
    print(f"[client] Wrote sender_window_log.csv ({len(sender_window_log)} rows)")

    with open('dropped_packets.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['packet_number', 'wrapped_seq'])
        for seq in dropped_log:
            w.writerow([seq, seq % MAX_SEQ])
    print(f"[client] Wrote dropped_packets.csv ({len(dropped_log)} rows)")

    with open('retransmit_table.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['seq', 'retransmit_count'])
        for seq, count in retransmit_counts.items():
            w.writerow([seq, count])
    print(f"[client] Wrote retransmit_table.csv ({len(retransmit_counts)} rows)")

def print_retransmit_table(retransmit_counts):
    """Print the retransmission distribution table required by the rubric."""
    # Only count packets that were actually dropped (retransmit_counts includes all dropped packets)
    # Packets with count 0 were dropped but recovered by the server advancing past them,
    # or were still pending. We care about packets that needed >= 1 retransmission.
    dist = Counter(retransmit_counts.values())
    print("\n========== Retransmission Table ==========")
    print(f"{'# of retransmissions':>22} | {'# of packets':>14}")
    print("-" * 40)
    for i in range(1, 4):
        print(f"{i:>22} | {dist.get(i, 0):>14}")
    four_plus = sum(v for k, v in dist.items() if k >= 4)
    print(f"{'4+':>22} | {four_plus:>14}")
    initially_dropped = len(retransmit_counts)
    print(f"\nTotal packets initially dropped: {initially_dropped}")
    print("==========================================\n")

def main():
    """Connect to the server, perform handshake, and send packets."""
    global window_base
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((SERVER_IP, PORT))
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)  # disable Nagle

    client_ip = sock.getsockname()[0]
    print(f"[client] Client IP: {client_ip}")
    print(f"[client] Connected to Server IP: {SERVER_IP}, Port: {PORT}")

    # Handshake — send initial string, expect "success"
    sock.sendall(b"network")
    resp = sock.recv(1024).decode()
    print(f"[client] Server response: '{resp}'")
    if resp != "success":
        print("[client] Handshake failed.")
        sock.close()
        return

    window_base = 0

    recv_t = threading.Thread(target=receiver_thread, args=(sock,), daemon=True)
    recv_t.start()

    total_sent, sender_window_log, dropped_log, retransmit_counts = sender_thread(sock)
    print(f"[client] Sender done. Total packets sent (including retransmits): {total_sent}")
    print(f"[client] Total unique packets intended: {TOTAL_PACKETS}")

    # End-of-run control message (0xFFFFFFFF cannot collide with wrapped seq, max 65535)
    sock.sendall(struct.pack('!I', 0xFFFFFFFF))
    sock.sendall(struct.pack('!I', total_sent))
    print("[client] Sent end-of-run signal.")

    recv_t.join(timeout=5)
    sock.close()

    # Write log files and print retransmission table
    write_client_logs(sender_window_log, dropped_log, retransmit_counts)
    print_retransmit_table(retransmit_counts)
    print("[client] Done.")

if __name__ == '__main__':
    main()
