# 258-Coding-Project

TCP sliding window simulation for CS 258 Computer Communication Networks at San Jose State University.

A client sends 10,000,000 packets to a server using a sliding window protocol with sequence numbers wrapping at 2^16 (65536). The client simulates 1% packet loss and retransmits dropped packets. The server tracks received/missing packets and reports goodput.

## Prerequisites

- Python 3
- matplotlib (`pip install matplotlib`)

## Usage

### 1. Start the server

On the receiving machine:

```bash
cd tcp_simulation
python server.py
```

The server listens on port 9999 and waits for a client connection.

### 2. Start the client

On the sending machine:

```bash
cd tcp_simulation
python client.py <server_ip>
```

If running both on the same machine, omit the IP (defaults to 127.0.0.1):

```bash
python client.py
```

### 3. Generate graphs

After the simulation completes, both the client and server write CSV log files to the current directory. Run the graph generator from the same directory:

```bash
python generate_graphs.py
```

This produces four PNG files:
- `graph_window_sizes.png` -- Sender and receiver window size over time
- `graph_seq_received.png` -- Sequence numbers received over time (sawtooth wrap pattern)
- `graph_seq_dropped.png` -- Sequence numbers dropped over time
- `graph_goodput.png` -- Goodput over time

## Output

The client prints:
- Client and server IP addresses
- Total packets sent (including retransmissions)
- Retransmission distribution table (packets needing 1, 2, 3, 4+ retransmissions)

The server prints:
- Server and client IP addresses
- Periodic goodput measurements
- Final and average goodput
- Total packets received

## Project Files

| File | Description |
|---|---|
| `tcp_simulation/client.py` | TCP client with sliding window, 1% drop simulation, and retransmission |
| `tcp_simulation/server.py` | TCP server with cumulative ACK tracking and goodput reporting |
| `tcp_simulation/generate_graphs.py` | Reads CSV logs and generates PNG graphs |

## References

- [Project Assignment](CS%20258%20Project%20Assignment%20Final.pdf)
- [Rubric](Project%20Submission%20details%20and%20rubrics.JPG)
