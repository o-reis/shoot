# Networking

The stack has three transport layers, each on its own port and its own wire format. A fourth mechanism, LAN broadcast, helps peers on the same network find a host quickly.

## 1. Discovery: Kademlia DHT over UDP (port 8468)

Discovery runs on the `kademlia-dynamic` package (a from-scratch Kademlia distributed hash table over asyncio UDP), imported as `from kademlia_dynamic import KademliaServer` in `matchmaking.py` and `matchmaking_helpers.py`. Peers use it to publish and look up lobby and player records, keyed by `(player_id -> ip:port)`.

The DHT does **not** use protobuf on the wire. It serializes its own message dicts with one of two codecs (a JSON codec and a hand-rolled bencode codec). The Kademlia message types in `proto/game.proto` (`FindNodeRequest`, `StoreRequest`, and so on) describe the design but are not what the running DHT sends.

Node identity here is a 160-bit SHA-1 node ID. This is a separate identity space from the numeric player IDs used everywhere else (see below).

## 2. Lobby: gRPC over TCP (port 50051)

`grpc_services.py` defines `LobbyService`. Clients call `JoinLobby` with their `PlayerInfo` and receive a **server stream** of `LobbyEvent` messages:

- `player_joined` - a `PlayerInfo` for a peer that joined
- `player_left` - the id of a peer that left
- `game_start` - a `GameStart` carrying every peer's `PlayerInfo` plus the map seed

The host signals game start with `trigger_game_start`, which fans a `game_start` event out to all connected clients. Receiving it is the signal for every client to leave the lobby and form the game mesh.

`LobbyService` also declares `LeaveLobby`, which returns a single `ServerReply`. It is part of the service contract.

## 3. Gameplay: gRPC bidirectional stream plus raw UDP (port 50152)

In a live match both channels run at once on the same port.

### Reliable events: gRPC `PeerGameService.P2PStream`

A bidirectional stream of `GameEvent` messages. Each `GameEvent` is a oneof; the fields the game actually sends and handles are:

- `bullet_fired` - a `Bullet` (attacker id and the tracer's start and end points)
- `player_death` - a `PlayerDeath` (dead player id and killer id)
- `disconnect_event` - a `PlayerDisconnect` (player id leaving)
- `game_ended` - a `GameEnd` (winner id)
- `host_rematch` - a `HostRematch` (rematch availability)

The proto also defines `state_update`, `received_attack`, and `zone_update` oneof fields; live position and attack traffic goes over UDP instead, described next.

### High-frequency state: raw UDP

`udp_sync.py` sends struct-packed binary packets for the traffic that happens many times per second. Every packet starts with a one-byte type tag, and player ids are carried as a fixed 32-byte field (right-padded with `\x00`). All fields are big-endian (`!`).

| Packet | Type tag | Layout (`struct` format)                        | Min length |
| ------ | -------- | ----------------------------------------------- | ---------- |
| state  | 0        | `!B 32s f f f I` (id, x, y, angle, hp)          | 49 bytes   |
| attack | 1        | `!B 32s 32s I` (attacker id, target id, damage) | 69 bytes   |
| dead   | 2        | `!B 32s` (id)                                   | 33 bytes   |

The receiver can be given an allow-list of peer IP addresses; packets from other addresses are dropped.

### Anti-cheat checks (client-side)

The receiving client validates incoming traffic in `game_loop.py`:

- A position update implying a speed above `15.0` units per second is ignored.
- An attack with damage above `80` is ignored.
- An attack from an attacker whose last known position is more than `55.0` units away is ignored.

## LAN discovery: UDP broadcast (port 8471)

`lan_discovery.py` broadcasts a beacon whose payload begins with the header `b"SHOOT_NODE:"` and carries the host's DHT port. `LANScanner` listens for these beacons so peers on the same network can find a host without going through the DHT.

## Two identity spaces

Keep these distinct when reading the code:

- **Numeric player IDs** identify players in the game and in UDP, gRPC, and lobby traffic. They are generated in `main.py` and stored at `~/.shoot_id`.
- **160-bit SHA-1 node IDs** identify nodes inside the Kademlia DHT only.
