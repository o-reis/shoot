import json
from kademlia_dynamic import KademliaServer
from src.network.matchmaking_helpers import register_player, publish_lobby, fetch_all_lobbies


async def start_scan() -> "LANScanner":
    from src.network.lan_discovery import start_lan_scanner
    return await start_lan_scanner()


async def init_node(port: int, bootstrap_nodes: list = None) -> KademliaServer:
    node = KademliaServer()
    await node.listen(port)
    if bootstrap_nodes:
        await node.bootstrap(bootstrap_nodes)
    return node


async def create_lobby(node: KademliaServer, name: str, ip: str, port: int, private: bool = False):
    info = {"name": name, "ip": ip, "port": port}
    await node.set(name, json.dumps(info))
    if not private:
        await publish_lobby(node, ip, info)


async def list_lobbies(node: KademliaServer, seed_ips: list[str] = None) -> list[dict]:
    return await fetch_all_lobbies(node, seed_ips)


async def join_private_game(node: KademliaServer, key: str):
    raw = await node.get(key)
    return json.loads(raw) if raw else None


async def join_player(node: KademliaServer, player_id: str, ip: str, port: int):
    await register_player(node, player_id, ip, port)
