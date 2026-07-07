import math
import os
import random
import re
import time

from engine.assets import ASSETS_DIR

PI2 = math.pi * 2.0
PI_15 = math.pi * 1.5

MAP = [
    "################",
    "#..............#",
    "#..............#",
    "#..............#",
    "################",
]
MAP_W = len(MAP[0])
MAP_H = len(MAP)

CURRENT_LEVEL = "generated.map"
NEXT_LEVEL = "generated.map"
PLAYER_START = (2.5, 2.5, 0.0)

SPRITES = []
ACTIVE_TRACERS = []  # each item: [xi, yi, xf, yf, expire_timestamp]


def _parse_level_file(path):
    with open(path, encoding='utf-8') as f:
        src = f.read()
    src = re.sub(r"//.*", "", src)

    rows = re.findall(r"map\s*\+=\s*\"([^\"]*)\"\s*;", src)
    width_match  = re.search(r"\bnMapWidth\s*:\s*(\d+)", src)
    height_match = re.search(r"\bnMapHeight\s*:\s*(\d+)", src)
    px_match     = re.search(r"\bfPlayerX\s*:\s*(-?\d+(?:\.\d+)?)", src)
    py_match     = re.search(r"\bfPlayerY\s*:\s*(-?\d+(?:\.\d+)?)", src)
    pa_match     = re.search(r"\bfPlayerA\s*:\s*(-?\d+(?:\.\d+)?)", src)
    exit_match   = re.search(r"\bexitsto\s*:\s*\"([^\"]+)\"", src)

    if not rows:
        raise ValueError(f"No map rows found in {path}")

    level_w = int(width_match.group(1))  if width_match  else len(rows[0])
    level_h = int(height_match.group(1)) if height_match else len(rows)

    map_rows = [(r + ("#" * max(0, level_w - len(r))))[:level_w] for r in rows[:level_h]]
    while len(map_rows) < level_h:
        map_rows.append("#" * level_w)

    px      = float(px_match.group(1))   if px_match    else 2.5
    py      = float(py_match.group(1))   if py_match    else 2.5
    pa      = float(pa_match.group(1))   if pa_match    else 0.0
    exit_to = exit_match.group(1)        if exit_match  else CURRENT_LEVEL

    sprites = _parse_sprites(src)
    return map_rows, px, py, pa, exit_to, sprites


def _parse_sprites(src):
    sprites = []
    sprite_blocks = re.findall(r"\"(\w+)\"\s*:\s*\{([^\}]*)\}", src)
    for _, block in sprite_blocks:
        x_match    = re.search(r"\"x\"\s*:\s*\"([^\"]*)\"", block)
        y_match    = re.search(r"\"y\"\s*:\s*\"([^\"]*)\"", block)
        r_match    = re.search(r"\"r\"\s*:\s*\"([^\"]*)\"", block)
        name_match = re.search(r"\"name\"\s*:\s*\"([^\"]*)\"", block)
        move_match = re.search(r"\"move\"\s*:\s*(true|false)", block)
        if x_match and y_match and name_match:
            sprites.append({
                "x": float(x_match.group(1)),
                "y": float(y_match.group(1)),
                "r": float(r_match.group(1)) if r_match else 0.0,
                "name": name_match.group(1),
                "move": move_match.group(1) == "true" if move_match else False,
                "z": 0.0,
                "stuckcounter": 0,
                "speed": 0.03,
            })
    return sprites


def load_level(level_file):
    global MAP, MAP_W, MAP_H, CURRENT_LEVEL, NEXT_LEVEL, PLAYER_START, SPRITES

    path = level_file if os.path.isabs(level_file) else os.path.join(ASSETS_DIR, level_file)
    map_rows, px, py, pa, exit_to, level_sprites = _parse_level_file(path)

    MAP = map_rows
    MAP_W = len(MAP[0])
    MAP_H = len(MAP)
    CURRENT_LEVEL = level_file
    NEXT_LEVEL = exit_to
    PLAYER_START = (px, py, pa)
    SPRITES = level_sprites if level_sprites else []


def map_tile(x, y):
    ix, iy = int(x), int(y)
    if ix < 0 or iy < 0 or iy >= MAP_H or ix >= MAP_W:
        return '#'
    return MAP[iy][ix]


def is_wall(x, y):
    return map_tile(x, y) not in ('.', ' ', 'o', ',', 'X')


def _is_open_spawn(x, y):
    return not any(is_wall(x + dx, y + dy) for dx, dy in ((0,0),(1,0),(-1,0),(0,1),(0,-1)))

def _random_floor_pos(rng=None):
    _rng = rng or random
    while True:
        x = _rng.uniform(1, MAP_W - 1)
        y = _rng.uniform(1, MAP_H - 1)
        if _is_open_spawn(x, y):
            return x, y


def random_spawn(seed: str = None, player_id: str = None):
    if seed and player_id:
        import hashlib
        digest = hashlib.sha1(f"{seed}:spawn:{player_id}".encode()).hexdigest()
        rng = random.Random(int(digest, 16))
        return _random_floor_pos(rng)
    return _random_floor_pos()


def update_sprite_distances(px, py):
    for sp in SPRITES:
        dx, dy = sp["x"] - px, sp["y"] - py
        sp["z"] = math.sqrt(dx * dx + dy * dy)
    SPRITES.sort(key=lambda s: -s["z"])


def move_sprites():
    for sp in SPRITES:
        if not sp["move"]:
            continue
        speed = sp["speed"] or 0.03
        sp["x"] += math.cos(sp["r"]) * speed
        sp["y"] += math.sin(sp["r"]) * speed

        cx  = sp["x"] + 0.125
        cy  = sp["y"] - 0.65
        cx2 = sp["x"] - 0.65
        cy2 = sp["y"] + 0.425

        if map_tile(cx, cy) != '.' or map_tile(cx2, cy2) != '.':
            sp["stuckcounter"] += 1
            sp["x"] -= math.cos(sp["r"]) * speed * 2
            sp["y"] -= math.sin(sp["r"]) * speed * 2
            sp["r"] = (sp["r"] + PI_15) % PI2
            if sp["stuckcounter"] > 10:
                sp["stuckcounter"] = 0
                sp["r"] = 0.5
                sp["x"] -= math.cos(sp["r"]) * 0.5
                sp["y"] -= math.sin(sp["r"]) * 0.5


def update_network_player(pid, px, py, pa, label=None, full_pid=None):
    for sp in SPRITES:
        if sp.get("pid") == pid:
            sp["x"] = px
            sp["y"] = py
            sp["r"] = pa
            if label:
                sp["label"] = label
            if full_pid:
                sp["full_pid"] = full_pid
            return

    SPRITES.append({
        "pid": pid,
        "full_pid": full_pid,
        "label": label or str(pid)[:4],
        "name": "O",
        "x": px,
        "y": py,
        "r": pa,
        "move": False,
        "z": 999.0,
        "stuckcounter": 0,
        "speed": 0.0,
    })


def remove_network_player(pid):
    global SPRITES
    SPRITES = [sp for sp in SPRITES if sp.get("pid") != pid]


def add_tracer(xi, yi, xf, yf, duration=0.2):
    ACTIVE_TRACERS.append([xi, yi, xf, yf, time.time() + duration])


def clear_old_tracers():
    now = time.time()
    ACTIVE_TRACERS[:] = [t for t in ACTIVE_TRACERS if t[4] > now]


try:
    load_level(CURRENT_LEVEL)
except Exception:
    pass
