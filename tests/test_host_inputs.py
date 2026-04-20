import socket, time
from nethost import HostSession
from netcommon import encode, decode, PacketType, PROTO_VERSION


def _hello_welcome(port, username):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(2.0)
    s.sendto(encode({"t": PacketType.HELLO, "s": 1, "username": username,
                     "protoVersion": PROTO_VERSION}),
             ("127.0.0.1", port))
    deadline = time.monotonic() + 2.0
    welcome = None
    while time.monotonic() < deadline:
        try:
            data, _ = s.recvfrom(8192)
            pkt = decode(data)
            if pkt and pkt["t"] == PacketType.WELCOME:
                welcome = pkt
                break
        except socket.timeout:
            break
    assert welcome is not None, "did not receive WELCOME"
    return s, welcome


def test_input_updates_buffer(free_udp_port):
    host = HostSession(bind_port=free_udp_port,
                       maze_string="M", max_clients=4)
    host.start()
    try:
        s, welcome = _hello_welcome(free_udp_port, "alice")
        cid = welcome["clientId"]
        s.sendto(encode({"t": PacketType.INPUT, "s": 1,
                         "clientId": cid, "dir": 4, "inputSeq": 10}),
                 ("127.0.0.1", free_udp_port))
        # Wait for host to process
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            buf = host.get_client_inputs()
            if cid in buf and buf[cid]["dir"] == 4:
                return
            time.sleep(0.02)
        assert False, f"input not reflected: {host.get_client_inputs()}"
    finally:
        host.stop()


def test_bye_removes_client(free_udp_port):
    host = HostSession(bind_port=free_udp_port,
                       maze_string="M", max_clients=4)
    host.start()
    try:
        s, welcome = _hello_welcome(free_udp_port, "alice")
        cid = welcome["clientId"]
        assert len(host.get_roster()) == 1
        s.sendto(encode({"t": PacketType.BYE, "s": 2, "clientId": cid}),
                 ("127.0.0.1", free_udp_port))
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            if len(host.get_roster()) == 0:
                return
            time.sleep(0.02)
        assert False, "client was not removed on BYE"
    finally:
        host.stop()


def test_ping_timeout_removes_silent_client(free_udp_port):
    host = HostSession(bind_port=free_udp_port,
                       maze_string="M", max_clients=4,
                       ping_timeout_s=0.3)  # shortened for test
    host.start()
    try:
        s, welcome = _hello_welcome(free_udp_port, "alice")
        time.sleep(0.6)  # stay silent past timeout
        host.check_timeouts()
        assert len(host.get_roster()) == 0
    finally:
        host.stop()


def test_unknown_client_id_input_dropped(free_udp_port):
    host = HostSession(bind_port=free_udp_port,
                       maze_string="M", max_clients=4)
    host.start()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.sendto(encode({"t": PacketType.INPUT, "s": 1,
                         "clientId": "nonexistent", "dir": 3, "inputSeq": 1}),
                 ("127.0.0.1", free_udp_port))
        time.sleep(0.2)
        assert host.get_client_inputs() == {}
    finally:
        host.stop()
