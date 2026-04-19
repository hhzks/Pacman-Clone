import socket
import time
import pytest
from nethost import HostSession
from netcommon import encode, decode, PacketType


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
