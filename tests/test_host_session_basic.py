import socket
import time
import pytest
from nethost import HostSession
from netcommon import encode, decode, PacketType, MAX_CLIENT_PACKETS_PER_SEC


def test_host_binds_and_closes(free_udp_port):
    host = HostSession(bind_port=free_udp_port)
    host.start()
    try:
        assert host.port == free_udp_port
        assert host.is_running()
    finally:
        host.stop()
    assert not host.is_running()


def test_host_bind_failure_raises(free_udp_port):
    # Hold the port on 0.0.0.0 (same address HostSession defaults to)
    blocker = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    blocker.bind(("0.0.0.0", free_udp_port))
    try:
        with pytest.raises(OSError):
            HostSession(bind_port=free_udp_port).start()
    finally:
        blocker.close()


def test_host_receives_arbitrary_packet(free_udp_port):
    host = HostSession(bind_port=free_udp_port)
    host.start()
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.sendto(encode({"t": "UNKNOWN", "s": 1}),
                      ("127.0.0.1", free_udp_port))
        # Give the listener a moment
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            if host.debug_packet_count() > 0:
                break
            time.sleep(0.02)
        assert host.debug_packet_count() >= 1
    finally:
        host.stop()


def test_rate_limit_drops_excess_packets(free_udp_port):
    host = HostSession(bind_port=free_udp_port)
    host.start()
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        flood_count = MAX_CLIENT_PACKETS_PER_SEC + 100
        pkt = encode({"t": "noop"})
        for _ in range(flood_count):
            client.sendto(pkt, ("127.0.0.1", free_udp_port))
        # Wait for packets to be processed
        time.sleep(0.3)
        addr = ("127.0.0.1", client.getsockname()[1])
        # The rate bucket for this addr should not exceed MAX_CLIENT_PACKETS_PER_SEC
        with host._rate_lock:
            bucket = host._rate_buckets.get(("127.0.0.1", free_udp_port), None)
            # bucket may be keyed by the actual client addr; check all buckets
            total_in_buckets = sum(len(b) for b in host._rate_buckets.values())
        assert total_in_buckets <= MAX_CLIENT_PACKETS_PER_SEC
    finally:
        host.stop()
