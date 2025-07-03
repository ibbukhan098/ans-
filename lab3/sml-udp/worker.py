"""
Level 2: In-network AllReduce over UDP
"""

from lib.gen import GenInts, GenMultipleOfInRange
from lib.test import CreateTestData, RunIntTest
from lib.worker import *
import socket
import struct
import time
import random
import os

NUM_ITER   = 1
CHUNK_SIZE = 4

# Network configuration
SWITCHML_PORT = 9999

def get_worker_mac(rank):
    return f"00:00:00:00:01:{rank+1:02x}"

def get_worker_ip(rank):
    return f"10.0.0.{rank+1}"

def ip_to_int(ip_str):
    parts = ip_str.split('.')
    return (int(parts[0]) << 24) + (int(parts[1]) << 16) + (int(parts[2]) << 8) + int(parts[3])

def mac_to_bytes(mac_str):
    return bytes.fromhex(mac_str.replace(':', ''))

def calculate_checksum(data):
    if len(data) % 2 == 1:
        data += b'\x00'

    checksum = 0
    for i in range(0, len(data), 2):
        word = (data[i] << 8) + data[i + 1]
        checksum += word
        checksum = (checksum & 0xFFFF) + (checksum >> 16)

    return (~checksum) & 0xFFFF

def pack_switchml_packet(worker_id, chunk_id, num_workers, flags, values):
    padded_values = values + [0] * (4 - len(values))
    padded_values = padded_values[:4]

    packet = struct.pack('!BBBBLLLL',
                        worker_id, chunk_id, num_workers, flags,
                        padded_values[0], padded_values[1],
                        padded_values[2], padded_values[3])
    return packet

def unpack_switchml_packet(data):
    if len(data) < 20:
        return None

    unpacked = struct.unpack('!BBBBLLLL', data[:20])
    worker_id, chunk_id, num_workers, flags = unpacked[:4]
    values = list(unpacked[4:])

    return (worker_id, chunk_id, num_workers, flags, values)

def create_raw_udp_packet(src_ip, dst_ip, src_port, dst_port, payload, src_mac, dst_mac):
    # Ethernet header (14 bytes)
    eth_header = struct.pack('!6s6sH',
                            mac_to_bytes(dst_mac),
                            mac_to_bytes(src_mac),
                            0x0800)

    # IP header (20 bytes)
    version_ihl = 0x45
    tos = 0
    total_length = 20 + 8 + len(payload)
    identification = random.randint(0, 65535)
    flags_fragment = 0x4000
    ttl = 64
    protocol = 17
    checksum = 0
    src_ip_int = ip_to_int(src_ip)
    dst_ip_int = ip_to_int(dst_ip)

    ip_header_no_checksum = struct.pack('!BBHHHBBHLL',
                                       version_ihl, tos, total_length,
                                       identification, flags_fragment,
                                       ttl, protocol, 0,
                                       src_ip_int, dst_ip_int)

    ip_checksum = calculate_checksum(ip_header_no_checksum)
    ip_header = struct.pack('!BBHHHBBHLL',
                           version_ihl, tos, total_length,
                           identification, flags_fragment,
                           ttl, protocol, ip_checksum,
                           src_ip_int, dst_ip_int)

    # UDP header (8 bytes)
    udp_length = 8 + len(payload)
    udp_checksum = 0
    udp_header = struct.pack('!HHHH',
                            src_port, dst_port,
                            udp_length, udp_checksum)

    packet = eth_header + ip_header + udp_header + payload
    return packet

def AllReduce(rank, data, result):
    """
    Perform in-network all-reduce over UDP

    :param int   rank: the worker's rank
    :param [int] data: the input vector for this worker
    :param [int] result: the output vector

    This function is blocking, i.e. only returns with a result or error
    """
    Log(f"Worker {rank}: Starting AllReduce with {len(data)} values")

    # Get network information
    src_mac = get_worker_mac(rank)
    src_ip = get_worker_ip(rank)
    dst_mac = "ff:ff:ff:ff:ff:ff"
    dst_ip = "255.255.255.255"
    src_port = 10000 + rank
    dst_port = SWITCHML_PORT

    interface = "eth0"

    # Create raw socket for sending
    try:
        send_sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(0x0003))
        send_sock.bind((interface, 0))
        Log(f"Worker {rank}: Created raw send socket on {interface}")
    except Exception as e:
        Log(f"Worker {rank}: ERROR - Could not create raw socket: {e}")
        raise RuntimeError(f"AllReduce failed: {e}")

    # Create UDP socket for receiving
    try:
        recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        recv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        recv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        recv_sock.bind(('', src_port))
        recv_sock.settimeout(10.0)
        Log(f"Worker {rank}: Created UDP receive socket on port {src_port}")
    except Exception as e:
        Log(f"Worker {rank}: ERROR - Could not create receive socket: {e}")
        send_sock.close()
        raise RuntimeError(f"AllReduce failed: {e}")

    try:
        num_workers = 3
        # Split the data into chunks
        chunks = [data[i:i + CHUNK_SIZE] for i in range(0, len(data), CHUNK_SIZE)]

        # Staggered delay based on rank
        delay = 1.0 + (rank * 0.5)
        Log(f"Worker {rank}: Waiting {delay} seconds before sending...")
        time.sleep(delay)

        MAX_RETRIES = 5
        for chunk_id, chunk in enumerate(chunks):
            # Pad chunk to CHUNK_SIZE if needed
            padded = chunk + [0] * (CHUNK_SIZE - len(chunk))

            success = False
            for attempt in range(1, MAX_RETRIES + 1):
                Log(f"Sending chunk {chunk_id} (attempt {attempt}): {chunk}")

                # Create SwitchML payload
                switchml_payload = pack_switchml_packet(
                    worker_id=rank,
                    chunk_id=chunk_id,
                    num_workers=num_workers,
                    flags=0,
                    values=padded
                )

                # Create raw packet
                raw_packet = create_raw_udp_packet(
                    src_ip, dst_ip, src_port, dst_port,
                    switchml_payload, src_mac, dst_mac
                )

                # Send packet
                try:
                    bytes_sent = send_sock.send(raw_packet)
                    Log(f"Worker {rank}: Sent packet for chunk {chunk_id} ({bytes_sent} bytes)")
                except Exception as e:
                    Log(f"Worker {rank}: ERROR - Failed to send packet for chunk {chunk_id}: {e}")
                    continue

                # Wait for aggregation result
                try:
                    response_data, addr = recv_sock.recvfrom(1024)
                    Log(f"Worker {rank}: Received response from {addr}")

                    # Unpack response
                    response = unpack_switchml_packet(response_data)
                    if response is None:
                        Log(f"Worker {rank}: ERROR - Invalid response packet for chunk {chunk_id}")
                        continue

                    resp_worker_id, resp_chunk_id, resp_num_workers, resp_flags, chunk_result = response

                    # Verify this is the response we're expecting
                    if resp_chunk_id == chunk_id and resp_flags == 1:
                        Log(f"Received aggregated chunk {chunk_id}: {chunk_result}")
                        start_idx = chunk_id * CHUNK_SIZE
                        end_idx = start_idx + CHUNK_SIZE
                        result[start_idx:end_idx] = chunk_result
                        success = True
                        break
                    else:
                        Log(f"Worker {rank}: ERROR - Wrong response: chunk_id={resp_chunk_id}, flags={resp_flags}")

                except socket.timeout:
                    Log(f"No response for chunk {chunk_id} (attempt {attempt})")
                    time.sleep(0.2)
                except Exception as e:
                    Log(f"Worker {rank}: ERROR - Exception receiving response for chunk {chunk_id}: {e}")

            if not success:
                Log(f"FAIL: Did not receive a response for chunk {chunk_id} after {MAX_RETRIES} attempts.")
                raise RuntimeError(f"AllReduce failed for chunk {chunk_id}")

            time.sleep(0.1)  # Add a small delay between chunks

    finally:
        send_sock.close()
        recv_sock.close()

def main():
    rank = GetRankOrExit()
    Log("Started...")
    try:
        for i in range(NUM_ITER):
            # Generate a random vector whose length is a multiple of CHUNK_SIZE
            num_elem = GenMultipleOfInRange(CHUNK_SIZE, 16, CHUNK_SIZE)
            data_out = GenInts(num_elem)
            # Initialize the result vector with zeros
            data_in = [0] * num_elem
            # Create test data so we can verify the result
            CreateTestData("udp-iter-%d" % i, rank, data_out)
            # Perform the AllReduce
            AllReduce(rank, data_out, data_in)
            # Check if the result is correct
            RunIntTest("udp-iter-%d" % i, rank, data_in, True)
        Log("PASS: AllReduce completed successfully.")
    except Exception as e:
        Log(f"FAIL: {e}")
    Log("Done")

if __name__ == '__main__':
    main()
