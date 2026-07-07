import asyncio
import uuid

import grpc
import game_pb2
import game_pb2_grpc

from src.network.matchmaking import init_node, create_lobby, list_lobbies, join_private_game, join_player
from src.network.matchmaking_helpers import get_local_ip, keep_alive
from src.network.lan_discovery import broadcast_node
from src.network.grpc_services import LobbyService
from src.ui.screens import show_status, show_lobby_wait, pick_from_list, prompt_text, scan_with_spinner
import src.network.net_logger as net_logger

DHT_PORT  = 8468
GRPC_PORT = 50051
P2P_PORT  = 50152


async def host_match(stdscr, player_id: str, player_name: str):
    visibility = pick_from_list(stdscr, " H O S T   L O B B Y", ["Public", "Private"],
                                hint="UP/DOWN   ENTER to select   ESC to cancel")
    if visibility == -1:
        return None, None, None, None
    is_private = visibility == 1

    ip   = get_local_ip()
    port = DHT_PORT

    if is_private:
        lobby_name = prompt_text(stdscr, " P R I V A T E   L O B B Y", "Enter lobby key:", max_len=24)
        if not lobby_name:
            return None, None, None, None
    else:
        lobby_name = player_name + "'s lobby"

    show_status(stdscr, " H O S T I N G", [
        f"Player : {player_name}",
        f"Lobby  : {lobby_name}",
        f"Type   : {'Private' if is_private else 'Public'}",
        f"IP     : {ip}:{port}",
        "",
        "Starting DHT node...",
    ])

    node = await init_node(port, bootstrap_nodes=None)
    await join_player(node, player_id, ip, port)
    asyncio.create_task(broadcast_node(port))
    await create_lobby(node, lobby_name, ip, port, private=is_private)

    lobby_service = LobbyService()
    lobby_service.host_info = game_pb2.PlayerInfo(
        player_id=player_id,
        player_name=player_name,
        ip_address=ip,
        port=P2P_PORT,
    )
    server = grpc.aio.server()
    game_pb2_grpc.add_LobbyServiceServicer_to_server(lobby_service, server)
    server.add_insecure_port(f'[::]:{GRPC_PORT}')
    await server.start()

    lobby_info   = {"name": lobby_name, "ip": ip, "port": port}
    keep_alive_t = asyncio.create_task(keep_alive(node, ip, lobby_info)) \
                   if not is_private else None

    static_lines = [f"Lobby  : {lobby_name}", f"IP     : {ip}:{port}"]
    if is_private:
        static_lines.append(f"Key    : {lobby_name}")

    stdscr.nodelay(True)
    while True:
        players_in = [f"{player_name} (host)"] + [p.player_name for p in lobby_service.players_in_lobby]
        show_lobby_wait(stdscr, " L O B B Y   R E A D Y", static_lines, players_in)
        await asyncio.sleep(0.5)
        key = stdscr.getch()
        if key in (10, 13):
            break
        if key == 27:
            if keep_alive_t:
                keep_alive_t.cancel()
            node.stop()
            await server.stop(grace=None)
            return None, None, None, None

    stdscr.nodelay(False)
    if keep_alive_t:
        keep_alive_t.cancel()

    map_seed = uuid.uuid4().hex
    peer_snapshot = list(lobby_service.players_in_lobby)
    await lobby_service.trigger_game_start(map_seed=map_seed)
    await server.stop(grace=None)

    return node, peer_snapshot, map_seed, ip


async def _connect_to_lobby(stdscr, player_id: int, host_grpc_address: str, player_name: str, ip: str, host_ip: str = None):
    my_info      = game_pb2.PlayerInfo(
        player_id=player_id,
        player_name=player_name,
        ip_address=ip,
        port=P2P_PORT,
    )
    peer_list    = []
    map_seed     = ""
    players_seen = [player_name]
    id_to_display = {}

    async with grpc.aio.insecure_channel(host_grpc_address) as channel:
        stub = game_pb2_grpc.LobbyServiceStub(channel)
        net_logger.grpc_sent(host_grpc_address, "JoinLobby",
                             f"player_id={player_id} name={my_info.player_name}")
        try:
            stream = stub.JoinLobby(my_info)
            show_lobby_wait(stdscr, " W A I T I N G   F O R   H O S T", [
                "Connected. Waiting for host to start...",
            ], players_seen, hint="Waiting for host...")
            host_player_id = [None]
            async for event in stream:
                if event.HasField('player_joined'):
                    p = event.player_joined
                    net_logger.grpc_recv(host_grpc_address, "JoinLobby/player_joined",
                                         f"name={p.player_name}")
                    if host_player_id[0] is None:
                        host_player_id[0] = p.player_id
                        display = f"{p.player_name} (host)"
                    else:
                        display = p.player_name
                    id_to_display[str(p.player_id)] = display
                    players_seen.append(display)
                    show_lobby_wait(stdscr, " W A I T I N G   F O R   H O S T", [
                        "Connected. Waiting for host to start...",
                    ], players_seen, hint="Waiting for host...")
                elif event.HasField('player_left'):
                    pid = event.player_left
                    net_logger.grpc_recv(host_grpc_address, "JoinLobby/player_left", f"player_id={pid}")
                    display = id_to_display.pop(pid, None)
                    if display and display in players_seen:
                        players_seen.remove(display)
                    show_lobby_wait(stdscr, " W A I T I N G   F O R   H O S T", [
                        "Connected. Waiting for host to start...",
                    ], players_seen, hint="Waiting for host...")
                elif event.HasField('game_start'):
                    net_logger.grpc_recv(host_grpc_address, "JoinLobby/game_start",
                                         f"peers={len(event.game_start.all_peers)} seed={event.game_start.map_name[:8]}")
                    peers = list(event.game_start.all_peers)
                    if host_ip:
                        patched = []
                        for p in peers:
                            if not p.ip_address:
                                p2 = game_pb2.PlayerInfo()
                                p2.CopyFrom(p)
                                p2.ip_address = host_ip
                                patched.append(p2)
                            else:
                                patched.append(p)
                        peers = patched
                    peer_list = [p for p in peers if p.player_id != player_id]
                    map_seed  = event.game_start.map_name
                    break
        except grpc.aio.AioRpcError as e:
            if e.code() in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.CANCELLED):
                show_status(stdscr, " E R R O R", ["Host disconnected."])
            else:
                show_status(stdscr, " E R R O R", [f"Lost connection: {e.details()}"])
            await asyncio.sleep(2)
            return None, None

    return peer_list, map_seed


async def join_public(stdscr, player_id: str, player_name: str):
    discovered_hosts = await scan_with_spinner(
        stdscr, " J O I N   P U B L I C", f"Player: {player_name}   Scanning LAN for hosts...")
    if discovered_hosts is None:
        return None, None, None, None
    if not discovered_hosts:
        show_status(stdscr, " J O I N   P U B L I C", ["No hosts found on LAN."])
        await asyncio.sleep(2)
        return None, None, None, None

    first_host_ip, first_host_dht_port = discovered_hosts[0]
    ip = get_local_ip(target=first_host_ip)

    show_status(stdscr, " J O I N   P U B L I C", [
        f"Found {len(discovered_hosts)} host(s) on LAN",
        "",
        "Connecting to DHT...",
    ])

    node = await init_node(0, [(first_host_ip, first_host_dht_port)])
    await join_player(node, player_id, ip, node.own_peer.port)

    seed_ips = [ip for ip, _ in discovered_hosts]
    available_lobbies = await list_lobbies(node, seed_ips)
    if not available_lobbies:
        show_status(stdscr, " J O I N   P U B L I C", ["No public lobbies found."])
        await asyncio.sleep(2)
        return None, None, None, None

    lobby_labels = [f"{l['name']}  ({l['_host_ip']})" for l in available_lobbies]
    chosen_idx = pick_from_list(stdscr, " A V A I L A B L E   L O B B I E S", lobby_labels,
                                hint="UP/DOWN   ENTER to join   ESC to cancel")
    if chosen_idx == -1:
        return None, None, None, None

    chosen_lobby = available_lobbies[chosen_idx]
    chosen_host_ip = chosen_lobby["_host_ip"]

    show_status(stdscr, " J O I N E D", [
        f"Lobby  : {chosen_lobby['name']}",
        f"Host   : {chosen_host_ip}:{chosen_lobby['port']}",
        "",
        "Connecting...",
    ])

    peer_list, map_seed = await _connect_to_lobby(
        stdscr, player_id, f"{chosen_host_ip}:{chosen_lobby.get('grpc_port', GRPC_PORT)}",
        player_name, ip, host_ip=chosen_host_ip)
    if peer_list is None:
        return None, None, None, None
    return node, peer_list, map_seed, chosen_host_ip


async def join_private(stdscr, player_id: str, player_name: str):
    stdscr.nodelay(False)
    key = prompt_text(stdscr, " J O I N   P R I V A T E", "Enter lobby key:")
    if not key:
        return None, None, None, None

    peers_found = await scan_with_spinner(
        stdscr, " J O I N   P R I V A T E", f"Player: {player_name}   Scanning LAN for hosts...")
    if peers_found is None:
        return None, None, None, None
    if not peers_found:
        show_status(stdscr, " J O I N   P R I V A T E", ["No hosts found on LAN."])
        await asyncio.sleep(2)
        return None, None, None, None

    host_ip, host_dht_port = peers_found[0]
    ip = get_local_ip(target=host_ip)

    node = await init_node(0, [(host_ip, host_dht_port)])
    await join_player(node, player_id, ip, node.own_peer.port)

    lobby = await join_private_game(node, key)
    if not lobby:
        show_status(stdscr, " J O I N   P R I V A T E", [f"Lobby '{key}' not found."])
        await asyncio.sleep(2)
        return None, None, None, None

    show_status(stdscr, " J O I N E D", [
        f"Lobby  : {lobby['name']}",
        f"Host   : {lobby['ip']}:{lobby['port']}",
        "",
        "Connecting...",
    ])

    peer_list, map_seed = await _connect_to_lobby(
        stdscr, player_id, f"{host_ip}:{lobby.get('grpc_port', GRPC_PORT)}", player_name, ip, host_ip=host_ip)
    if peer_list is None:
        return None, None, None, None
    return node, peer_list, map_seed, host_ip


REMATCH_WAIT_FOR_PEERS_SECONDS = 15


async def host_rematch(stdscr, player_id: str, player_name: str, expected_peer_count: int):
    ip = get_local_ip()

    lobby_service = LobbyService()
    lobby_service.host_info = game_pb2.PlayerInfo(
        player_id=player_id,
        player_name=player_name,
        ip_address=ip,
        port=P2P_PORT,
    )
    for attempt in range(10):
        try:
            server = grpc.aio.server()
            game_pb2_grpc.add_LobbyServiceServicer_to_server(lobby_service, server)
            server.add_insecure_port(f'[::]:{GRPC_PORT}')
            await server.start()
            break
        except OSError:
            await asyncio.sleep(0.5)
    else:
        return None, None, None

    map_seed = uuid.uuid4().hex
    deadline = asyncio.get_event_loop().time() + REMATCH_WAIT_FOR_PEERS_SECONDS

    stdscr.nodelay(True)
    while True:
        joined = len(lobby_service.players_in_lobby)
        show_status(stdscr, " R E M A T C H", [
            f"Waiting for players... ({joined}/{expected_peer_count})",
            "Starting automatically when all join or after 15s",
        ])
        await asyncio.sleep(0.5)
        if joined >= expected_peer_count:
            break
        if asyncio.get_event_loop().time() >= deadline:
            break

    stdscr.nodelay(False)
    peer_snapshot = list(lobby_service.players_in_lobby)
    if not peer_snapshot:
        await server.stop(grace=None)
        return None, None, None
    await lobby_service.trigger_game_start(map_seed=map_seed)
    await server.stop(grace=None)

    return None, peer_snapshot, map_seed


async def join_rematch(stdscr, player_id: str, player_name: str, host_ip: str):
    ip = get_local_ip(target=host_ip)
    address = f"{host_ip}:{GRPC_PORT}"
    deadline = asyncio.get_event_loop().time() + 30

    stdscr.nodelay(True)
    while asyncio.get_event_loop().time() < deadline:
        secs_left = int(deadline - asyncio.get_event_loop().time())
        show_status(stdscr, " R E M A T C H", [
            f"Reconnecting to {host_ip}... ({secs_left}s)",
            "ESC to cancel",
        ])
        key = stdscr.getch()
        if key == 27:
            stdscr.nodelay(False)
            return None, None, None
        try:
            async with grpc.aio.insecure_channel(address) as channel:
                stub = game_pb2_grpc.LobbyServiceStub(channel)
                net_logger.grpc_sent(address, "JoinLobby",
                                     f"player_id={player_id} name={player_name}")
                stream = stub.JoinLobby(game_pb2.PlayerInfo(
                    player_id=player_id,
                    player_name=player_name,
                    ip_address=ip,
                    port=P2P_PORT,
                ))
                async for event in stream:
                    if event.HasField('game_start'):
                        net_logger.grpc_recv(address, "JoinLobby/game_start",
                                             f"peers={len(event.game_start.all_peers)} seed={event.game_start.map_name[:8]}")
                        stdscr.nodelay(False)
                        peers = list(event.game_start.all_peers)
                        patched = []
                        for p in peers:
                            if not p.ip_address:
                                p2 = game_pb2.PlayerInfo()
                                p2.CopyFrom(p)
                                p2.ip_address = host_ip
                                patched.append(p2)
                            else:
                                patched.append(p)
                        peer_list = [p for p in patched if p.player_id != player_id]
                        return None, peer_list, event.game_start.map_name
        except grpc.aio.AioRpcError:
            await asyncio.sleep(1)

    stdscr.nodelay(False)
    return None, None, None
