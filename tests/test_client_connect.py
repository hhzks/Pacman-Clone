import time, pytest
from nethost import HostSession
from netclient import ClientSession


def test_client_connects_and_receives_welcome(free_udp_port):
    host = HostSession(bind_port=free_udp_port, maze_string="MAZE", max_clients=4)
    host.start()
    try:
        client = ClientSession(host_ip="127.0.0.1", host_port=free_udp_port,
                               username="alice")
        ok, info = client.connect(timeout_s=2.0)
        assert ok is True
        assert info["mazeString"] == "MAZE"
        assert info["ghostAssignment"] == "Blinky"
        assert client.client_id is not None
        client.close()
    finally:
        host.stop()


def test_client_connect_timeout(free_udp_port):
    # No host running
    client = ClientSession(host_ip="127.0.0.1", host_port=free_udp_port,
                           username="alice")
    ok, info = client.connect(timeout_s=1.0)
    assert ok is False
    assert "unreachable" in info.get("error", "") or "timeout" in info.get("error", "")
    client.close()


def test_client_connect_rejected_version(free_udp_port):
    host = HostSession(bind_port=free_udp_port, maze_string="M", max_clients=4)
    host.start()
    try:
        # Monkeypatch the client's proto version locally
        import netclient
        original = netclient.PROTO_VERSION
        netclient.PROTO_VERSION = original + 999
        try:
            client = ClientSession(host_ip="127.0.0.1",
                                   host_port=free_udp_port, username="x")
            ok, info = client.connect(timeout_s=2.0)
            assert ok is False
            assert info.get("reason") == "version"
            client.close()
        finally:
            netclient.PROTO_VERSION = original
    finally:
        host.stop()
