import time
from netclient import ClientSession
from nethost import HostSession
from netcommon import PacketType


def test_input_sent_reflected_on_host(free_udp_port):
    host = HostSession(bind_port=free_udp_port, maze_string="M", max_clients=4)
    host.start()
    try:
        c = ClientSession("127.0.0.1", free_udp_port, "a")
        assert c.connect(timeout_s=2.0)[0] is True
        c.send_input(direction=3)
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            inputs = host.get_client_inputs()
            if c.client_id in inputs and inputs[c.client_id]["dir"] == 3:
                c.close()
                return
            time.sleep(0.02)
        c.close()
        assert False, f"host never saw INPUT: {host.get_client_inputs()}"
    finally:
        host.stop()


def test_state_buffered_as_prev_and_latest(free_udp_port):
    host = HostSession(bind_port=free_udp_port, maze_string="M", max_clients=4)
    host.start()
    try:
        c = ClientSession("127.0.0.1", free_udp_port, "a")
        assert c.connect(timeout_s=2.0)[0] is True
        # Simulate host broadcasting two STATE packets
        host.broadcast_state({
            "t": PacketType.STATE, "s": 1, "tick": 1,
            "pacman": {"x": 0, "y": 0, "dir": 0, "alive": True},
            "ghosts": [], "score": 0, "lives": 3, "level": 1,
            "dotsLeft": 10, "pelletDelta": [], "lastInputSeq": {},
        })
        time.sleep(0.05)
        host.broadcast_state({
            "t": PacketType.STATE, "s": 2, "tick": 2,
            "pacman": {"x": 5, "y": 0, "dir": 4, "alive": True},
            "ghosts": [], "score": 10, "lives": 3, "level": 1,
            "dotsLeft": 9, "pelletDelta": [0], "lastInputSeq": {},
        })
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            c.poll()
            if c.latest_state is not None and c.latest_state["s"] == 2:
                break
            time.sleep(0.02)
        assert c.latest_state is not None
        assert c.latest_state["s"] == 2
        assert c.prev_state is not None
        assert c.prev_state["s"] == 1
        c.close()
    finally:
        host.stop()
