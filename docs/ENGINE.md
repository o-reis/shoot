# Engine

The game side: how the world is drawn, how maps are made, and the gameplay rules. The raycaster and ASCII assets are adapted from the original JavaScript engine in [`legacy/`](../legacy/).

## Rendering (`renderer.py`)

A raycaster drawn into a `curses` window:

- **Walls** are cast with DDA (digital differential analysis), one ray per screen column, shaded by distance.
- **Sprites** (other players and level objects) are billboarded and depth-sorted against the wall depth buffer so nearer walls occlude them.
- **Tracers** draw the short-lived lines of recent shots.
- **Minimap** and **HUD** overlay HP, the current weapon, and the kill feed.

## World and maps (`world.py`)

`world.py` holds the live map and sprite state in module globals and provides the collision and spawn helpers.

- **Level format**: maps are `.map` files parsed by `_parse_level_file`. A tile is walkable when it is one of `.`, space, `o`, `,`, or `X`; anything else is a wall.
- **Collision**: `is_wall(x, y)` and `map_tile(x, y)` test positions against the tile grid; out-of-bounds counts as wall.
- **Spawns**: `random_spawn` can derive a deterministic floor position from a seed and player id (SHA-1 of `seed:spawn:player_id`), so every client agrees on where each player starts.
- **Network players**: `update_network_player` and `remove_network_player` keep peer sprites in sync with incoming state.

## Map generation (`map/map_generator.py`)

A deterministic generator: from a seed it lays out rooms and connects them with corridors, then writes the result in the `.map` format. The same seed always produces the same map, which is how every peer in a match renders an identical world from the seed the host sends at game start.

Run it directly:

```bash
python src/map/map_generator.py <seed> [outpath] [rooms]
```

Defaults: seed `default-seed`, output `assets/generated.map`, 7 rooms.

## Gameplay

### Player (`player.py`)

Holds position, view angle, HP, and the look and jump timers the renderer reads for view offset.

### Weapons (`weapons.py`)

A `Weapon` has a name, damage, reload time, range, and spread. The five weapons, in slot order:

| Slot | Name    | Damage | Reload (s) | Range | Spread |
| ---- | ------- | ------ | ---------- | ----- | ------ |
| 1    | Pistol  | 15     | 0.4        | 12.0  | 1      |
| 2    | Shotgun | 40     | 1.2        | 6.0   | 3      |
| 3    | SMG     | 4      | 0.2        | 10.0  | 1      |
| 4    | Sniper  | 80     | 3.0        | 50.0  | 1      |
| 5    | Knife   | 25     | 0.8        | 2.0   | 1      |

Shooting is hitscan: the game finds the nearest enemy sprite within the weapon's range and inside the crosshair cone, checks line of sight, and applies damage. A shot is gated by the current weapon's reload time.

### Safe zone (`safe_zone.py`)

A rectangular zone that shrinks in steps. Damage is applied to any player outside the zone once every `2.0` seconds, and the damage per tick rises as the zone shrinks:

| Shrink count | Damage per tick |
| ------------ | --------------- |
| below 8      | 1               |
| 8 to 14      | 2               |
| 15 to 19     | 5               |
| 20 or more   | 10              |

### Anti-cheat

Combat and movement received from peers are validated on the receiving client. See the anti-cheat section in [NETWORKING.md](NETWORKING.md).

## Assets (`assets.py`)

Textures and sprites load from `.tex` files and map to ASCII shading. `assets.py` resolves the assets directory in both a normal run and a PyInstaller-packaged build. The texture and sprite artwork originates from the `legacy/` engine.
