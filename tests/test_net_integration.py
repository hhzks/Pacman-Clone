import time
import pytest
from nethost import HostSession
from netclient import ClientSession
from netcommon import PacketType, PROTO_VERSION


def _wait(cond, budget=2.0):
    deadline = time.monotonic() + budget
    while time.monotonic() < deadline:
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_two_clients_full_lobby_and_start(free_udp_port):
    host = HostSession(bind_port=free_udp_port, maze_string="M",
                       max_clients=2)
    host.start()
    try:
        a = ClientSession("127.0.0.1", free_udp_port, "alice")
        b = ClientSession("127.0.0.1", free_udp_port, "bob")
        ok_a, _ = a.connect(timeout_s=2.0)
        ok_b, _ = b.connect(timeout_s=2.0)
        assert ok_a and ok_b

        assert _wait(lambda: len(host.get_roster()) == 2)

        # Verify roster propagated to both clients
        def _has_two(c):
            c.poll()
            return len(c.lobby_roster) == 2
        assert _wait(lambda: _has_two(a))
        assert _wait(lambda: _has_two(b))

        # Inputs
        a.send_input(1); b.send_input(3)
        assert _wait(lambda: (host.get_client_inputs().get(a.client_id, {}).get("dir") == 1
                              and host.get_client_inputs().get(b.client_id, {}).get("dir") == 3))

        # Start match
        host.start_match(fps=60, level=1, rng_seed=42)
        def _got_start(c):
            c.poll()
            return c.start_info is not None
        assert _wait(lambda: _got_start(a))
        assert _wait(lambda: _got_start(b))

        # Host broadcasts STATE; clients receive
        host.broadcast_state({
            "t": PacketType.STATE, "s": 1, "tick": 1,
            "pacman": {"x": 0, "y": 0, "dir": 0, "alive": True},
            "ghosts": [], "score": 0, "lives": 3, "level": 1,
            "dotsLeft": 100, "pelletDelta": [], "lastInputSeq": {},
        })
        def _got_state(c):
            c.poll()
            return c.latest_state is not None
        assert _wait(lambda: _got_state(a))
        assert _wait(lambda: _got_state(b))

        a.close(); b.close()
    finally:
        host.stop()


def test_client_bye_mid_session_host_reassigns(free_udp_port):
    host = HostSession(bind_port=free_udp_port, maze_string="M",
                       max_clients=4, ping_timeout_s=0.3)
    host.start()
    try:
        a = ClientSession("127.0.0.1", free_udp_port, "a")
        assert a.connect(timeout_s=2.0)[0]
        assert _wait(lambda: len(host.get_roster()) == 1)
        a.send_bye(); a.close()
        assert _wait(lambda: len(host.get_roster()) == 0, budget=2.0)
    finally:
        host.stop()


def test_hard_disconnect_via_timeout(free_udp_port):
    host = HostSession(bind_port=free_udp_port, maze_string="M",
                       max_clients=4, ping_timeout_s=0.3)
    host.start()
    try:
        a = ClientSession("127.0.0.1", free_udp_port, "a")
        assert a.connect(timeout_s=2.0)[0]
        a.close()  # silent drop — no BYE
        # Wait past timeout and manually trigger sweep
        time.sleep(0.5)
        host.check_timeouts()
        assert len(host.get_roster()) == 0
    finally:
        host.stop()
