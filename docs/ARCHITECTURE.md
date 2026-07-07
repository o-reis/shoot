# Architecture

This document maps the source tree, the threads that run at play time, and how a session flows from the menu into a live match.

## Module map

```
src/
  main.py            Entry point: player ID, menu loop, dispatch to lobby flows and the game
  engine/            The game itself
    game_loop.py     Main loop: input, netcode wiring, combat, victory/spectate/rematch state
    renderer.py      Curses raycaster: walls, sprites, tracers, minimap, HUD
    world.py         Map state, level parsing, collision, spawns, network-player sprites, tracers
    player.py        Player data: position, angle, HP, look/jump timers
    weapons.py       Weapon dataclass and the weapon list
    safe_zone.py     Shrinking battle-royale zone with phased damage
    assets.py        Texture and sprite loading from .tex files, ASCII shading
  map/
    map_generator.py Seeded procedural map generator (rooms and corridors)
  network/
    lobby.py         Host and client lobby flows (host_match, join_public, join_private, rematch)
    matchmaking.py   Thin async wrappers over the DHT
    matchmaking_helpers.py  Local IP detection, DHT registration, host keep-alive
    grpc_services.py gRPC servicers: LobbyService and PeerGameService
    lan_discovery.py UDP broadcast host discovery
    udp_sync.py      Raw UDP position/attack/death sync
    net_logger.py    Network event logging to net.log
    generated/       protoc-generated protobuf and gRPC stubs (do not edit by hand)
  ui/
    screens.py       Curses menus, prompts, lobby-wait and scan screens
proto/
  game.proto         Source of truth for the generated protobuf code
```

## Thread model

The game runs several threads at once. The main thread owns the terminal; the rest handle networking so the render loop never blocks on I/O.

- **Main thread** runs `game_loop.game()`: the curses input and render loop.
- **gRPC worker thread** (`_grpc_worker`, started in `game_loop.py`) runs an asyncio event loop that hosts the `PeerGameService` server and the outgoing peer streams. It bridges two thread-safe queues: an incoming queue that the main loop drains, and an outgoing queue the main loop fills.
- **UDP broadcaster and receiver threads** (`UDPStateBroadcaster`, `UDPStateReceiver` in `udp_sync.py`) send and receive the high-frequency state, attack, and death packets on background daemon threads.
- **Windows mouse-wheel hook thread** (`_install_wheel_hook` in `game_loop.py`, Windows only) runs a low-level `SetWindowsHookExW` message pump so the scroll wheel can switch weapons.

Cross-thread communication uses queues (gRPC events) and the `UDP*` callback handlers (UDP packets). Shared world state lives in module globals in `world.py`.

## Runtime flow

1. `main.py` loads or creates the persistent player ID, prompts for a name, and shows the menu.
2. A menu choice dispatches to a flow in `lobby.py` (host, join public, join private) run under `asyncio.run`, or to Play Solo which skips networking.
3. The lobby flow brings up the DHT node, LAN broadcast, and the gRPC `LobbyService`. Clients stream lobby events until the host triggers game start.
4. Game start delivers the full peer list plus the map seed. `run_game` regenerates the map deterministically from that seed and calls `game_loop.game()`.
5. In the game loop every peer forms a mesh: a gRPC bidirectional stream for reliable events plus raw UDP for state, all on the P2P port.
6. On victory or death the loop enters a victory or spectate state; the host can offer a rematch, which loops back to step 4 with a new seed.

See [NETWORKING.md](NETWORKING.md) for the wire protocols and [ENGINE.md](ENGINE.md) for the render and gameplay side.
