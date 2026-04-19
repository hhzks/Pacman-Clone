import time
import pytest
from netcommon import ReliableChannel, PacketType


class FakeTransport:
    """Captures sent packets; lets tests steer delivery."""
    def __init__(self):
        self.outbox = []  # list of (addr, packet_dict)

    def send(self, addr, packet):
        self.outbox.append((addr, packet))


def test_send_emits_packet_with_seq():
    t = FakeTransport()
    ch = ReliableChannel(send_callback=t.send, now_fn=lambda: 0.0)
    ch.send_reliable(("127.0.0.1", 5555), {"t": PacketType.HELLO, "username": "a"})
    assert len(t.outbox) == 1
    addr, pkt = t.outbox[0]
    assert addr == ("127.0.0.1", 5555)
    assert pkt["t"] == PacketType.HELLO
    assert "s" in pkt


def test_ack_stops_retransmit():
    clock = [0.0]
    t = FakeTransport()
    ch = ReliableChannel(send_callback=t.send, now_fn=lambda: clock[0])
    seq = ch.send_reliable(("127.0.0.1", 5555), {"t": PacketType.HELLO})
    # Ack arrives
    ch.handle_incoming(("127.0.0.1", 5555), {"t": PacketType.ACK, "ack": seq})
    clock[0] = 5.0  # way past any retry window
    ch.tick()
    assert len(t.outbox) == 1  # original, no retries


def test_no_ack_triggers_retries_then_timeout():
    clock = [0.0]
    t = FakeTransport()
    ch = ReliableChannel(send_callback=t.send, now_fn=lambda: clock[0])
    ch.send_reliable(("127.0.0.1", 5555), {"t": PacketType.HELLO})
    # Advance past each retry window
    for dt in (0.06, 0.12, 0.22, 0.42, 0.82):
        clock[0] += dt
        ch.tick()
    # Original send + up to 4 retries = at most 5 outbox entries
    assert 2 <= len(t.outbox) <= 5
    timeouts = ch.drain_timeouts()
    assert len(timeouts) == 1


def test_duplicate_incoming_is_deduped():
    t = FakeTransport()
    ch = ReliableChannel(send_callback=t.send, now_fn=lambda: 0.0)
    pkt = {"t": PacketType.HELLO, "s": 7, "username": "a"}
    first = ch.handle_incoming(("127.0.0.1", 5555), pkt)
    second = ch.handle_incoming(("127.0.0.1", 5555), pkt)
    assert first is not None
    assert second is None  # dedup: None means "already seen"
    # Both receptions should trigger an ACK send back
    acks = [p for (_, p) in t.outbox if p["t"] == PacketType.ACK]
    assert len(acks) == 2


def test_unreliable_packet_has_no_retries():
    clock = [0.0]
    t = FakeTransport()
    ch = ReliableChannel(send_callback=t.send, now_fn=lambda: clock[0])
    ch.send_unreliable(("127.0.0.1", 5555), {"t": PacketType.STATE})
    clock[0] = 5.0
    ch.tick()
    assert len(t.outbox) == 1
