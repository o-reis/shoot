from engine.player import Player
from engine.safe_zone import (
    SafeZone,
    DPS_LOW, DPS_MID, DPS_HIGH, DPS_MAX,
    LOW_PHASE_SHRINKS, MID_PHASE_SHRINKS, HIGH_PHASE_SHRINKS,
    DAMAGE_INTERVAL_SECONDS,
)


def test_inactive_zone_is_always_safe():
    z = SafeZone(0, 0, 10, 10)
    assert z.is_safe(-100, -100) is True


def test_active_zone_bounds():
    z = SafeZone(0, 0, 10, 10)
    z.active = True
    assert z.is_safe(5, 5) is True
    assert z.is_safe(11, 5) is False


def test_dps_scales_with_shrink_count():
    z = SafeZone(0, 0, 40, 40)
    assert z.dps() == DPS_LOW
    z.shrink_count = LOW_PHASE_SHRINKS
    assert z.dps() == DPS_MID
    z.shrink_count = MID_PHASE_SHRINKS
    assert z.dps() == DPS_HIGH
    z.shrink_count = HIGH_PHASE_SHRINKS
    assert z.dps() == DPS_MAX


def test_shrink_activates_and_reduces_size():
    z = SafeZone(0, 0, 10, 10)
    z.shrink(2.0)
    assert z.active is True
    assert z.width == 8
    assert z.height == 8
    assert z.shrink_count == 1


def test_damage_applied_only_when_outside_and_interval_passed():
    z = SafeZone(0, 0, 10, 10)
    z.active = True
    z.last_damage_time = 0.0  # force interval elapsed
    p = Player(100, 100, 0, hp=100)
    z.update_damage(p)
    assert p.hp == 100 - DPS_LOW


def test_no_damage_inside_zone():
    z = SafeZone(0, 0, 10, 10)
    z.active = True
    z.last_damage_time = 0.0
    p = Player(5, 5, 0, hp=100)
    z.update_damage(p)
    assert p.hp == 100
