"""
 Copyright (c) 2025 Computer Networks Group @ UPB

 Permission is hereby granted, free of charge, to any person obtaining a copy of
 this software and associated documentation files (the "Software"), to deal in
 the Software without restriction, including without limitation the rights to
 use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
 the Software, and to permit persons to whom the Software is furnished to do so,
 subject to the following conditions:

 The above copyright notice and this permission notice shall be included in all
 copies or substantial portions of the Software.

 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
 FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
 COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
 IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
 CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 """

# Import necessary modules from scapy
from scapy.all import Packet, IntField, FieldListField, Ether, srp1

from lib.gen import GenInts, GenMultipleOfInRange
from lib.test import CreateTestData, RunIntTest
from lib.worker import *


NUM_ITER   = 1
# Let's start with a small, fixed chunk size for easier debugging.
CHUNK_SIZE = 4
# We need a custom EtherType so the switch knows these packets are for us.
SML_PROTO_TYPE = 0x88B5 # Custom EtherType

class SwitchML(Packet):
    name = "SwitchMLPacket"
    # Our packet will contain the worker's rank and four 32-bit payload fields
    fields_desc = [
        IntField("rank", 0),
        IntField("payload0", 0),
        IntField("payload1", 0),
        IntField("payload2", 0),
        IntField("payload3", 0)
    ]

# Ensure Scapy binds our EtherType to the SwitchML layer
from scapy.all import bind_layers
bind_layers(Ether, SwitchML, type=SML_PROTO_TYPE)

def AllReduce(iface, rank, data, result):
    """
    Perform in-network all-reduce over ethernet

    :param str  iface: the ethernet interface used for all-reduce
    :param int   rank: the worker's rank
    :param [int] data: the input vector for this worker
    :param [int]  res: the output vector

    This function is blocking, i.e. only returns with a result or error
    """
    # Split the data into chunks
    chunks = [data[i:i + CHUNK_SIZE] for i in range(0, len(data), CHUNK_SIZE)]

    import time
    MAX_RETRIES = 5
    for i, chunk in enumerate(chunks):
        # Pad chunk to CHUNK_SIZE if needed
        padded = chunk + [0] * (CHUNK_SIZE - len(chunk))
        req_p = SwitchML(
            rank=rank,
            payload0=padded[0],
            payload1=padded[1],
            payload2=padded[2],
            payload3=padded[3]
        )
        req_eth = Ether(dst="ff:ff:ff:ff:ff:ff", type=SML_PROTO_TYPE)
        success = False
        for attempt in range(1, MAX_RETRIES + 1):
            Log(f"Sending chunk {i} (attempt {attempt}): {chunk}")
            resp_eth = srp1(req_eth / req_p,
                            iface=iface,
                            timeout=2,
                            verbose=False,
                            filter="ether proto %d" % SML_PROTO_TYPE)
            if resp_eth:
                Log("Raw response: %s" % resp_eth.summary())
            if resp_eth and SwitchML in resp_eth:
                resp_p = resp_eth[SwitchML]
                Log("Received aggregated chunk %d: [%d, %d, %d, %d]" % (
                    i, resp_p.payload0, resp_p.payload1, resp_p.payload2, resp_p.payload3))
                start_idx = i * CHUNK_SIZE
                end_idx = start_idx + CHUNK_SIZE
                result[start_idx:end_idx] = [
                    resp_p.payload0, resp_p.payload1, resp_p.payload2, resp_p.payload3
                ]
                success = True
                break
            else:
                Log(f"No response for chunk {i} (attempt {attempt})")
                time.sleep(0.2)
        if not success:
            Log(f"FAIL: Did not receive a response for chunk {i} after {MAX_RETRIES} attempts.")
            raise RuntimeError(f"AllReduce failed for chunk {i}")
        time.sleep(0.1)  # Add a small delay between chunks

def main():
    iface = 'eth0'
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
            CreateTestData("eth-iter-%d" % i, rank, data_out)
            # Perform the AllReduce
            AllReduce(iface, rank, data_out, data_in)
            # Check if the result is correct
            RunIntTest("eth-iter-%d" % i, rank, data_in, True)
        Log("PASS: AllReduce completed successfully.")
    except Exception as e:
        Log(f"FAIL: {e}")
    Log("Done")

if __name__ == '__main__':
    main()