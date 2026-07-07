import asyncio
import json
import socket
import time
from kademlia_dynamic import KademliaServer

PEER_TTL_SECONDS = 120
LOBBY_KEY_PREFIX = "shoot_lobby_"


def get_local_ip(target: str = "8.8.8.8") -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((target, 80))
        return s.getsockname()[0]
    finally:
        s.close()


async def register_player(node: KademliaServer, player_id, ip: str, port: int):
    await node.set(str(player_id), f"{ip}:{port}")


async def publish_lobby(node: KademliaServer, ip: str, lobby_info: dict):
    entry = {**lobby_info, "ts": time.time()}
    await node.set(LOBBY_KEY_PREFIX + ip, json.dumps(entry))


async def fetch_lobby_for_host(node: KademliaServer, host_ip: str) -> dict | None:
    raw = await node.get(LOBBY_KEY_PREFIX + host_ip)
    if not raw:
        return None
    entry = json.loads(raw)
    if time.time() - entry.get("ts", 0) > PEER_TTL_SECONDS:
        return None
    return entry


async def fetch_all_lobbies(node: KademliaServer, seed_ips: list[str] = None) -> list[dict]:
    routing_ips = {peer.ip for peer in node.routing_table.all_peers()}
    all_ips = routing_ips | set(seed_ips or [])

    fetch_tasks = [fetch_lobby_for_host(node, ip) for ip in all_ips]
    results = await asyncio.gather(*fetch_tasks)

    lobbies = []
    for ip, lobby in zip(all_ips, results):
        if lobby:
            lobby["_host_ip"] = ip
            lobbies.append(lobby)
    return lobbies


async def keep_alive(node: KademliaServer, host_ip: str, lobby_info: dict,
                     interval: float = PEER_TTL_SECONDS / 2):
    while True:
        await publish_lobby(node, host_ip, lobby_info)
        await asyncio.sleep(interval)
