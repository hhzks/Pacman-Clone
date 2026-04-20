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

    def __init__(self, bind_port, bind_host="0.0.0.0",
                 maze_string="", max_clients=4):
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
            except OSError:
                return
            packet = decode(data)
            if packet is None:
                continue
            with self._packet_count_lock:
                self._packet_count += 1
            processed = self._reliable.handle_incoming(addr, packet)
            if processed is None:
                continue
            self._dispatch(addr, processed)

    def _dispatch(self, addr, packet):
        t = packet.get("t")
        if t == PacketType.HELLO:
            self._handle_hello(addr, packet)
        # Later tasks add INPUT, BYE, PING handling here.

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

    def debug_packet_count(self):
        with self._packet_count_lock:
            return self._packet_count
