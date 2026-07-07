from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class KademliaNode(_message.Message):
    __slots__ = ("node_id", "ip_address", "port")
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    IP_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    PORT_FIELD_NUMBER: _ClassVar[int]
    node_id: bytes
    ip_address: str
    port: int
    def __init__(self, node_id: _Optional[bytes] = ..., ip_address: _Optional[str] = ..., port: _Optional[int] = ...) -> None: ...

class FindNodeRequest(_message.Message):
    __slots__ = ("sender", "target_id")
    SENDER_FIELD_NUMBER: _ClassVar[int]
    TARGET_ID_FIELD_NUMBER: _ClassVar[int]
    sender: KademliaNode
    target_id: bytes
    def __init__(self, sender: _Optional[_Union[KademliaNode, _Mapping]] = ..., target_id: _Optional[bytes] = ...) -> None: ...

class NodesResponse(_message.Message):
    __slots__ = ("nodes",)
    NODES_FIELD_NUMBER: _ClassVar[int]
    nodes: _containers.RepeatedCompositeFieldContainer[KademliaNode]
    def __init__(self, nodes: _Optional[_Iterable[_Union[KademliaNode, _Mapping]]] = ...) -> None: ...

class StoreRequest(_message.Message):
    __slots__ = ("sender", "key", "value")
    SENDER_FIELD_NUMBER: _ClassVar[int]
    KEY_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    sender: KademliaNode
    key: bytes
    value: bytes
    def __init__(self, sender: _Optional[_Union[KademliaNode, _Mapping]] = ..., key: _Optional[bytes] = ..., value: _Optional[bytes] = ...) -> None: ...

class FindValueRequest(_message.Message):
    __slots__ = ("sender", "key")
    SENDER_FIELD_NUMBER: _ClassVar[int]
    KEY_FIELD_NUMBER: _ClassVar[int]
    sender: KademliaNode
    key: bytes
    def __init__(self, sender: _Optional[_Union[KademliaNode, _Mapping]] = ..., key: _Optional[bytes] = ...) -> None: ...

class FindValueResponse(_message.Message):
    __slots__ = ("value", "closest_nodes")
    VALUE_FIELD_NUMBER: _ClassVar[int]
    CLOSEST_NODES_FIELD_NUMBER: _ClassVar[int]
    value: bytes
    closest_nodes: NodesResponse
    def __init__(self, value: _Optional[bytes] = ..., closest_nodes: _Optional[_Union[NodesResponse, _Mapping]] = ...) -> None: ...

class Ping(_message.Message):
    __slots__ = ("timestamp",)
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    timestamp: int
    def __init__(self, timestamp: _Optional[int] = ...) -> None: ...

class PlayerInfo(_message.Message):
    __slots__ = ("player_id", "player_name", "ip_address", "port")
    PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
    PLAYER_NAME_FIELD_NUMBER: _ClassVar[int]
    IP_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    PORT_FIELD_NUMBER: _ClassVar[int]
    player_id: int
    player_name: str
    ip_address: str
    port: int
    def __init__(self, player_id: _Optional[int] = ..., player_name: _Optional[str] = ..., ip_address: _Optional[str] = ..., port: _Optional[int] = ...) -> None: ...

class ServerReply(_message.Message):
    __slots__ = ("success", "message")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    def __init__(self, success: bool = ..., message: _Optional[str] = ...) -> None: ...

class LobbyEvent(_message.Message):
    __slots__ = ("player_joined", "player_left", "game_start")
    PLAYER_JOINED_FIELD_NUMBER: _ClassVar[int]
    PLAYER_LEFT_FIELD_NUMBER: _ClassVar[int]
    GAME_START_FIELD_NUMBER: _ClassVar[int]
    player_joined: PlayerInfo
    player_left: str
    game_start: GameStart
    def __init__(self, player_joined: _Optional[_Union[PlayerInfo, _Mapping]] = ..., player_left: _Optional[str] = ..., game_start: _Optional[_Union[GameStart, _Mapping]] = ...) -> None: ...

class GameStart(_message.Message):
    __slots__ = ("all_peers", "map_name")
    ALL_PEERS_FIELD_NUMBER: _ClassVar[int]
    MAP_NAME_FIELD_NUMBER: _ClassVar[int]
    all_peers: _containers.RepeatedCompositeFieldContainer[PlayerInfo]
    map_name: str
    def __init__(self, all_peers: _Optional[_Iterable[_Union[PlayerInfo, _Mapping]]] = ..., map_name: _Optional[str] = ...) -> None: ...

class PlayerState(_message.Message):
    __slots__ = ("player_id", "player_name", "x", "y", "direction", "hp")
    PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
    PLAYER_NAME_FIELD_NUMBER: _ClassVar[int]
    X_FIELD_NUMBER: _ClassVar[int]
    Y_FIELD_NUMBER: _ClassVar[int]
    DIRECTION_FIELD_NUMBER: _ClassVar[int]
    HP_FIELD_NUMBER: _ClassVar[int]
    player_id: int
    player_name: str
    x: float
    y: float
    direction: float
    hp: int
    def __init__(self, player_id: _Optional[int] = ..., player_name: _Optional[str] = ..., x: _Optional[float] = ..., y: _Optional[float] = ..., direction: _Optional[float] = ..., hp: _Optional[int] = ...) -> None: ...

class Attack(_message.Message):
    __slots__ = ("attacker_id", "target_id", "damage")
    ATTACKER_ID_FIELD_NUMBER: _ClassVar[int]
    TARGET_ID_FIELD_NUMBER: _ClassVar[int]
    DAMAGE_FIELD_NUMBER: _ClassVar[int]
    attacker_id: str
    target_id: str
    damage: int
    def __init__(self, attacker_id: _Optional[str] = ..., target_id: _Optional[str] = ..., damage: _Optional[int] = ...) -> None: ...

class Bullet(_message.Message):
    __slots__ = ("attacker_id", "xi", "yi", "xf", "yf")
    ATTACKER_ID_FIELD_NUMBER: _ClassVar[int]
    XI_FIELD_NUMBER: _ClassVar[int]
    YI_FIELD_NUMBER: _ClassVar[int]
    XF_FIELD_NUMBER: _ClassVar[int]
    YF_FIELD_NUMBER: _ClassVar[int]
    attacker_id: str
    xi: float
    yi: float
    xf: float
    yf: float
    def __init__(self, attacker_id: _Optional[str] = ..., xi: _Optional[float] = ..., yi: _Optional[float] = ..., xf: _Optional[float] = ..., yf: _Optional[float] = ...) -> None: ...

class PlayerDeath(_message.Message):
    __slots__ = ("player_id", "killer_id")
    PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
    KILLER_ID_FIELD_NUMBER: _ClassVar[int]
    player_id: int
    killer_id: str
    def __init__(self, player_id: _Optional[int] = ..., killer_id: _Optional[str] = ...) -> None: ...

class SafeZone(_message.Message):
    __slots__ = ("x", "y", "radius")
    X_FIELD_NUMBER: _ClassVar[int]
    Y_FIELD_NUMBER: _ClassVar[int]
    RADIUS_FIELD_NUMBER: _ClassVar[int]
    x: float
    y: float
    radius: float
    def __init__(self, x: _Optional[float] = ..., y: _Optional[float] = ..., radius: _Optional[float] = ...) -> None: ...

class GameEnd(_message.Message):
    __slots__ = ("winner_id",)
    WINNER_ID_FIELD_NUMBER: _ClassVar[int]
    winner_id: str
    def __init__(self, winner_id: _Optional[str] = ...) -> None: ...

class PlayerDisconnect(_message.Message):
    __slots__ = ("player_id",)
    PLAYER_ID_FIELD_NUMBER: _ClassVar[int]
    player_id: str
    def __init__(self, player_id: _Optional[str] = ...) -> None: ...

class GameEvent(_message.Message):
    __slots__ = ("state_update", "bullet_fired", "received_attack", "player_death", "zone_update", "game_ended", "disconnect_event")
    STATE_UPDATE_FIELD_NUMBER: _ClassVar[int]
    BULLET_FIRED_FIELD_NUMBER: _ClassVar[int]
    RECEIVED_ATTACK_FIELD_NUMBER: _ClassVar[int]
    PLAYER_DEATH_FIELD_NUMBER: _ClassVar[int]
    ZONE_UPDATE_FIELD_NUMBER: _ClassVar[int]
    GAME_ENDED_FIELD_NUMBER: _ClassVar[int]
    DISCONNECT_EVENT_FIELD_NUMBER: _ClassVar[int]
    state_update: PlayerState
    bullet_fired: Bullet
    received_attack: Attack
    player_death: PlayerDeath
    zone_update: SafeZone
    game_ended: GameEnd
    disconnect_event: PlayerDisconnect
    def __init__(self, state_update: _Optional[_Union[PlayerState, _Mapping]] = ..., bullet_fired: _Optional[_Union[Bullet, _Mapping]] = ..., received_attack: _Optional[_Union[Attack, _Mapping]] = ..., player_death: _Optional[_Union[PlayerDeath, _Mapping]] = ..., zone_update: _Optional[_Union[SafeZone, _Mapping]] = ..., game_ended: _Optional[_Union[GameEnd, _Mapping]] = ..., disconnect_event: _Optional[_Union[PlayerDisconnect, _Mapping]] = ...) -> None: ...
