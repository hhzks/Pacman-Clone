import socket
import threading
import time

from netcommon import (encode, decode, ReliableChannel, PacketType,
                       PROTO_VERSION)


class ClientSession:
    """Client-side UDP session. Handles HELLO/WELCOME, receives LOBBY/START,
    sends INPUT, receives STATE/EVENT. One client talks to one host."""

    def __init__(self, host_ip, host_port, username=""):
        self._host_addr = (host_ip, host_port)
        self._username = username or ""
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.settimeout(0.1)
        self._sock.bind(("0.0.0.0", 0))  # ephemeral port
        self._reliable = ReliableChannel(send_callback=self._raw_send)
        self.client_id = None
        self._ghost_assignment = None
        self._maze_string = None
        self._thread = None
        self._running = False
        self._inbox = []  # list of decoded packets for the main thread
        self._inbox_lock = threading.Lock()
        self.start_info = None  # set once START arrives
        self.lobby_roster = []  # updated on every LOBBY
        self.events = []        # accumulates EVENT packets
        self.latest_state = None  # set by later task (16)
        self.prev_state = None
        self.latest_state_arrived_at = 0.0
        self.prev_state_arrived_at = 0.0
        self._input_seq = 0

    def _raw_send(self, addr, packet):
        try:
            self._sock.sendto(encode(packet), addr)
        except OSError:
            pass

    def _start_listener(self):
        self._running = True
        self._thread = threading.Thread(target=self._listener_loop,
                                        name="ClientListener", daemon=True)
        self._thread.start()

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
            # STATE packets are unreliable game snapshots; bypass seq dedup so
            # the game-level "s" field is preserved and no spurious ACKs are sent.
            if packet.get("t") == PacketType.STATE:
                with self._inbox_lock:
                    self._inbox.append(packet)
                continue
            processed = self._reliable.handle_incoming(addr, packet)
            if processed is None:
                continue
            with self._inbox_lock:
                self._inbox.append(processed)

    def drain_inbox(self):
        with self._inbox_lock:
            out, self._inbox = self._inbox, []
        return out

    def close(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        self._sock.close()

    def poll(self):
        """Drain the inbox and update self.start_info / self.lobby_roster
        / self.events. Call each frame from the main thread."""
        for pkt in self.drain_inbox():
            t = pkt.get("t")
            if t == PacketType.START:
                self.start_info = pkt
            elif t == PacketType.LOBBY:
                self.lobby_roster = pkt.get("players", [])
            elif t == PacketType.EVENT:
                self.events.append(pkt)
            elif t == PacketType.BYE:
                self.events.append({"t": PacketType.BYE})
            elif t == PacketType.STATE:
                # Discard out-of-order
                from netcommon import seq_newer
                if (self.latest_state is None
                        or seq_newer(pkt["s"], self.latest_state["s"])):
                    self.prev_state = self.latest_state
                    self.prev_state_arrived_at = self.latest_state_arrived_at
                    self.latest_state = pkt
                    self.latest_state_arrived_at = time.monotonic()

    def send_input(self, direction):
        if self.client_id is None:
            return
        self._input_seq += 1
        self._reliable.send_unreliable(self._host_addr, {
            "t": PacketType.INPUT,
            "clientId": self.client_id,
            "dir": direction,
            "inputSeq": self._input_seq,
        })

    def send_bye(self):
        if self.client_id is not None:
            self._reliable.send_reliable(self._host_addr, {
                "t": PacketType.BYE, "clientId": self.client_id,
            })

    def connect(self, timeout_s=2.0):
        """Send HELLO, wait for WELCOME or REJECT. Returns (ok, info_dict)."""
        self._start_listener()
        self._reliable.send_reliable(self._host_addr, {
            "t": PacketType.HELLO,
            "username": self._username,
            "protoVersion": PROTO_VERSION,
        })
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            batch = self.drain_inbox()
            welcome_pkt = None
            reject_pkt = None
            deferred = []
            for pkt in batch:
                t = pkt.get("t")
                if t == PacketType.WELCOME and welcome_pkt is None:
                    welcome_pkt = pkt
                elif t == PacketType.REJECT and reject_pkt is None:
                    reject_pkt = pkt
                else:
                    deferred.append(pkt)
            # Re-queue any non-handshake packets so poll() can see them later.
            if deferred:
                with self._inbox_lock:
                    self._inbox = deferred + self._inbox
            if welcome_pkt is not None:
                self.client_id = welcome_pkt["clientId"]
                self._ghost_assignment = welcome_pkt["ghostAssignment"]
                self._maze_string = welcome_pkt["mazeString"]
                return True, {
                    "clientId": self.client_id,
                    "ghostAssignment": self._ghost_assignment,
                    "mazeString": self._maze_string,
                    "playerSlots": welcome_pkt.get("playerSlots"),
                }
            if reject_pkt is not None:
                return False, {"reason": reject_pkt.get("reason", "unknown")}
            time.sleep(0.02)
        return False, {"error": "unreachable/timeout"}
