import json
import threading
import time as _time

PROTO_VERSION = 1
NET_HZ = 30
DEFAULT_PORT = 5555
PING_INTERVAL_S = 1.0
PING_TIMEOUT_S = 3.0
MAX_CLIENT_PACKETS_PER_SEC = 500


class PacketType:
    HELLO = "HELLO"
    WELCOME = "WELCOME"
    REJECT = "REJECT"
    LOBBY = "LOBBY"
    START = "START"
    INPUT = "INPUT"
    STATE = "STATE"
    EVENT = "EVENT"
    PING = "PING"
    PONG = "PONG"
    BYE = "BYE"
    ACK = "ACK"


def encode(packet: dict) -> bytes:
    """Serialise a packet dict to UTF-8 JSON bytes."""
    return json.dumps(packet, separators=(",", ":")).encode("utf-8")


def decode(data: bytes):
    """Deserialise bytes into a dict. Returns None on any parse failure
    or if the packet is missing the mandatory 't' (type) field."""
    if not data:
        return None
    try:
        obj = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(obj, dict) or "t" not in obj:
        return None
    return obj


SEQ_MOD = 1 << 32
SEQ_HALF = 1 << 31


def seq_next(s: int) -> int:
    """Return the next sequence number (32-bit wrap)."""
    return (s + 1) & (SEQ_MOD - 1)


def seq_newer(a: int, b: int) -> bool:
    """True if sequence `a` is strictly newer than `b` under wrap-around.

    Uses the standard (a - b) mod 2^32 comparison against the half range.
    """
    return ((a - b) & (SEQ_MOD - 1)) != 0 and ((a - b) & (SEQ_MOD - 1)) < SEQ_HALF


RELIABLE_RETRY_DELAYS_S = (0.05, 0.10, 0.20, 0.40)
RELIABLE_MAX_RETRIES = len(RELIABLE_RETRY_DELAYS_S)


class ReliableChannel:
    """Seq/ACK/retry layer for reliable packets; pass-through for unreliable.

    `send_callback(addr, packet_dict)` is the transport primitive. `now_fn()`
    returns a monotonic time in seconds (injectable for tests).
    """

    def __init__(self, send_callback, now_fn=None):
        self._send = send_callback
        self._now = now_fn if now_fn is not None else _time.monotonic
        self._lock = threading.Lock()
        self._next_out_seq = 1
        self._outbox = {}   # seq -> {"addr", "packet", "deadline", "retries", "first_sent"}
        self._seen_in = {}  # (addr, seq) -> True (dedup set)
        self._timed_out = []

    def _alloc_seq(self):
        s = self._next_out_seq
        self._next_out_seq = seq_next(s)
        return s

    def send_reliable(self, addr, packet):
        """Send with retries; returns the seq assigned."""
        with self._lock:
            s = self._alloc_seq()
            packet = dict(packet)
            packet["s"] = s
            now = self._now()
            self._outbox[s] = {
                "addr": addr,
                "packet": packet,
                "deadline": now + RELIABLE_RETRY_DELAYS_S[0],
                "retries": 0,
                "first_sent": now,
            }
        self._send(addr, packet)
        return s

    def send_unreliable(self, addr, packet):
        """Fire-and-forget; still assigns a seq so receivers can order."""
        with self._lock:
            s = self._alloc_seq()
        packet = dict(packet)
        packet["s"] = s
        self._send(addr, packet)
        return s

    def handle_incoming(self, addr, packet):
        """Returns the packet if it should be processed, or None if duplicate.

        ACK packets are consumed internally and return None.
        Reliable packets (those carrying 's' and expected to be ACKed) get an
        ACK emitted here automatically.
        """
        if packet.get("t") == PacketType.ACK:
            ack = packet.get("ack")
            with self._lock:
                self._outbox.pop(ack, None)
            return None
        s = packet.get("s")
        if s is None:
            return packet
        key = (addr, s)
        with self._lock:
            dup = key in self._seen_in
            self._seen_in[key] = True
        # Always ACK — even duplicates — so the peer stops retrying.
        self._send(addr, {"t": PacketType.ACK, "ack": s})
        if dup:
            return None
        return packet

    def tick(self):
        """Call periodically (every ~20ms) to drive retries/timeouts."""
        now = self._now()
        to_resend = []
        to_timeout = []
        with self._lock:
            for seq, entry in list(self._outbox.items()):
                if now < entry["deadline"]:
                    continue
                if entry["retries"] >= RELIABLE_MAX_RETRIES:
                    to_timeout.append((seq, entry))
                    del self._outbox[seq]
                    continue
                entry["retries"] += 1
                delay = RELIABLE_RETRY_DELAYS_S[min(entry["retries"],
                                                   RELIABLE_MAX_RETRIES - 1)]
                entry["deadline"] = now + delay
                to_resend.append((entry["addr"], entry["packet"]))
            for seq, entry in to_timeout:
                self._timed_out.append(entry)
        for addr, pkt in to_resend:
            self._send(addr, pkt)

    def drain_timeouts(self):
        with self._lock:
            out = self._timed_out
            self._timed_out = []
        return out
