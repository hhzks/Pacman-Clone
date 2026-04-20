import time
from nethost import HostSession
from netclient import ClientSession


def test_client_receives_start(free_udp_port):
    host = HostSession(bind_port=free_udp_port, maze_string="M", max_clients=2)
    host.start()
    try:
        alice = ClientSession("127.0.0.1", free_udp_port, "alice")
        assert alice.connect(timeout_s=2.0)[0] is True
        bob = ClientSession("127.0.0.1", free_udp_port, "bob")
        assert bob.connect(timeout_s=2.0)[0] is True

        host.start_match(fps=60, level=1, rng_seed=77)

        def wait_for_start(client, budget=2.0):
            deadline = time.monotonic() + budget
            while time.monotonic() < deadline:
                if client.start_info is not None:
                    return True
                client.poll()
                time.sleep(0.02)
            return False

        assert wait_for_start(alice)
        assert alice.start_info["rngSeed"] == 77
        assert wait_for_start(bob)

        alice.close(); bob.close()
    finally:
        host.stop()


def test_client_bye_removes_from_host_roster(free_udp_port):
    host = HostSession(bind_port=free_udp_port, maze_string="M", max_clients=4)
    host.start()
    try:
        c = ClientSession("127.0.0.1", free_udp_port, "a")
        assert c.connect(timeout_s=2.0)[0] is True
        assert len(host.get_roster()) == 1
        c.send_bye()
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            if len(host.get_roster()) == 0:
                break
            time.sleep(0.02)
        assert len(host.get_roster()) == 0
        c.close()
    finally:
        host.stop()
