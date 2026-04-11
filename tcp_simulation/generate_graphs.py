"""
Graph Generator for TCP Sliding Window Simulation
CS 258 - Computer Communication Networks

Reads CSV log files produced by client.py and server.py, then generates
the three graphs required by the rubric:
  1. TCP Sender and Receiver window size over time
  2. TCP Sequence number received over time
  3. TCP Sequence number dropped over time

Usage: python generate_graphs.py
  (run from the same directory where the CSV files were written)
"""

import csv
import matplotlib.pyplot as plt


def load_csv(filename):
    """Load a CSV file and return rows as a list of tuples of floats."""
    rows = []
    with open(filename, 'r') as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            rows.append(tuple(float(x) for x in row))
    return rows


def plot_window_sizes():
    """Graph 1: TCP Sender and Receiver window size over time."""
    sender_data = load_csv('sender_window_log.csv')
    receiver_data = load_csv('receiver_window_log.csv')

    fig, ax = plt.subplots(figsize=(12, 6))

    if sender_data:
        x_s, y_s = zip(*sender_data)
        ax.plot(x_s, y_s, label='Sender Window (in-flight packets)', alpha=0.7)

    if receiver_data:
        x_r, y_r = zip(*receiver_data)
        ax.plot(x_r, y_r, label='Receiver Out-of-Order Buffer', alpha=0.7)

    ax.set_xlabel('Packet Number / Packets Received')
    ax.set_ylabel('Window Size (packets)')
    ax.set_title('TCP Sender and Receiver Window Size Over Time')
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('graph_window_sizes.png', dpi=150)
    plt.close()
    print("Saved graph_window_sizes.png")


def plot_seq_received():
    """Graph 2: TCP Sequence number received over time."""
    data = load_csv('seq_received_log.csv')

    if not data:
        print("No data in seq_received_log.csv")
        return

    x, y = zip(*data)

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.scatter(x, y, s=1, alpha=0.5)
    ax.set_xlabel('Packets Received')
    ax.set_ylabel('Sequence Number (wrapped, 0-65535)')
    ax.set_title('TCP Sequence Number Received Over Time')
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('graph_seq_received.png', dpi=150)
    plt.close()
    print("Saved graph_seq_received.png")


def plot_seq_dropped():
    """Graph 3: TCP Sequence number dropped over time."""
    data = load_csv('dropped_packets.csv')

    if not data:
        print("No data in dropped_packets.csv")
        return

    x, y = zip(*data)

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.scatter(x, y, s=1, alpha=0.3, color='red')
    ax.set_xlabel('Packet Number (logical)')
    ax.set_ylabel('Sequence Number (wrapped, 0-65535)')
    ax.set_title('TCP Sequence Number Dropped Over Time')
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('graph_seq_dropped.png', dpi=150)
    plt.close()
    print("Saved graph_seq_dropped.png")


def plot_goodput():
    """Bonus: Goodput over time."""
    data = load_csv('goodput_log.csv')

    if not data:
        print("No data in goodput_log.csv")
        return

    x, y = zip(*data)

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(x, y, alpha=0.7, color='green')
    ax.set_xlabel('Packets Received')
    ax.set_ylabel('Goodput (unique / total)')
    ax.set_title('Goodput Over Time')
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('graph_goodput.png', dpi=150)
    plt.close()
    print("Saved graph_goodput.png")


if __name__ == '__main__':
    print("Generating graphs from CSV data...")
    plot_window_sizes()
    plot_seq_received()
    plot_seq_dropped()
    plot_goodput()
    print("Done! All graphs saved as PNG files.")
