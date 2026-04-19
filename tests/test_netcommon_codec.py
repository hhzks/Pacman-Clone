import pytest
from netcommon import encode, decode, PROTO_VERSION, PacketType


def test_encode_decode_roundtrip_hello():
    original = {"t": PacketType.HELLO, "s": 1, "username": "alice",
                "protoVersion": PROTO_VERSION}
    data = encode(original)
    assert isinstance(data, bytes)
    assert decode(data) == original


def test_encode_decode_roundtrip_state():
    original = {
        "t": PacketType.STATE, "s": 42, "tick": 100,
        "pacman": {"x": 12.5, "y": 340.0, "dir": 4, "alive": True},
        "ghosts": [{"id": "abc", "name": "Blinky", "x": 0, "y": 0,
                    "dir": 0, "scared": False, "dead": False}],
        "score": 250, "lives": 3, "level": 1, "dotsLeft": 40,
        "pelletDelta": [3, 7],
        "lastInputSeq": {"abc": 5},
    }
    assert decode(encode(original)) == original


def test_decode_returns_none_on_invalid_json():
    assert decode(b"not json at all") is None


def test_decode_returns_none_on_missing_type():
    assert decode(b'{"s": 1}') is None


def test_decode_returns_none_on_empty():
    assert decode(b"") is None


def test_packet_type_constants_are_strings():
    assert isinstance(PacketType.HELLO, str)
    assert PacketType.HELLO != PacketType.WELCOME


def test_proto_version_is_int():
    assert isinstance(PROTO_VERSION, int)
