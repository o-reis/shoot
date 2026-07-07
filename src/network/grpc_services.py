import asyncio
import queue
import grpc
import game_pb2
import game_pb2_grpc
import src.network.net_logger as net_logger


class LobbyService(game_pb2_grpc.LobbyServiceServicer):

    def __init__(self):
        self.clients = {}
        self.players_in_lobby = []
        self.host_info = None
        self._game_started = False

    async def JoinLobby(self, request: game_pb2.PlayerInfo, context):
        player_id = request.player_id
        peer_addr = context.peer() if context else "?"
        net_logger.grpc_recv(peer_addr, "JoinLobby",
                             f"player_id={player_id} name={request.player_name}")

        if self._game_started:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, "game already in progress")
            return

        client_queue = asyncio.Queue()
        self.clients[player_id] = client_queue
        if not self._game_started:
            self.players_in_lobby.append(request)

            # send host info to new joiner so they see the host name immediately
            if self.host_info is not None:
                await client_queue.put(game_pb2.LobbyEvent(player_joined=self.host_info))

            # send all existing players to new joiner
            for p in self.players_in_lobby:
                if p.player_id != player_id:
                    await client_queue.put(game_pb2.LobbyEvent(player_joined=p))

            # notify existing clients about new joiner
            join_event = game_pb2.LobbyEvent(player_joined=request)
            for pid, q in self.clients.items():
                if pid != player_id:
                    await q.put(join_event)

        try:
            while True:
                event = await client_queue.get()
                yield event
                if event.HasField("game_start"):
                    break
        finally:
            self.clients.pop(player_id, None)
            self.players_in_lobby = [p for p in self.players_in_lobby if p.player_id != player_id]
            if not self._game_started:
                leave_event = game_pb2.LobbyEvent(player_left=str(player_id))
                for q in self.clients.values():
                    await q.put(leave_event)

    async def LeaveLobby(self, request: game_pb2.PlayerInfo, context):
        return game_pb2.ServerReply(success=True, message="Left lobby")

    async def trigger_game_start(self, map_seed: str = ""):
        self._game_started = True
        all_peers = list(self.players_in_lobby)
        if self.host_info is not None:
            all_peers.append(self.host_info)

        start_event = game_pb2.LobbyEvent(
            game_start=game_pb2.GameStart(all_peers=all_peers, map_name=map_seed)
        )
        net_logger.grpc_sent("all_clients", "GameStart",
                             f"peers={len(all_peers)} seed={map_seed[:8]}")
        for q in self.clients.values():
            await q.put(start_event)


class PeerGameService(game_pb2_grpc.PeerGameServiceServicer):

    def __init__(self, global_incoming_queue: queue.Queue):
        self.global_incoming_queue = global_incoming_queue
        self.peer_outboxes = []

    async def P2PStream(self, request_iterator, context):
        peer_addr = context.peer() if context else "?"
        net_logger.grpc_recv(peer_addr, "P2PStream/connect", "peer connected")
        my_outbox = asyncio.Queue()
        self.peer_outboxes.append(my_outbox)
        receiver_task = asyncio.create_task(self._receive_from_peer(request_iterator, peer_addr))
        try:
            while True:
                event = await my_outbox.get()
                yield event
        finally:
            receiver_task.cancel()
            if my_outbox in self.peer_outboxes:
                self.peer_outboxes.remove(my_outbox)

    async def _receive_from_peer(self, request_iterator, peer_addr: str = "?"):
        try:
            async for event in request_iterator:
                field = event.WhichOneof("event") or "unknown"
                net_logger.grpc_recv(peer_addr, f"P2PStream/{field}", "")
                self.global_incoming_queue.put(event)
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
