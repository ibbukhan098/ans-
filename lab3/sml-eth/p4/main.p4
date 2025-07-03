/*
 * Copyright (c) 2025 Computer Networks Group @ UPB
 * (Corrected Version 2)
 * This is the P4 program for a simple in-network aggregation switch.
 */

#include <core.p4>
#include <v1model.p4>

// Define constants that must match worker.py
#define SML_PROTO_TYPE 0x88B5
#define CHUNK_SIZE 4
#define NUM_WORKERS 2


typedef bit<9>  sw_port_t;
typedef bit<48> mac_addr_t;
typedef bit<32> int32_t;

// Define a unique MAC address for the switch
const mac_addr_t SWITCH_MAC = 0x0000000000FF;

// Standard Ethernet header
header ethernet_t {
    mac_addr_t dstAddr;
    mac_addr_t srcAddr;
    bit<16>    etherType;
}

// Our custom SwitchML header
header switchml_t {
    int32_t  rank;
    int32_t  payload0;
    int32_t  payload1;
    int32_t  payload2;
    int32_t  payload3;
}

// A struct containing all headers the switch understands
struct headers {
    ethernet_t eth;
    switchml_t sml;
}

struct metadata {
    int32_t current_count;
}

// ============================================================================
// PARSER
// ============================================================================
parser TheParser(packet_in packet,
                 out headers hdr,
                 inout metadata meta,
                 inout standard_metadata_t standard_metadata) {

    state start {
        transition parse_ethernet;
    }

    state parse_ethernet {
        packet.extract(hdr.eth);
        transition select (hdr.eth.etherType) {
            SML_PROTO_TYPE: parse_switchml;
            default: accept;
        }
    }

    state parse_switchml {
        packet.extract(hdr.sml);
        transition accept;
    }
}

// ============================================================================
// INGRESS PIPELINE
// ============================================================================
control TheIngress(inout headers hdr,
                   inout metadata meta,
                   inout standard_metadata_t standard_metadata) {

    // Stateful memory (registers) for aggregation
    register<int32_t>(CHUNK_SIZE) aggregation_reg;
    register<int32_t>(1) counter_reg;


    action drop() {
        mark_to_drop(standard_metadata);
    }

    action aggregate_and_increment() {
        int32_t current_val;
        aggregation_reg.read(current_val, 0);
        aggregation_reg.write(0, current_val + hdr.sml.payload0);
        aggregation_reg.read(current_val, 1);
        aggregation_reg.write(1, current_val + hdr.sml.payload1);
        aggregation_reg.read(current_val, 2);
        aggregation_reg.write(2, current_val + hdr.sml.payload2);
        aggregation_reg.read(current_val, 3);
        aggregation_reg.write(3, current_val + hdr.sml.payload3);
        counter_reg.write(0, meta.current_count + 1);
        // Drop the packet (not ready to broadcast)
        mark_to_drop(standard_metadata);
    }

    action broadcast_and_reset() {
        bit<32> tmp;
        // First, include this packet's contribution
        aggregation_reg.read(tmp, 0);
        aggregation_reg.write(0, tmp + hdr.sml.payload0);
        aggregation_reg.read(tmp, 1);
        aggregation_reg.write(1, tmp + hdr.sml.payload1);
        aggregation_reg.read(tmp, 2);
        aggregation_reg.write(2, tmp + hdr.sml.payload2);
        aggregation_reg.read(tmp, 3);
        aggregation_reg.write(3, tmp + hdr.sml.payload3);
        // Now read out the final sums
        aggregation_reg.read(hdr.sml.payload0, 0);
        aggregation_reg.read(hdr.sml.payload1, 1);
        aggregation_reg.read(hdr.sml.payload2, 2);
        aggregation_reg.read(hdr.sml.payload3, 3);
        // Reset state
        counter_reg.write(0, 0);
        aggregation_reg.write(0, 0);
        aggregation_reg.write(1, 0);
        aggregation_reg.write(2, 0);
        aggregation_reg.write(3, 0);
        hdr.eth.srcAddr = SWITCH_MAC;
        standard_metadata.mcast_grp = 1;
    }


    table aggregation_table {
        key = {
            meta.current_count : exact;
        }
        actions = {
            aggregate_and_increment;
            broadcast_and_reset;
            drop;
            NoAction;
        }
        size = 2;
        default_action = aggregate_and_increment();
    }

    apply {
        if (hdr.sml.isValid()) {
            // Read the counter register into metadata
            counter_reg.read(meta.current_count, 0);
            // Table will select the correct action based on the count
            aggregation_table.apply();
        }
    }
}

// ============================================================================
// EGRESS & OTHER PIPELINES
// ============================================================================
control TheEgress(inout headers hdr,
                  inout metadata meta,
                  inout standard_metadata_t standard_metadata) {
    apply { }
}
control TheChecksumVerification(inout headers hdr, inout metadata meta) {
    apply { }
}
control TheChecksumComputation(inout headers  hdr, inout metadata meta) {
    apply { }
}

// ============================================================================
// DEPARSER
// ============================================================================
control TheDeparser(packet_out packet, in headers hdr) {
    apply {
        packet.emit(hdr.eth);
        packet.emit(hdr.sml);
    }
}

// Switch instantiation
V1Switch(
    TheParser(),
    TheChecksumVerification(),
    TheIngress(),
    TheEgress(),
    TheChecksumComputation(),
    TheDeparser()
) main;