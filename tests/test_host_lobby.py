import socket, time
from nethost import HostSession
from netcommon import encode, decode, PacketType, PROTO_VERSION


def _join(port, username):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(2.0)
    s.sendto(encode({"t": PacketType.HELLO, "s": 1,
                     "username": username,
                     "protoVersion": PROTO_VERSION}),
             ("127.0.0.1", port))
    welcome = None
    lobby = None
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        try:
            data, _ = s.recvfrom(8192)
            pkt = decode(data)
            if not pkt:
                continue
            if pkt["t"] == PacketType.WELCOME:
                welcome = pkt
            elif pkt["t"] == PacketType.LOBBY:
                lobby = pkt
                break
        except socket.timeout:
            break
    return s, welcome, lobby


def test_host_roster_reports_joined_clients(free_udp_port):
    host = HostSession(bind_port=free_udp_port,
                       maze_string="MAZE", max_clients=4)
    host.start()
    try:
        a, wa, la = _join(free_udp_port, "alice")
        b, wb, lb = _join(free_udp_port, "bob")
        assert wa is not None and wb is not None
        roster = host.get_roster()
        assert len(roster) == 2
        usernames = {r["username"] for r in roster}
        assert usernames == {"alice", "bob"}
    finally:
        host.stop()


def test_start_match_broadcasts_to_all_clients(free_udp_port):
    host = HostSession(bind_port=free_udp_port,
                       maze_string="M", max_clients=2)
    host.start()
    try:
        a, wa, la = _join(free_udp_port, "alice")
        b, wb, lb = _join(free_udp_port, "bob")
        host.start_match(fps=60, level=1, rng_seed=42)
        starts = {}
        for name, sock in (("alice", a), ("bob", b)):
            deadline = time.monotonic() + 2.0
            sock.settimeout(0.2)
            while time.monotonic() < deadline:
                try:
                    data, _ = sock.recvfrom(8192)
                    pkt = decode(data)
                    if pkt and pkt["t"] == PacketType.START:
                        starts[name] = pkt
                        break
                except socket.timeout:
                    continue
        assert "alice" in starts and "bob" in starts
        assert starts["alice"]["rngSeed"] == 42
    finally:
        host.stop()


def test_join_after_start_is_rejected_in_progress(free_udp_port):
    host = HostSession(bind_port=free_udp_port,
                       maze_string="M", max_clients=2)
    host.start()
    try:
        _join(free_udp_port, "alice")
        host.start_match(fps=60, level=1, rng_seed=1)
        # New client tries to join after START
        c = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        c.settimeout(2.0)
        c.sendto(encode({"t": PacketType.HELLO, "s": 1, "username": "late",
                         "protoVersion": PROTO_VERSION}),
                 ("127.0.0.1", free_udp_port))
        deadline = time.monotonic() + 2.0
        got_reject = False
        while time.monotonic() < deadline:
            try:
                data, _ = c.recvfrom(8192)
                pkt = decode(data)
                if pkt and pkt["t"] == PacketType.REJECT and pkt.get("reason") == "in-progress":
                    got_reject = True
                    break
            except socket.timeout:
                break
        assert got_reject
    finally:
        host.stop()
