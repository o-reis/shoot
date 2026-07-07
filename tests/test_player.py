import math

from engine.player import Player


def test_take_damage_reduces_hp():
    p = Player(0, 0, 0, hp=100)
    p.take_damage(30)
    assert p.hp == 70


def test_take_damage_clamps_at_zero():
    p = Player(0, 0, 0, hp=20)
    p.take_damage(50)
    assert p.hp == 0


def test_rotate_wraps_into_zero_two_pi():
    p = Player(0, 0, 0.0)
    p.rotate(3 * math.pi)
    assert 0 <= p.angle < 2 * math.pi
    assert math.isclose(p.angle, math.pi, abs_tol=1e-9)


def test_move_offsets_position():
    p = Player(1.0, 2.0, 0)
    p.move(0.5, -1.0)
    assert p.x == 1.5
    assert p.y == 1.0
