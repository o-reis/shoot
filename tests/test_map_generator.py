from map.map_generator import Room, generate_map, _seed_rng, _room_overlaps, _build_rooms


def test_room_center():
    r = Room(2, 4, 6, 8)
    assert r.center == (5, 8)


def test_room_overlap_detection():
    a = Room(0, 0, 5, 5)
    assert _room_overlaps(a, Room(3, 3, 5, 5))
    assert not _room_overlaps(a, Room(10, 10, 5, 5))


def test_seed_rng_is_deterministic():
    a = _seed_rng("abc")
    b = _seed_rng("abc")
    assert a.random() == b.random()


def test_different_seeds_diverge():
    a = _seed_rng("abc").random()
    b = _seed_rng("xyz").random()
    assert a != b


def test_build_rooms_count_clamped():
    rng = _seed_rng("seed")
    rooms = _build_rooms(rng, 30, 30, 100)
    assert 4 <= len(rooms) <= 8


def test_generate_map_deterministic(tmp_path):
    out_a = tmp_path / "a.map"
    out_b = tmp_path / "b.map"
    generate_map("fixed-seed", outpath=str(out_a))
    generate_map("fixed-seed", outpath=str(out_b))
    assert out_a.read_text() == out_b.read_text()


def test_generate_map_seed_changes_output(tmp_path):
    out_a = tmp_path / "a.map"
    out_b = tmp_path / "b.map"
    generate_map("seed-one", outpath=str(out_a))
    generate_map("seed-two", outpath=str(out_b))
    assert out_a.read_text() != out_b.read_text()
