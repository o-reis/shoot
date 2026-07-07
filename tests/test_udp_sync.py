import math

from network.udp_sync import (
    _encode_state, _encode_attack, _encode_dead, _decode_packet,
    _PACKET_STATE, _PACKET_ATTACK, _PACKET_DEAD,
)


def test_state_roundtrip():
    payload = _encode_state("42", 1.5, 2.5, 0.75, 88)
    kind, pid, x, y, angle, hp = _decode_packet(payload)
    assert kind == "state"
    assert pid == "42"
    assert math.isclose(x, 1.5, abs_tol=1e-6)
    assert math.isclose(y, 2.5, abs_tol=1e-6)
    assert math.isclose(angle, 0.75, abs_tol=1e-6)
    assert hp == 88


def test_attack_roundtrip():
    payload = _encode_attack("7", "9", 40)
    kind, attacker, target, damage = _decode_packet(payload)
    assert kind == "attack"
    assert attacker == "7"
    assert target == "9"
    assert damage == 40


def test_dead_roundtrip():
    payload = _encode_dead("13")
    kind, pid = _decode_packet(payload)
    assert kind == "dead"
    assert pid == "13"


def test_packet_type_tags():
    assert _encode_state("1", 0, 0, 0, 0)[0] == _PACKET_STATE
    assert _encode_attack("1", "2", 0)[0] == _PACKET_ATTACK
    assert _encode_dead("1")[0] == _PACKET_DEAD


def test_empty_packet_rejected():
    assert _decode_packet(b"") is None


def test_truncated_packet_rejected():
    full = _encode_state("1", 0, 0, 0, 0)
    assert _decode_packet(full[:10]) is None


def test_unknown_type_rejected():
    assert _decode_packet(b"\xff" + b"\x00" * 40) is None
