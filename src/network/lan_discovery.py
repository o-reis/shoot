import asyncio
import ipaddress
import logging
import socket
import time

import src.network.net_logger as net_logger

logger = logging.getLogger(__name__)

BROADCAST_PORT = 8471
PEER_TIMEOUT_SECONDS = 10.0
_PACKET_HEADER = b"SHOOT_NODE:"


class LANScanner(asyncio.DatagramProtocol):
    def __init__(self):
        self.found_peers = {}
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        if not data.startswith(_PACKET_HEADER):
            return
        try:
            port_str = data[len(_PACKET_HEADER):].decode().strip()
            src_ip = addr[0]
            if port_str.isdigit() and src_ip and src_ip != "0.0.0.0":
                self.found_peers[(src_ip, int(port_str))] = time.time()
                net_logger.lan_recv(src_ip, addr[1], f"dht_port={port_str}")
        except Exception as e:
            logger.error(f"LANScanner recv error: {e}")

    def get_peers(self) -> list:
        now = time.time()
        self.found_peers = {k: v for k, v in self.found_peers.items()
                            if now - v < PEER_TIMEOUT_SECONDS}
        return list(self.found_peers.keys())


async def start_lan_scanner() -> LANScanner:
    loop = asyncio.get_running_loop()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if hasattr(socket, "SO_REUSEPORT"):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    sock.bind(("", BROADCAST_PORT))
    _, protocol = await loop.create_datagram_endpoint(lambda: LANScanner(), sock=sock)
    return protocol


def _get_broadcast_addr() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
    finally:
        s.close()
    try:
        iface = ipaddress.IPv4Interface(f"{local_ip}/24")
        return str(iface.network.broadcast_address)
    except Exception:
        return "255.255.255.255"


async def broadcast_node(kademlia_port: int, interval: float = 1.0):
    msg = _PACKET_HEADER + str(kademlia_port).encode()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    bcast = _get_broadcast_addr()
    logger.debug(f"Broadcasting to {bcast}:{BROADCAST_PORT}")
    try:
        while True:
            try:
                sock.sendto(msg, (bcast, BROADCAST_PORT))
                net_logger.lan_sent(f"{bcast}:{BROADCAST_PORT}", f"dht_port={kademlia_port}")
            except Exception as e:
                logger.debug(f"Broadcast send error: {e}")
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        pass
    finally:
        sock.close()
