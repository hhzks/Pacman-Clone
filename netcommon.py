import json

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
