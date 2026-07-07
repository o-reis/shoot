# Shoot

A terminal-based peer-to-peer battle-royale first-person shooter, written in Python. The world is rendered as an ASCII raycaster inside a `curses` terminal, and players connect to each other over a custom peer-to-peer networking stack: the `kademlia-dynamic` package (a Kademlia distributed hash table) for discovery, gRPC for lobby and reliable in-game events, and raw UDP for high-frequency position and combat state.

Built for a university systems-networking course.

## Credits

Made by:
Bernardo Reis
Fernando Santos
Nuno Costa

The 3D engine, the raycaster, and the ASCII texture/sprite assets are adapted from the original JavaScript engine in [`legacy/`](legacy/) (`gameengine.js`, `index.html`). That folder is the historical source the Python port grew out of.

## Requirements

- Python 3
- Dependencies in `requirements.txt`:

```bash
pip install -r requirements.txt
```

On Windows the standard-library `curses` module is not bundled; install `windows-curses` if it is missing.

## Running

```bash
python src/main.py
```

On first run the game generates a persistent numeric player ID at `~/.shoot_id` and stores its generated map at `~/.shoot/generated.map`.

You are prompted for a player name, then shown the main menu:

| Menu item                | What it does                                  |
| ------------------------ | --------------------------------------------- |
| Host Match               | Start a public lobby others can find and join |
| Join Match (Public)      | Discover and join a public lobby              |
| Join Match (Private Key) | Join a specific lobby by key                  |
| Play Solo                | Launch the game with no networking            |
| Exit                     | Quit                                          |

When enough players are in a lobby the host starts the match. Every player then forms a full mesh with every other player for the duration of the game.

## Controls

Movement and look use both WASD/arrow keys and (on Windows) low-level key polling, so keys can be held simultaneously.

| Input                   | Action                                            |
| ----------------------- | ------------------------------------------------- |
| W / Up                  | Move forward                                      |
| S / Down                | Move back                                         |
| A / Left                | Turn left                                         |
| D / Right               | Turn right                                        |
| Shift                   | Sprint                                            |
| Q / E                   | Look down / up                                    |
| Enter                   | Shoot                                             |
| 1 - 5                   | Select weapon by slot                             |
| Mouse wheel / Shift tap | Cycle weapon                                      |
| M                       | Toggle full-screen map                            |
| Esc                     | Leave the match (or exit spectate/victory screen) |

## Ports

| Port  | Transport  | Use                                   | Defined in                            |
| ----- | ---------- | ------------------------------------- | ------------------------------------- |
| 8468  | UDP        | Kademlia DHT discovery                | `src/network/lobby.py`                |
| 50051 | gRPC / TCP | Lobby service                         | `src/network/lobby.py`                |
| 50152 | gRPC + UDP | In-game peer-to-peer events and state | `src/main.py`, `src/network/lobby.py` |
| 8471  | UDP        | LAN broadcast host discovery          | `src/network/lan_discovery.py`        |

## Packaged build

`shoot.spec` is a PyInstaller spec that bundles `src/main.py`, the `assets/`, and the generated protobuf code into a one-file console executable named `shoot`:

```bash
pyinstaller shoot.spec
```

## Map generator

Maps are generated deterministically from a seed. The generator can also be run directly:

```bash
python src/map/map_generator.py <seed> [outpath] [rooms]
```

Defaults: seed `default-seed`, output `assets/generated.map`, 7 rooms.

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - module map, threads, and runtime flow
- [docs/NETWORKING.md](docs/NETWORKING.md) - the three transport layers and message formats
- [docs/ENGINE.md](docs/ENGINE.md) - raycaster, world, map generation, and gameplay

## Tests

Unit tests for the pure-logic modules live in [`tests/`](tests/):

```bash
pip install pytest
python -m pytest tests/ -q
```
