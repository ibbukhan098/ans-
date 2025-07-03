/*
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
 */

#include <core.p4>
#include <v1model.p4>

// Headers
header ethernet_t {
    bit<48> dstAddr;
    bit<48> srcAddr;
    bit<16> etherType;
}

header ipv4_t {
    bit<4>  version;
    bit<4>  ihl;
    bit<8>  diffserv;
    bit<16> totalLen;
    bit<16> identification;
    bit<3>  flags;
    bit<13> fragOffset;
    bit<8>  ttl;
    bit<8>  protocol;
    bit<16> hdrChecksum;
    bit<32> srcAddr;
    bit<32> dstAddr;
}

header udp_t {
    bit<16> srcPort;
    bit<16> dstPort;
    bit<16> length;
    bit<16> checksum;
}

header switchml_t {
    bit<8>  worker_id;      // Worker rank
    bit<8>  chunk_id;       // Chunk identifier within vector
    bit<8>  num_workers;    // Total number of workers
    bit<8>  flags;          // Control flags (0=data, 1=result)
    bit<32> value0;         // First value in chunk
    bit<32> value1;         // Second value in chunk
    bit<32> value2;         // Third value in chunk
    bit<32> value3;         // Fourth value in chunk
}

struct headers {
    ethernet_t ethernet;
    ipv4_t     ipv4;
    udp_t      udp;
    switchml_t switchml;
}

struct metadata {
    bit<1>  is_last_worker;
    bit<1>  is_retransmission;
    bit<1>  aggregation_complete;
    bit<8>  worker_bitmap;
    bit<32> chunk_result0;
    bit<32> chunk_result1;
    bit<32> chunk_result2;
    bit<32> chunk_result3;
    bit<32> reg_index;
}

// Parser
parser MyParser(packet_in packet,
                out headers hdr,
                inout metadata meta,
                inout standard_metadata_t standard_metadata) {

    state start {
        transition parse_ethernet;
    }

    state parse_ethernet {
        packet.extract(hdr.ethernet);
        transition select(hdr.ethernet.etherType) {
            0x0800: parse_ipv4;  // IPv4
            default: accept;
        }
    }

    state parse_ipv4 {
        packet.extract(hdr.ipv4);
        transition select(hdr.ipv4.protocol) {
            17: parse_udp;  // UDP
            default: accept;
        }
    }

    state parse_udp {
        packet.extract(hdr.udp);
        transition select(hdr.udp.dstPort) {
            9999: parse_switchml;
            default: accept;
        }
    }

    state parse_switchml {
        packet.extract(hdr.switchml);
        transition accept;
    }
}

// Checksum verification
control MyVerifyChecksum(inout headers hdr, inout metadata meta) {
    apply { }
}

// Ingress processing
control MyIngress(inout headers hdr,
                  inout metadata meta,
                  inout standard_metadata_t standard_metadata) {

    // Registers for aggregation (one per chunk position)
    register<bit<32>>(256) agg_value0;
    register<bit<32>>(256) agg_value1;
    register<bit<32>>(256) agg_value2;
    register<bit<32>>(256) agg_value3;

    // Register to track which workers have contributed (bitmap)
    register<bit<8>>(256)  worker_bitmap;

    // Registers to store final results for retransmissions
    register<bit<32>>(256) result_value0;
    register<bit<32>>(256) result_value1;
    register<bit<32>>(256) result_value2;
    register<bit<32>>(256) result_value3;
    register<bit<1>>(256)  result_ready;

    action drop() {
        mark_to_drop(standard_metadata);
    }

    action read_worker_bitmap() {
        worker_bitmap.read(meta.worker_bitmap, meta.reg_index);
    }

    action read_result_status() {
        bit<1> ready;
        result_ready.read(ready, meta.reg_index);
        meta.aggregation_complete = ready;
    }

    action read_stored_results() {
        result_value0.read(meta.chunk_result0, meta.reg_index);
        result_value1.read(meta.chunk_result1, meta.reg_index);
        result_value2.read(meta.chunk_result2, meta.reg_index);
        result_value3.read(meta.chunk_result3, meta.reg_index);
    }

    action update_worker_bitmap() {
        bit<8> worker_mask = (bit<8>)1 << (bit<8>)hdr.switchml.worker_id;
        bit<8> new_bitmap = meta.worker_bitmap | worker_mask;
        worker_bitmap.write(meta.reg_index, new_bitmap);
        meta.worker_bitmap = new_bitmap;
    }

    action read_current_aggregation() {
        agg_value0.read(meta.chunk_result0, meta.reg_index);
        agg_value1.read(meta.chunk_result1, meta.reg_index);
        agg_value2.read(meta.chunk_result2, meta.reg_index);
        agg_value3.read(meta.chunk_result3, meta.reg_index);
    }

    action update_aggregation() {
        bit<32> new_val0 = meta.chunk_result0 + hdr.switchml.value0;
        bit<32> new_val1 = meta.chunk_result1 + hdr.switchml.value1;
        bit<32> new_val2 = meta.chunk_result2 + hdr.switchml.value2;
        bit<32> new_val3 = meta.chunk_result3 + hdr.switchml.value3;

        agg_value0.write(meta.reg_index, new_val0);
        agg_value1.write(meta.reg_index, new_val1);
        agg_value2.write(meta.reg_index, new_val2);
        agg_value3.write(meta.reg_index, new_val3);

        meta.chunk_result0 = new_val0;
        meta.chunk_result1 = new_val1;
        meta.chunk_result2 = new_val2;
        meta.chunk_result3 = new_val3;
    }

    action store_final_results() {
        result_value0.write(meta.reg_index, meta.chunk_result0);
        result_value1.write(meta.reg_index, meta.chunk_result1);
        result_value2.write(meta.reg_index, meta.chunk_result2);
        result_value3.write(meta.reg_index, meta.chunk_result3);
        result_ready.write(meta.reg_index, 1);
    }

    action clear_old_aggregation() {
        bit<32> old_index = meta.reg_index - 2;
        worker_bitmap.write(old_index, 0);
        result_ready.write(old_index, 0);
        result_value0.write(old_index, 0);
        result_value1.write(old_index, 0);
        result_value2.write(old_index, 0);
        result_value3.write(old_index, 0);
        agg_value0.write(old_index, 0);
        agg_value1.write(old_index, 0);
        agg_value2.write(old_index, 0);
        agg_value3.write(old_index, 0);
    }

    action multicast_result() {
        // Update packet with aggregated values
        hdr.switchml.value0 = meta.chunk_result0;
        hdr.switchml.value1 = meta.chunk_result1;
        hdr.switchml.value2 = meta.chunk_result2;
        hdr.switchml.value3 = meta.chunk_result3;
        hdr.switchml.flags = 1;  // Mark as result

        // Prepare for broadcast response
        standard_metadata.mcast_grp = 1;

        // For broadcast, we need to send back to the source port of each worker
        bit<16> temp_port = hdr.udp.srcPort;
        hdr.udp.srcPort = hdr.udp.dstPort;
        hdr.udp.dstPort = temp_port;

        // Set switch as source
        hdr.ipv4.srcAddr = 0x0a000064;  // 10.0.0.100
        hdr.ethernet.srcAddr = 0x000000000100;

        // Keep destination as broadcast
        hdr.ipv4.dstAddr = 0xffffffff;  // 255.255.255.255
        hdr.ethernet.dstAddr = 0xffffffffffff;

        // Update IP header fields
        hdr.ipv4.ttl = 64;
        hdr.ipv4.totalLen = 20 + 8 + 20;  // 48 bytes total
        hdr.udp.length = 28;
    }

    action unicast_result() {
        // Update packet with stored values
        hdr.switchml.value0 = meta.chunk_result0;
        hdr.switchml.value1 = meta.chunk_result1;
        hdr.switchml.value2 = meta.chunk_result2;
        hdr.switchml.value3 = meta.chunk_result3;
        hdr.switchml.flags = 1;  // Mark as result

        // Swap addresses for unicast response
        bit<48> temp_mac = hdr.ethernet.srcAddr;
        hdr.ethernet.srcAddr = hdr.ethernet.dstAddr;
        hdr.ethernet.dstAddr = temp_mac;

        bit<32> temp_ip = hdr.ipv4.srcAddr;
        hdr.ipv4.srcAddr = hdr.ipv4.dstAddr;
        hdr.ipv4.dstAddr = temp_ip;

        bit<16> temp_port = hdr.udp.srcPort;
        hdr.udp.srcPort = hdr.udp.dstPort;
        hdr.udp.dstPort = temp_port;

        // Send back to ingress port
        standard_metadata.egress_spec = standard_metadata.ingress_port;

        // Update IP header fields
        hdr.ipv4.ttl = 64;
    }

    apply {
        if (hdr.ipv4.isValid() && hdr.udp.isValid() &&
            hdr.switchml.isValid() && hdr.switchml.flags == 0) {

            // Initialize metadata
            meta.is_retransmission = 0;
            meta.is_last_worker = 0;
            meta.aggregation_complete = 0;
            meta.chunk_result0 = 0;
            meta.chunk_result1 = 0;
            meta.chunk_result2 = 0;
            meta.chunk_result3 = 0;
            meta.reg_index = (bit<32>)hdr.switchml.chunk_id;

            // First, read the current worker bitmap
            read_worker_bitmap();

            // Check if this worker already contributed
            bit<8> worker_mask = (bit<8>)1 << (bit<8>)hdr.switchml.worker_id;
            if ((meta.worker_bitmap & worker_mask) != 0) {
                // Worker already contributed, this is a retransmission
                meta.is_retransmission = 1;

                // Check if result is ready
                read_result_status();
                if (meta.aggregation_complete == 1) {
                    // Load stored results
                    read_stored_results();
                    // Send unicast response
                    unicast_result();
                } else {
                    // Result not ready yet
                    drop();
                }
            } else {
                // New contribution
                meta.is_retransmission = 0;

                // Update worker bitmap
                update_worker_bitmap();

                // Read current aggregation values
                read_current_aggregation();

                // Update aggregation
                update_aggregation();

                // Count number of workers that have contributed
                bit<8> worker_count = 0;
                bit<8> bitmap = meta.worker_bitmap;

                // Count bits set in bitmap (unrolled loop)
                if ((bitmap & 0x01) != 0) worker_count = worker_count + 1;
                if ((bitmap & 0x02) != 0) worker_count = worker_count + 1;
                if ((bitmap & 0x04) != 0) worker_count = worker_count + 1;
                if ((bitmap & 0x08) != 0) worker_count = worker_count + 1;
                if ((bitmap & 0x10) != 0) worker_count = worker_count + 1;
                if ((bitmap & 0x20) != 0) worker_count = worker_count + 1;
                if ((bitmap & 0x40) != 0) worker_count = worker_count + 1;
                if ((bitmap & 0x80) != 0) worker_count = worker_count + 1;

                // Check if all workers have contributed
                if (worker_count == hdr.switchml.num_workers) {
                    // This was the last worker
                    meta.is_last_worker = 1;
                    meta.aggregation_complete = 1;

                    // Store results for future retransmissions
                    store_final_results();

                    // Multicast result to all workers
                    multicast_result();

                    // Clear old state if possible
                    if (meta.reg_index >= 2) {
                        clear_old_aggregation();
                    }
                } else {
                    // Not the last worker yet
                    meta.is_last_worker = 0;
                    meta.aggregation_complete = 0;
                    drop();
                }
            }
        } else {
            drop();
        }
    }
}

// Egress processing
control MyEgress(inout headers hdr,
                 inout metadata meta,
                 inout standard_metadata_t standard_metadata) {
    apply {
        // For multicast packets, we need to update the destination
        if (standard_metadata.instance_type == 1) {
            // This is a cloned packet from multicast
            // The egress port determines the destination
        }
    }
}

// Checksum computation
control MyComputeChecksum(inout headers hdr, inout metadata meta) {
    apply {
        update_checksum(
            hdr.ipv4.isValid(),
            { hdr.ipv4.version,
              hdr.ipv4.ihl,
              hdr.ipv4.diffserv,
              hdr.ipv4.totalLen,
              hdr.ipv4.identification,
              hdr.ipv4.flags,
              hdr.ipv4.fragOffset,
              hdr.ipv4.ttl,
              hdr.ipv4.protocol,
              hdr.ipv4.srcAddr,
              hdr.ipv4.dstAddr },
            hdr.ipv4.hdrChecksum,
            HashAlgorithm.csum16);
    }
}

// Deparser
control MyDeparser(packet_out packet, in headers hdr) {
    apply {
        packet.emit(hdr.ethernet);
        packet.emit(hdr.ipv4);
        packet.emit(hdr.udp);
        packet.emit(hdr.switchml);
    }
}

// Switch instantiation
V1Switch(
    MyParser(),
    MyVerifyChecksum(),
    MyIngress(),
    MyEgress(),
    MyComputeChecksum(),
    MyDeparser()
) main;
