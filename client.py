import socket
import struct
import threading
import random
import queue
import sys

SERVER_IP = sys.argv[1] if len(sys.argv) > 1 else '127.0.0.1'
PORT = 9999
TOTAL_PACKETS = 10_000_000
DROP_PROB = 0.01          # 1% simulated drop
RETRANSMIT_INTERVAL = 100 # retransmit dropped every N new seq numbers sent
WINDOW_SIZE = 500         # max packets in flight
STALL_TIMEOUT = 2         # seconds before retransmitting on stall

lock = threading.Lock()
window_base = 0           # lowest unACKed full sequence number
ack_queue = queue.Queue()

def receiver_thread(sock):
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
            ack = struct.unpack('!I', raw)[0]
            ack_queue.put(ack)
        except Exception as e:
            print(f"[receiver] Error: {e}")
            ack_queue.put(None)
            return

def sender_thread(sock):
    global window_base

    dropped = set()   # full sequence numbers simulated-dropped and not yet ACKed
    total_sent = 0
    next_seq = 0      # next new packet to send (full, unbounded)

    def do_retransmit():
        nonlocal total_sent
        batch = bytearray()
        for seq in list(dropped):
            if random.random() >= DROP_PROB:
                batch += struct.pack('!I', seq)
                total_sent += 1
                dropped.discard(seq)
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
                dropped.add(next_seq)
            else:
                batch += struct.pack('!I', next_seq)
                total_sent += 1
            next_seq += 1

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

    return total_sent

def main():
    global window_base
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((SERVER_IP, PORT))
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)  # disable Nagle
    print(f"[client] Connected to {SERVER_IP}:{PORT}")

    # Handshake
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

    total_sent = sender_thread(sock)
    print(f"[client] Sender done. Total sent (including retransmits): {total_sent}")

    # End-of-run control message
    sock.sendall(struct.pack('!I', 0xFFFFFFFF))
    sock.sendall(struct.pack('!I', total_sent))
    print("[client] Sent end-of-run signal.")

    recv_t.join(timeout=5)
    sock.close()
    print("[client] Done.")

if __name__ == '__main__':
    main()
