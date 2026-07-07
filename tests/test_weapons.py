from engine.weapons import WEAPONS, Weapon


def test_five_weapons_in_expected_order():
    assert [w.name for w in WEAPONS] == ["Pistol", "Shotgun", "SMG", "Sniper", "Knife"]


def test_every_weapon_has_positive_stats():
    for w in WEAPONS:
        assert w.damage > 0
        assert w.reload > 0
        assert w.range > 0
        assert w.spread >= 1


def test_weapon_is_dataclass_with_defaults():
    w = Weapon("Test", 10, 1.0, 5.0)
    assert w.spread == 1
