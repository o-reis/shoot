from engine import world


def _install_map(rows):
    world.MAP = rows
    world.MAP_H = len(rows)
    world.MAP_W = len(rows[0])


def test_is_wall_recognizes_floor_tiles():
    _install_map(["#####", "#. ,#", "#oX.#", "#####"])
    assert world.is_wall(1, 0) is True   # '#'
    assert world.is_wall(1, 1) is False  # '.'
    assert world.is_wall(2, 1) is False  # ' '
    assert world.is_wall(3, 1) is False  # ','
    assert world.is_wall(1, 2) is False  # 'o'
    assert world.is_wall(2, 2) is False  # 'X'


def test_map_tile_out_of_bounds_is_wall():
    _install_map(["...", "...", "..."])
    assert world.map_tile(-1, 0) == "#"
    assert world.map_tile(0, -1) == "#"
    assert world.map_tile(99, 0) == "#"
    assert world.map_tile(0, 99) == "#"


def test_seeded_spawn_is_deterministic_and_walkable():
    _install_map([
        "########",
        "#......#",
        "#......#",
        "#......#",
        "########",
    ])
    a = world.random_spawn(seed="s", player_id="p1")
    b = world.random_spawn(seed="s", player_id="p1")
    assert a == b
    assert not world.is_wall(a[0], a[1])


def test_different_player_ids_get_different_spawns():
    _install_map([
        "########",
        "#......#",
        "#......#",
        "#......#",
        "########",
    ])
    a = world.random_spawn(seed="s", player_id="p1")
    b = world.random_spawn(seed="s", player_id="p2")
    assert a != b
