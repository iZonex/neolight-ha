"""Packet headers observed in NeoLight 1.1.0's native P2P sender."""

import struct


MAGIC = 0x12345678
TALK_START_TYPE = 6
TALK_AUDIO_TYPE = 6


def control_packet(packet_type: int, operation: int) -> bytes:
    return struct.pack("<IIIII", MAGIC, packet_type, 0, 8, 8) + struct.pack("<II", 0, operation)


def audio_packet(timestamp: int, pcmu: bytes) -> bytes:
    if len(pcmu) != 320:
        raise ValueError("NeoLight talk frames contain 320 G.711 μ-law bytes")
    return struct.pack("<IIIIIIII", MAGIC, TALK_AUDIO_TYPE, 0x85, 0, 1, 0, timestamp & 0xFFFFFFFF, len(pcmu)) + pcmu
