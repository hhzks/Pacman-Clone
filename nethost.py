import secrets
import socket
import threading
import time

from netcommon import (encode, decode, ReliableChannel, PacketType,
                       PROTO_VERSION)

GHOST_ASSIGNMENT_ORDER = ["Blinky", "Inky", "Pinky", "Clyde"]


class HostSession:
    """UDP socket + background listener thread. This is the scaffolding —
    higher-level concerns (handshake, lobby, broadcast, disconnects) are
    added in later tasks."""

    def __init__(self, bind_port, bind_host="0.0.0.0", maze_string="",
                 max_clients=4, ping_timeout_s=3.0):
        self._bind_port = bind_port
        self._bind_host = bind_host
        self._maze_string = maze_string
        self._max_clients = max_clients  # number of human ghost slots
        self._sock = None
        self._thread = None
        self._running = False
        self._packet_count = 0
        self._packet_count_lock = threading.Lock()
        self._reliable = None
        # Client registry: clientId -> {"addr", "username", "ghost", "last_seen"}
        self._clients = {}
        self._clients_lock = threading.Lock()
        # Reverse index: addr -> clientId (fast lookup on every packet)
        self._addr_to_id = {}
        self._game_started = False
        self._ping_timeout_s = ping_timeout_s
        # clientId -> {"dir": int, "seq": int}
        self._client_inputs = {}
        self._inputs_lock = threading.Lock()

    @property
    def port(self):
        return self._bind_port

    def start(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self._bind_host, self._bind_port))
        self._sock.settimeout(0.1)
        self._reliable = ReliableChannel(send_callback=self._raw_send)
        self._running = True
        self._thread = threading.Thread(target=self._listener_loop,
                                        name="HostListener", daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if self._sock is not None:
            self._sock.close()
        self._sock = None
        self._thread = None

    def is_running(self):
        return self._running

    def _raw_send(self, addr, packet):
        if self._sock is None:
            return
        try:
            self._sock.sendto(encode(packet), addr)
        except OSError:
            pass  # socket closed during shutdown

    def _listener_loop(self):
        while self._running:
            try:
                data, addr = self._sock.recvfrom(8192)
            except socket.timeout:
                self._reliable.tick()
                continue
            except OSError as exc:
                # 10054 = WSAECONNRESET: Windows sends this when an ICMP
                # "port unreachable" is received (e.g. after sending to a
                # client whose socket was closed).  It is safe to continue.
                if getattr(exc, "winerror", None) == 10054:
                    continue
                return
            packet = decode(data)
            if packet is None:
                continue
            with self._packet_count_lock:
                self._packet_count += 1
            # INPUT packets are unreliable; bypass seq dedup so retransmits
            # from the client (or seq collisions with other packet types) are
            # never silently dropped.
            if packet.get("t") == PacketType.INPUT:
                self._dispatch(addr, packet)
                continue
            processed = self._reliable.handle_incoming(addr, packet)
            if processed is None:
                continue
            self._dispatch(addr, processed)

    def _dispatch(self, addr, packet):
        t = packet.get("t")
        if t == PacketType.HELLO:
            self._handle_hello(addr, packet)
            return
        cid = packet.get("clientId")
        if not cid:
            return
        with self._clients_lock:
            info = self._clients.get(cid)
            if info is None or info["addr"] != addr:
                return
            info["last_seen"] = time.monotonic()
        if t == PacketType.INPUT:
            self._handle_input(cid, packet)
        elif t == PacketType.BYE:
            self._remove_client(cid)
        elif t == PacketType.PING:
            self._reliable.send_unreliable(addr, {
                "t": PacketType.PONG, "clientId": cid})
        # PONG from client is ignored; last_seen refresh is sufficient.

    def _handle_input(self, cid, packet):
        dir_ = packet.get("dir", 0)
        seq = packet.get("inputSeq", 0)
        with self._inputs_lock:
            prev = self._client_inputs.get(cid)
            if prev is not None and seq < prev["seq"]:
                return  # stale
            self._client_inputs[cid] = {"dir": dir_, "seq": seq}

    def _remove_client(self, cid):
        with self._clients_lock:
            info = self._clients.pop(cid, None)
            if info:
                self._addr_to_id.pop(info["addr"], None)
        with self._inputs_lock:
            self._client_inputs.pop(cid, None)
        if info:
            self._broadcast_lobby()
            # Caller (Task 18 runHostedGame) will handle moving the ghost to Bots.

    def get_client_inputs(self):
        with self._inputs_lock:
            return {cid: dict(v) for cid, v in self._client_inputs.items()}

    def check_timeouts(self):
        """Remove clients that haven't sent anything for > ping_timeout_s.
        Call this periodically from the main thread."""
        now = time.monotonic()
        stale = []
        with self._clients_lock:
            for cid, info in list(self._clients.items()):
                if now - info["last_seen"] > self._ping_timeout_s:
                    stale.append(cid)
        for cid in stale:
            self._remove_client(cid)
        return stale

    def get_roster(self):
        """Snapshot of current clients for the lobby UI. Thread-safe."""
        with self._clients_lock:
            return [
                {"clientId": cid, "username": info["username"],
                 "ghost": info["ghost"], "addr": info["addr"]}
                for cid, info in self._clients.items()
            ]

    def _broadcast_lobby(self):
        roster = self.get_roster()
        payload = {
            "t": PacketType.LOBBY,
            "players": [{"username": r["username"], "ghost": r["ghost"]}
                        for r in roster],
        }
        with self._clients_lock:
            addrs = [info["addr"] for info in self._clients.values()]
        for addr in addrs:
            self._reliable.send_reliable(addr, dict(payload))

    def start_match(self, fps, level, rng_seed):
        """Broadcast START, flip the in-progress flag."""
        with self._clients_lock:
            if self._game_started:
                return
            self._game_started = True
            addrs = [info["addr"] for info in self._clients.values()]
        payload = {
            "t": PacketType.START,
            "fps": fps,
            "level": level,
            "rngSeed": rng_seed,
            "mazeString": self._maze_string,
            "startTick": int(time.monotonic() * 1000),
        }
        for addr in addrs:
            self._reliable.send_reliable(addr, dict(payload))

    def is_game_started(self):
        return self._game_started

    def _handle_hello(self, addr, packet):
        if packet.get("protoVersion") != PROTO_VERSION:
            self._reliable.send_reliable(addr, {
                "t": PacketType.REJECT, "reason": "version"
            })
            return
        if self._game_started:
            self._reliable.send_reliable(addr, {
                "t": PacketType.REJECT, "reason": "in-progress"
            })
            return
        with self._clients_lock:
            if len(self._clients) >= self._max_clients:
                self._reliable.send_reliable(addr, {
                    "t": PacketType.REJECT, "reason": "full"
                })
                return
            existing_id = self._addr_to_id.get(addr)
            if existing_id is None:
                client_id = secrets.token_urlsafe(16)
                ghost = GHOST_ASSIGNMENT_ORDER[len(self._clients)]
                self._clients[client_id] = {
                    "addr": addr,
                    "username": packet.get("username", "") or "",
                    "ghost": ghost,
                    "last_seen": time.monotonic(),
                }
                self._addr_to_id[addr] = client_id
                broadcast_needed = True
            else:
                client_id = existing_id
                ghost = self._clients[client_id]["ghost"]
                broadcast_needed = False
        # (now outside the lock)
        self._reliable.send_reliable(addr, {
            "t": PacketType.WELCOME,
            "clientId": client_id,
            "mazeString": self._maze_string,
            "playerSlots": self._max_clients,
            "ghostAssignment": ghost,
        })
        if broadcast_needed:
            self._broadcast_lobby()

    def broadcast_state(self, snapshot_packet):
        """Fire-and-forget STATE broadcast to every client."""
        with self._clients_lock:
            addrs = [info["addr"] for info in self._clients.values()]
        for addr in addrs:
            self._raw_send(addr, dict(snapshot_packet))

    def broadcast_event(self, event_packet):
        """Reliable broadcast for EVENT packets."""
        with self._clients_lock:
            addrs = [info["addr"] for info in self._clients.values()]
        for addr in addrs:
            self._reliable.send_reliable(addr, dict(event_packet))

    def debug_packet_count(self):
        with self._packet_count_lock:
            return self._packet_count
