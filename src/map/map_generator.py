import hashlib
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class Room:
    x: int
    y: int
    w: int
    h: int

    @property
    def center(self) -> Tuple[int, int]:
        return self.x + self.w // 2, self.y + self.h // 2


def _seed_rng(seed: str) -> random.Random:
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()
    return random.Random(int(digest, 16))


def _make_grid(width: int, height: int) -> List[List[str]]:
    return [["#" for _ in range(width)] for _ in range(height)]


def _room_overlaps(a: Room, b: Room, padding: int = 0) -> bool:
    return not (
        a.x + a.w + padding <= b.x
        or b.x + b.w + padding <= a.x
        or a.y + a.h + padding <= b.y
        or b.y + b.h + padding <= a.y
    )


def _build_rooms(rng: random.Random, width: int, height: int, count: int) -> List[Room]:
    count = max(4, min(8, count))
    rooms: List[Room] = []
    center_w = rng.randint(7, 14)
    center_h = rng.randint(7, 14)
    center_room = Room(
        max(1, width // 2 - center_w // 2),
        max(1, height // 2 - center_h // 2),
        center_w, center_h,
    )
    rooms.append(center_room)

    attempts = 0
    while len(rooms) < count and attempts < 200:
        attempts += 1
        rw = rng.randint(6, 14)
        rh = rng.randint(6, 14)
        candidate = Room(
            rng.randint(1, max(1, width - rw - 1)),
            rng.randint(1, max(1, height - rh - 1)),
            rw, rh,
        )
        if not any(_room_overlaps(candidate, existing) for existing in rooms):
            rooms.append(candidate)
    return rooms


def _carve_room(grid: List[List[str]], room: Room, rng: random.Random):
    cx, cy = room.center
    rx = room.w / 2.0
    ry = room.h / 2.0
    for y in range(room.y, room.y + room.h):
        for x in range(room.x, room.x + room.w):
            dx = (x - cx) / (rx if rx > 0 else 1)
            dy = (y - cy) / (ry if ry > 0 else 1)
            if (dx * dx + dy * dy) * rng.uniform(0.85, 1.15) <= 1.0:
                grid[y][x] = "#" if rng.random() < 0.08 else "."


def _carve_h_corridor(grid, x1, x2, y, rng, width=1):
    for x in range(min(x1, x2), max(x1, x2) + 1):
        for dy in range(width):
            if 0 <= y + dy < len(grid):
                grid[y + dy][x] = "."
        if width > 1 and rng.random() < 0.15:
            dy_obs = rng.randint(0, width - 1)
            if 0 <= y + dy_obs < len(grid):
                grid[y + dy_obs][x] = "#"


def _carve_v_corridor(grid, y1, y2, x, rng, width=1):
    for y in range(min(y1, y2), max(y1, y2) + 1):
        for dx in range(width):
            if 0 <= x + dx < len(grid[0]):
                grid[y][x + dx] = "."
        if width > 1 and rng.random() < 0.15:
            dx_obs = rng.randint(0, width - 1)
            if 0 <= x + dx_obs < len(grid[0]):
                grid[y][x + dx_obs] = "#"


def _connect_rooms(grid: List[List[str]], rooms: List[Room], rng: random.Random):
    for i in range(len(rooms)):
        room_a = rooms[i]
        room_b = rooms[(i + 1) % len(rooms)]
        ax, ay = room_a.center
        bx, by = room_b.center
        width = rng.randint(1, 2)
        if rng.random() < 0.5:
            _carve_h_corridor(grid, ax, bx, ay, rng, width)
            _carve_v_corridor(grid, ay, by, bx, rng, width)
        else:
            _carve_v_corridor(grid, ay, by, ax, rng, width)
            _carve_h_corridor(grid, ax, bx, by, rng, width)

    for _ in range(len(rooms) // 2):
        room_a = rng.choice(rooms)
        room_b = rng.choice(rooms)
        if room_a == room_b:
            continue
        ax, ay = room_a.center
        bx, by = room_b.center
        width = rng.randint(1, 2)
        if rng.random() < 0.5:
            _carve_h_corridor(grid, ax, bx, ay, rng, width)
            _carve_v_corridor(grid, ay, by, bx, rng, width)
        else:
            _carve_v_corridor(grid, ay, by, ax, rng, width)
            _carve_h_corridor(grid, ax, bx, by, rng, width)


def _render_map_js(grid: List[List[str]], player_x: float, player_y: float,
                   sprites: List[dict], filename: str):
    lines = ["var map = \"\";"]
    for row in grid:
        lines.append(f'map += "{"".join(row)}";')

    h, w = len(grid), len(grid[0])
    lines += [
        "",
        "levelfile_gen = {",
        f"  nMapHeight: {h},",
        f"  nMapWidth: {w},",
        "  map: map,",
        f"  fPlayerX: {player_x},",
        f"  fPlayerY: {player_y},",
        "  fPlayerA: 0.0,",
        "  exitsto: \"\",",
        "  color: \"white\",",
        "  background: \"black\",",
        "  sprites: {",
    ]
    for i, sp in enumerate(sprites):
        lines += [
            f"    \"{i}\": {{",
            f"      \"x\": \"{sp['x']:.2f}\",",
            f"      \"y\": \"{sp['y']:.2f}\",",
            f"      \"r\": \"{sp['r']:.2f}\",",
            f"      \"name\": \"{sp['name']}\",",
            f"      \"move\": {'true' if sp['move'] else 'false'}",
            "    },",
        ]
    lines += ["  }", "};"]

    Path(filename).parent.mkdir(parents=True, exist_ok=True)
    Path(filename).write_text("\n".join(lines), encoding="utf-8")


def generate_map(seed: str, width: int = 30, height: int = 30,
                 rooms: int = 5, outpath: str = "assets/generated.map"):
    rng = _seed_rng(seed)
    grid = _make_grid(width, height)
    room_list = _build_rooms(rng, width, height, rooms)
    for room in room_list:
        _carve_room(grid, room, rng)
    _connect_rooms(grid, room_list, rng)

    start_x, start_y = room_list[0].center
    _render_map_js(grid, start_x + 0.5, start_y + 0.5, [], outpath)


def main(argv: Optional[List[str]] = None):
    args = argv if argv is not None else sys.argv[1:]
    seed    = args[0] if args else "default-seed"
    outpath = args[1] if len(args) > 1 else "assets/generated.map"
    rooms   = int(args[2]) if len(args) > 2 else 7
    generate_map(seed, rooms=rooms, outpath=outpath)


if __name__ == "__main__":
    main()
