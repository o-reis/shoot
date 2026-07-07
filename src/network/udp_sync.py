import logging
import socket
import struct
import threading
import time

import src.network.net_logger as net_logger

_log = logging.getLogger(__name__)

_PACKET_STATE  = 0
_PACKET_ATTACK = 1
_PACKET_DEAD   = 2


def _pid_bytes(player_id: str) -> bytes:
    return player_id.encode('utf-8')[:32].ljust(32, b'\x00')


def _encode_state(player_id: str, x: float, y: float, angle: float, hp: int) -> bytes:
    return struct.pack('!B32sfffI', _PACKET_STATE, _pid_bytes(player_id), x, y, angle, hp)


def _encode_dead(player_id: str) -> bytes:
    return struct.pack('!B32s', _PACKET_DEAD, _pid_bytes(player_id))


def _encode_attack(attacker_id: str, target_id: str, damage: int) -> bytes:
    return struct.pack('!B32s32sI', _PACKET_ATTACK, _pid_bytes(attacker_id), _pid_bytes(target_id), damage)


def _decode_pid(raw: bytes) -> str:
    return raw.rstrip(b'\x00').decode('utf-8')


def _decode_packet(data: bytes):
    if len(data) < 1:
        return None
    ptype = data[0]
    if ptype == _PACKET_STATE and len(data) >= 49:
        pid_bytes, x, y, angle, hp = struct.unpack('!32sfffI', data[1:49])
        return ('state', _decode_pid(pid_bytes), x, y, angle, hp)
    if ptype == _PACKET_ATTACK and len(data) >= 69:
        a_bytes, t_bytes, damage = struct.unpack('!32s32sI', data[1:69])
        return ('attack', _decode_pid(a_bytes), _decode_pid(t_bytes), damage)
    if ptype == _PACKET_DEAD and len(data) >= 33:
        pid_bytes, = struct.unpack('!32s', data[1:33])
        return ('dead', _decode_pid(pid_bytes))
    return None


class UDPStateBroadcaster:
    def __init__(self, player_id: str, peers: list, base_port: int, interval: float = 0.05, numeric_id: int = None):
        self.player_id = player_id
        self.numeric_id = numeric_id
        self.peers = peers
        self.base_port = base_port
        self.interval = interval
        self._state = None
        self._is_dead = False
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def update_state(self, x: float, y: float, angle: float, hp: int):
        with self._lock:
            self._state = (x, y, angle, hp)

    def set_dead(self):
        with self._lock:
            self._is_dead = True

    def send_attack(self, target_id: str, damage: int):
        payload = _encode_attack(self.player_id, target_id, damage)
        for peer in self.peers:
            try:
                self._sock.sendto(payload, (peer['ip'], peer['port']))
                net_logger.udp_sent(peer['ip'], peer['port'],
                                    "attack", f"attacker={self.player_id[:8]} target={target_id[:8]} dmg={damage}")
            except OSError as e:
                _log.error("UDPStateBroadcaster: attack send failed for %s: %s", peer, e)

    def remove_peer_by_id(self, player_id: str):
        with self._lock:
            self.peers = [p for p in self.peers if str(p.get('player_id')) != str(player_id)]

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        self._sock.close()

    def _broadcast(self, payload: bytes, label: str, detail: str):
        for peer in self.peers:
            try:
                self._sock.sendto(payload, (peer['ip'], peer['port']))
                net_logger.udp_sent(peer['ip'], peer['port'], label, detail)
            except OSError as e:
                _log.error("UDPStateBroadcaster: send failed for %s: %s", peer, e)

    def _run(self):
        pid_str = str(self.numeric_id) if self.numeric_id is not None else self.player_id
        while self._running:
            with self._lock:
                is_dead = self._is_dead
                state = self._state
            if is_dead:
                self._broadcast(
                    _encode_dead(pid_str),
                    "dead",
                    f"pid={pid_str[:8]}"
                )
            elif state:
                self._broadcast(
                    _encode_state(pid_str, *state),
                    "state",
                    f"pid={pid_str[:8]} x={state[0]:.1f} y={state[1]:.1f} hp={state[3]}"
                )
            time.sleep(self.interval)


class UDPStateReceiver:
    def __init__(self, listen_port: int, on_state_received, on_attack_received=None, on_dead_received=None, allowed_ips=None):
        self._listen_port = listen_port
        self._on_state = on_state_received
        self._on_attack = on_attack_received
        self._on_dead = on_dead_received
        self._allowed_ips = set(allowed_ips) if allowed_ips else None
        self._running = False
        self._thread = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(('', self._listen_port))
        except OSError as e:
            _log.error("UDPStateReceiver: cannot bind port %d: %s", self._listen_port, e)
            return
        sock.settimeout(0.5)
        while self._running:
            try:
                data, addr = sock.recvfrom(1024)
                if self._allowed_ips is not None and addr[0] not in self._allowed_ips:
                    continue
                result = _decode_packet(data)
                if result is None:
                    continue
                if result[0] == 'state':
                    _, pid, x, y, angle, hp = result
                    net_logger.udp_recv(addr[0], addr[1], "state",
                                        f"pid={pid[:8]} x={x:.1f} y={y:.1f} hp={hp}")
                    self._on_state(pid, x, y, angle, hp)
                elif result[0] == 'attack' and self._on_attack:
                    _, attacker, target, damage = result
                    net_logger.udp_recv(addr[0], addr[1], "attack",
                                        f"attacker={attacker[:8]} target={target[:8]} dmg={damage}")
                    self._on_attack(attacker, target, damage)
                elif result[0] == 'dead' and self._on_dead:
                    _, pid = result
                    net_logger.udp_recv(addr[0], addr[1], "dead", f"pid={pid[:8]}")
                    self._on_dead(pid)
            except socket.timeout:
                pass
            except OSError as e:
                _log.error("UDPStateReceiver: socket error: %s", e)
                break
        sock.close()
