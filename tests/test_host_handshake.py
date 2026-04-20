import socket
import time
import pytest
from nethost import HostSession
from netcommon import encode, decode, PacketType, PROTO_VERSION


def _send_and_wait(client_sock, server_addr, packet, timeout=1.5):
    client_sock.sendto(encode(packet), server_addr)
    client_sock.settimeout(timeout)
    try:
        data, _ = client_sock.recvfrom(8192)
        return decode(data)
    except socket.timeout:
        return None


def test_hello_gets_welcome(free_udp_port):
    host = HostSession(bind_port=free_udp_port,
                       maze_string="MAZE", max_clients=4)
    host.start()
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        reply = _send_and_wait(
            client, ("127.0.0.1", free_udp_port),
            {"t": PacketType.HELLO, "s": 1,
             "username": "alice", "protoVersion": PROTO_VERSION},
        )
        # First reply may be an ACK; drain until we see WELCOME or REJECT
        deadline = time.monotonic() + 2.0
        found = None
        while time.monotonic() < deadline:
            if reply and reply["t"] in (PacketType.WELCOME, PacketType.REJECT):
                found = reply
                break
            try:
                data, _ = client.recvfrom(8192)
                reply = decode(data)
            except socket.timeout:
                break
        assert found is not None
        assert found["t"] == PacketType.WELCOME
        assert "clientId" in found
        assert found["mazeString"] == "MAZE"
        assert found["ghostAssignment"] == "Blinky"
    finally:
        host.stop()


def test_version_mismatch_rejected(free_udp_port):
    host = HostSession(bind_port=free_udp_port,
                       maze_string="MAZE", max_clients=4)
    host.start()
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.settimeout(1.5)
        client.sendto(encode({"t": PacketType.HELLO, "s": 1, "username": "x",
                              "protoVersion": PROTO_VERSION + 999}),
                      ("127.0.0.1", free_udp_port))
        deadline = time.monotonic() + 2.0
        found = None
        while time.monotonic() < deadline:
            try:
                data, _ = client.recvfrom(8192)
                pkt = decode(data)
                if pkt and pkt["t"] == PacketType.REJECT:
                    found = pkt
                    break
            except socket.timeout:
                break
        assert found is not None
        assert found["reason"] == "version"
    finally:
        host.stop()


def test_full_lobby_rejects_further_joins(free_udp_port):
    host = HostSession(bind_port=free_udp_port,
                       maze_string="MAZE", max_clients=1)
    host.start()
    try:
        # First join succeeds
        a = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        a.sendto(encode({"t": PacketType.HELLO, "s": 1, "username": "alice",
                         "protoVersion": PROTO_VERSION}),
                 ("127.0.0.1", free_udp_port))
        time.sleep(0.3)
        # Second join should be rejected
        b = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        b.settimeout(1.5)
        b.sendto(encode({"t": PacketType.HELLO, "s": 1, "username": "bob",
                         "protoVersion": PROTO_VERSION}),
                 ("127.0.0.1", free_udp_port))
        deadline = time.monotonic() + 2.0
        reject = None
        while time.monotonic() < deadline:
            try:
                data, _ = b.recvfrom(8192)
                pkt = decode(data)
                if pkt and pkt["t"] == PacketType.REJECT:
                    reject = pkt
                    break
            except socket.timeout:
                break
        assert reject is not None
        assert reject["reason"] == "full"
    finally:
        host.stop()
