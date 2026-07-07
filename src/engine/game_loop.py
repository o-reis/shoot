#!/usr/bin/env python3

import asyncio
import ctypes
import curses
import math
import os
import queue
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path

import grpc

_src_path = Path(__file__).resolve().parent.parent
sys.path.append(str(_src_path / "network" / "generated"))
sys.path.append(str(_src_path))

from network.grpc_services import PeerGameService
from network.udp_sync import UDPStateBroadcaster, UDPStateReceiver
import src.network.net_logger as net_logger

from . import renderer
from . import world
from .player import Player
from .safe_zone import SafeZone
from .weapons import WEAPONS

import game_pb2
import game_pb2_grpc

MOVE_SPEED = 2.0
ROTATION_SPEED = 1.0
TARGET_FPS = 60
FRAME_TIME = 1.0 / TARGET_FPS
ZONE_SHRINK_INTERVAL = 13
REMATCH_COUNTDOWN_SECONDS = 10
PEER_TIMEOUT_SECONDS = 5

IS_WINDOWS = (os.name == 'nt')

_wheel_delta = 0  # accumulated scroll ticks, consumed each frame

if IS_WINDOWS:

    def _install_wheel_hook():
        global _wheel_delta

        import ctypes.wintypes as _wt

        class MSLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [
                ("pt", _wt.POINT),
                ("mouseData", _wt.DWORD),
                ("flags", _wt.DWORD),
                ("time", _wt.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
            ]

        WH_MOUSE_LL = 14
        WM_MOUSEWHEEL = 0x020A
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, ctypes.c_uint, ctypes.POINTER(MSLLHOOKSTRUCT))

        def _hook_proc(nCode, wParam, lParam):
            global _wheel_delta
            if nCode >= 0 and wParam == WM_MOUSEWHEEL:
                delta = ctypes.c_short((lParam.contents.mouseData >> 16) & 0xFFFF).value
                _wheel_delta += (-1 if delta > 0 else 1)
            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        hook_fn = HOOKPROC(_hook_proc)
        hook = user32.SetWindowsHookExW(WH_MOUSE_LL, hook_fn, kernel32.GetModuleHandleW(None), 0)

        msg = _wt.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        user32.UnhookWindowsHookEx(hook)

    _wheel_thread = threading.Thread(target=_install_wheel_hook, daemon=True)
    _wheel_thread.start()


def _consume_wheel_delta():
    global _wheel_delta
    d = _wheel_delta
    _wheel_delta = 0
    return d


def _lock_mouse():
    if IS_WINDOWS:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        rect = wintypes.RECT()
        if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            user32.ClipCursor(ctypes.byref(rect))


def _unlock_mouse():
    if IS_WINDOWS:
        ctypes.windll.user32.ClipCursor(None)


def _is_key_held(vk_code):
    if not IS_WINDOWS:
        return False
    return (ctypes.windll.user32.GetAsyncKeyState(vk_code) & 0x8000) != 0


def _get_held_keys():
    if not IS_WINDOWS:
        return set()
    mapping = {
        0x57: ord('w'), 0x41: ord('a'), 0x53: ord('s'), 0x44: ord('d'),
        0x51: ord('q'), 0x45: ord('e'), 0x52: ord('R'), 0x20: ord(' '),
        0x25: curses.KEY_LEFT, 0x26: curses.KEY_UP,
        0x27: curses.KEY_RIGHT, 0x28: curses.KEY_DOWN,
    }
    return {mapped for vk, mapped in mapping.items() if _is_key_held(vk)}


def _peer_info_to_dict(peer):
    if hasattr(peer, 'ip_address'):
        return {'ip': peer.ip_address, 'port': peer.port}
    return peer


def _show_full_screen_message(stdscr, lines, color_pair=2):
    stdscr.erase()
    max_rows, max_cols = stdscr.getmaxyx()
    start_y = max_rows // 2 - len(lines) // 2
    for i, (text, bold) in enumerate(lines):
        attr = curses.color_pair(color_pair) | curses.A_BOLD if bold else curses.color_pair(5)
        try:
            stdscr.addstr(start_y + i, max((max_cols - len(text)) // 2, 0), text, attr)
        except curses.error:
            pass
    stdscr.refresh()


def _grpc_worker(incoming_queue, outgoing_queue, peer_dicts, local_port, stop_event):
    async def run():
        async_stop = asyncio.Event()

        def _watch_stop():
            stop_event.wait()
            try:
                loop.call_soon_threadsafe(async_stop.set)
            except RuntimeError:
                pass

        loop = asyncio.get_event_loop()
        watcher = threading.Thread(target=_watch_stop, daemon=True)
        watcher.start()

        peer_servicer = PeerGameService(global_incoming_queue=incoming_queue)
        server = grpc.aio.server()
        game_pb2_grpc.add_PeerGameServiceServicer_to_server(peer_servicer, server)
        server.add_insecure_port(f'[::]:{local_port}')
        await server.start()

        peer_send_queues = [asyncio.Queue() for _ in peer_dicts]

        async def _connect_to_peer(peer, send_q):
            addr = f"{peer['ip']}:{peer['port']}"
            while not async_stop.is_set():
                try:
                    channel = grpc.aio.insecure_channel(addr)
                    stub = game_pb2_grpc.PeerGameServiceStub(channel)

                    async def _request_gen(q=send_q):
                        while not async_stop.is_set():
                            try:
                                event = q.get_nowait()
                                yield event
                            except queue.Empty:
                                await asyncio.sleep(0.01)

                    async for incoming in stub.P2PStream(_request_gen()):
                        if async_stop.is_set():
                            break
                        incoming_queue.put_nowait(incoming)
                except Exception:
                    if async_stop.is_set():
                        break
                    await asyncio.sleep(2.0)

        peer_tasks = [
            asyncio.create_task(_connect_to_peer(p, q))
            for p, q in zip(peer_dicts, peer_send_queues)
        ]

        while not async_stop.is_set():
            await asyncio.sleep(0.01)
            try:
                event = outgoing_queue.get_nowait()
                field = event.WhichOneof("event") or "unknown"
                for p, sq in zip(peer_dicts, peer_send_queues):
                    net_logger.grpc_sent(f"{p['ip']}:{p['port']}", f"P2PStream/{field}", "")
                    sq.put_nowait(event)
            except queue.Empty:
                pass

        while True:
            try:
                event = outgoing_queue.get_nowait()
                field = event.WhichOneof("event") or "unknown"
                for p, sq in zip(peer_dicts, peer_send_queues):
                    net_logger.grpc_sent(f"{p['ip']}:{p['port']}", f"P2PStream/{field}", "")
                    sq.put_nowait(event)
            except queue.Empty:
                break
        await asyncio.sleep(0.15)

        for t in peer_tasks:
            t.cancel()
        await asyncio.gather(*peer_tasks, return_exceptions=True)
        await server.stop(grace=0)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run())
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


def game(stdscr, map_path="assets/generated.map", peers=None, player_id=None,
         player_name="Player", local_port=50052, map_seed=None, is_host=False):
    if peers is None:
        peers = []
    if player_id is None:
        player_id = 0

    peer_dicts = [_peer_info_to_dict(p) for p in peers]
    active_peer_ids = {p.player_id for p in peers if hasattr(p, 'player_id')}

    _numeric_to_name = {}
    for p in peers:
        if hasattr(p, 'player_id') and hasattr(p, 'player_name') and p.player_name:
            _numeric_to_name[p.player_id] = p.player_name

    incoming_queue = queue.Queue()
    outgoing_queue = queue.Queue()

    dead_peers = set()
    disconnected_peers = set()
    game_state = ["playing"]
    spectate_idx = [0]
    kill_feed = []
    player_wants_rematch = [False]

    peer_last_state = {}
    peer_last_seen = {}
    peer_names = {}

    player_ref = [None]
    last_attacker_name = [""]
    shift_was_held = [False]
    left_was_held = [False]
    right_was_held = [False]

    def _all_enemies_eliminated():
        eliminated = dead_peers | disconnected_peers
        return active_peer_ids.issubset(eliminated)

    def _check_victory():
        if game_state[0] != "playing":
            return
        if not active_peer_ids:
            return
        if player_ref[0] is not None and player_ref[0].hp > 0 and _all_enemies_eliminated():
            game_state[0] = "victory"

    def on_player_position_received(pid, x, y, angle, hp):
        numeric = int(pid)
        if numeric == player_id:
            return
        now = time.time()

        if numeric in peer_last_state:
            last_state = peer_last_state[numeric]
            dt = now - peer_last_seen[numeric]
            if dt > 0:
                distance = math.sqrt((x - last_state["x"])**2 + (y - last_state["y"])**2)
                if distance / dt > 15.0:
                    return

        name = peer_names.get(numeric) or _numeric_to_name.get(numeric) or pid[:4]
        peer_names[numeric] = name
        peer_last_state[numeric] = {"x": x, "y": y, "angle": angle, "hp": hp, "name": name}
        peer_last_seen[numeric] = now
        if numeric not in dead_peers and numeric not in disconnected_peers:
            world.update_network_player(numeric, x, y, angle, label=name, full_pid=pid)

    def on_dead_ping_received(pid):
        numeric = int(pid)
        if numeric == player_id:
            return
        if numeric not in dead_peers:
            dead_peers.add(numeric)
            world.remove_network_player(numeric)
        _check_victory()

    def on_attack_received(attacker_id, target_id, damage):
        if int(target_id) == player_id and player_ref[0] is not None:
            MAX_POSSIBLE_DAMAGE = 80
            if damage > MAX_POSSIBLE_DAMAGE:
                return

            attacker_numeric = int(attacker_id)
            if attacker_numeric in peer_last_state:
                attacker_pos = peer_last_state[attacker_numeric]
                my_x, my_y = player_ref[0].x, player_ref[0].y
                dist = math.sqrt((attacker_pos["x"] - my_x)**2 + (attacker_pos["y"] - my_y)**2)
                if dist > 55.0:
                    return

            last_attacker_name[0] = peer_names.get(int(attacker_id), attacker_id[:4])
            player_ref[0].take_damage(damage)

    grpc_stop_event = threading.Event()
    grpc_thread = threading.Thread(
        target=_grpc_worker,
        args=(incoming_queue, outgoing_queue, peer_dicts, local_port, grpc_stop_event),
        daemon=True
    )
    grpc_thread.start()

    
    udp_broadcaster = UDPStateBroadcaster(str(player_id), peer_dicts, local_port, numeric_id=player_id)
    peer_ips = {d['ip'] for d in peer_dicts if d.get('ip')}
    udp_receiver = UDPStateReceiver(
        local_port,
        on_player_position_received,
        on_attack_received=on_attack_received,
        on_dead_received=on_dead_ping_received,
        allowed_ips=peer_ips if peer_ips else None,
    )
    udp_broadcaster.start()
    udp_receiver.start()

    curses.curs_set(0)
    stdscr.keypad(True)
    stdscr.nodelay(True)
    stdscr.timeout(0)
    curses.start_color()
    curses.use_default_colors()
    for pair_id, fg, bg in [
        (1, curses.COLOR_WHITE, curses.COLOR_BLACK),
        (2, curses.COLOR_WHITE, curses.COLOR_BLACK),
        (5, curses.COLOR_GREEN, curses.COLOR_BLACK),
        (6, curses.COLOR_BLUE,  curses.COLOR_BLACK),
        (7, curses.COLOR_WHITE, curses.COLOR_BLACK),
        (8, curses.COLOR_RED,   curses.COLOR_BLACK),
        (9, curses.COLOR_RED,   curses.COLOR_BLACK),
    ]:
        curses.init_pair(pair_id, fg, bg)

    curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
    if not IS_WINDOWS:
        print('\033[?1003h\033[?1015h\033[?1006h', end='')
        sys.stdout.flush()

    try:
        sx, sy = world.random_spawn(seed=map_seed, player_id=player_id)
    except Exception:
        sx, sy = world.PLAYER_START[0], world.PLAYER_START[1]

    current_player = Player(sx, sy, world.PLAYER_START[2])
    player_ref[0] = current_player
    safe_zone = SafeZone(0, 0, world.MAP_W, world.MAP_H)

    anim_timer = 0
    prev_time = time.time()
    fps = 0.0
    show_map = False
    last_shrink_time = time.time()
    last_shot_time = 0.0
    depth_buf = []
    weapon_idx = 0
    weapon = WEAPONS[weapon_idx]
    _pending_shot = [None]
    _hitscan_result = [None]

    _lock_mouse()

    while True:
        mouse_clicked = False

        if IS_WINDOWS and (_is_key_held(0x01) or _is_key_held(0x0D)):
            if time.time() - last_shot_time >= weapon.reload:
                mouse_clicked = True
                last_shot_time = time.time()

        try:
            while True:
                net_event = incoming_queue.get_nowait()
                if net_event.HasField('bullet_fired'):
                    b = net_event.bullet_fired
                    world.add_tracer(b.xi, b.yi, b.xf, b.yf)
                elif net_event.HasField('player_death'):
                    d = net_event.player_death
                    dead_num = d.player_id
                    dead_peers.add(dead_num)
                    world.remove_network_player(dead_num)
                    killer = d.killer_id or "?"
                    victim = peer_names.get(dead_num, str(dead_num))
                    kill_feed.append([f"{killer} killed {victim}", time.time() + 5.0])
                    _check_victory()
                elif net_event.HasField('game_ended'):
                    if game_state[0] == "playing":
                        game_state[0] = "spectating"
                elif net_event.HasField('disconnect_event'):
                    d_pid = net_event.disconnect_event.player_id
                    numeric = int(d_pid)
                    disconnected_peers.add(numeric)
                    dead_peers.discard(numeric)
                    world.remove_network_player(numeric)
                    udp_broadcaster.remove_peer_by_id(d_pid)
                    name = peer_names.get(numeric, d_pid[:4])
                    kill_feed.append([f"{name} left the game", time.time() + 5.0])
                    _check_victory()
        except queue.Empty:
            pass

        if game_state[0] == "playing":
            _now = time.time()
            for pid in list(active_peer_ids):
                if pid in dead_peers or pid in disconnected_peers:
                    continue
                last = peer_last_seen.get(pid)
                if last is not None and _now - last > PEER_TIMEOUT_SECONDS:
                    disconnected_peers.add(pid)
                    dead_peers.discard(pid)
                    world.remove_network_player(pid)
                    udp_broadcaster.remove_peer_by_id(str(pid))
                    name = peer_names.get(pid, str(pid))
                    kill_feed.append([f"{name} disconnected", _now + 5.0])
                    _check_victory()

        now = time.time()
        dt = now - prev_time
        remaining = FRAME_TIME - dt
        if remaining > 0.002:
            time.sleep(remaining - 0.002)
        while time.time() - prev_time < FRAME_TIME:
            pass
        now = time.time()
        dt = now - prev_time
        prev_time = now
        dt = min(dt, 0.1)
        if dt > 0:
            fps = 0.85 * fps + 0.15 * (1.0 / dt)

        anim_timer = (anim_timer + 1) % 16
        max_rows, max_cols = stdscr.getmaxyx()

        pressed = set()
        scroll_delta = 0
        while True:
            key = stdscr.getch()
            if key == -1:
                break
            if key == curses.KEY_MOUSE:
                try:
                    _, _mx, _my, _, bstate = curses.getmouse()
                    if bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED |
                                 curses.BUTTON1_RELEASED | curses.BUTTON1_DOUBLE_CLICKED):
                        if time.time() - last_shot_time >= weapon.reload:
                            mouse_clicked = True
                            last_shot_time = time.time()
                    if bstate & curses.BUTTON4_PRESSED:
                        scroll_delta -= 1
                    if bstate & curses.BUTTON5_PRESSED:
                        scroll_delta += 1
                except curses.error:
                    pass
                continue
            if key in (curses.KEY_ENTER, 10, 13):
                if time.time() - last_shot_time >= weapon.reload:
                    mouse_clicked = True
                    last_shot_time = time.time()
                continue
            pressed.add(key)
            if key in (ord('m'), ord('M')):
                show_map = not show_map

        pressed |= _get_held_keys()
        scroll_delta += _consume_wheel_delta()

        if 27 in pressed and game_state[0] == "playing":
            outgoing_queue.put(game_pb2.GameEvent(
                disconnect_event=game_pb2.PlayerDisconnect(player_id=str(player_id))
            ))
            time.sleep(0.1)
            grpc_stop_event.set()
            grpc_thread.join(timeout=3.0)
            udp_broadcaster.stop()
            udp_receiver.stop()
            _unlock_mouse()
            return True

        for digit, idx in ((ord('1'), 0), (ord('2'), 1), (ord('3'), 2), (ord('4'), 3), (ord('5'), 4)):
            if digit in pressed and idx < len(WEAPONS):
                weapon_idx = idx
                weapon = WEAPONS[weapon_idx]
        shift_held = IS_WINDOWS and (_is_key_held(0xA0) or _is_key_held(0xA1))
        if not IS_WINDOWS:
            shift_held = curses.KEY_SR in pressed or curses.KEY_SF in pressed
        if shift_held and not shift_was_held[0]:
            scroll_delta += 1
        shift_was_held[0] = shift_held
        if scroll_delta:
            weapon_idx = (weapon_idx + scroll_delta) % len(WEAPONS)
            weapon = WEAPONS[weapon_idx]

        if game_state[0] in ("spectating", "victory"):
            if 27 in pressed:
                if not is_host:
                    outgoing_queue.put(game_pb2.GameEvent(
                        disconnect_event=game_pb2.PlayerDisconnect(player_id=str(player_id))
                    ))
                time.sleep(0.1)
                break

            if ord('r') in pressed or ord('R') in pressed:
                player_wants_rematch[0] = True
                break

            if is_host:
                rematch_hint = "R = host rematch  |  ESC = quit"
            else:
                rematch_hint = "R = rematch  |  ESC = quit"

            if game_state[0] == "victory":
                _show_full_screen_message(stdscr, [
                    (" V I C T O R Y ! ", True),
                    ("", False),
                    ("You are the last one standing!", False),
                    ("", False),
                    (rematch_hint, False),
                ], color_pair=5)
                continue

            alive_pids = [pid for pid, st in peer_last_state.items()
                          if st.get("hp", 0) > 0 and pid not in dead_peers]
            game_over = len(alive_pids) <= 1
            if game_over:
                _show_full_screen_message(stdscr, [
                    (" G A M E   O V E R ", True),
                    ("", False),
                    (rematch_hint, False),
                ], color_pair=8)
            else:
                spectate_idx[0] = spectate_idx[0] % len(alive_pids)
                watched_pid = alive_pids[spectate_idx[0]]
                st = peer_last_state[watched_pid]
                spx, spy, spa = st["x"], st["y"], st["angle"]
                watched_name = st.get("name", str(watched_pid)[:4])

                left_held = curses.KEY_LEFT in pressed
                right_held = curses.KEY_RIGHT in pressed
                if left_held and not left_was_held[0]:
                    spectate_idx[0] = (spectate_idx[0] - 1) % len(alive_pids)
                if right_held and not right_was_held[0]:
                    spectate_idx[0] = (spectate_idx[0] + 1) % len(alive_pids)
                left_was_held[0] = left_held
                right_was_held[0] = right_held

                stdscr.bkgd(' ', curses.color_pair(1))
                stdscr.erase()
                spec_depth_buf, spec_num_cols = renderer.cast_rays(
                    stdscr, spx, spy, spa, 0.0, 0.0, max_rows, max_cols
                )
                renderer.draw_sprites(
                    stdscr, spx, spy, spa,
                    spec_depth_buf, spec_num_cols, max_rows, 0.0, 0.0, anim_timer
                )
                renderer.draw_hud(
                    stdscr, spx, spy, spa,
                    fps, 0.0, 0.0, max_rows, max_cols,
                    player_hp=st.get("hp", 0),
                    outside_zone=False, zone_dps=0,
                    safe_zone_cx=None, safe_zone_cy=None,
                    weapon=weapon, last_shot_time=0,
                    kill_feed=kill_feed,
                )
                try:
                    label = f" SPECTATING: {watched_name}  [<-/-> switch]  |  {rematch_hint} "
                    stdscr.addstr(0, max((max_cols - len(label)) // 2, 0), label,
                                  curses.color_pair(8) | curses.A_BOLD)
                except curses.error:
                    pass
                stdscr.refresh()
            continue

        is_sprinting = (curses.KEY_SR in pressed or ord('R') in pressed)
        move_speed = MOVE_SPEED * (2.0 if is_sprinting else 1.0) * dt
        rot_speed  = ROTATION_SPEED * dt

        if curses.KEY_LEFT in pressed or ord('a') in pressed or ord('A') in pressed:
            current_player.rotate(-rot_speed)
        if curses.KEY_RIGHT in pressed or ord('d') in pressed or ord('D') in pressed:
            current_player.rotate(rot_speed)

        moving_forward = curses.KEY_UP in pressed or ord('w') in pressed or ord('W') in pressed
        moving_back    = curses.KEY_DOWN in pressed or ord('s') in pressed or ord('S') in pressed

        wall_nudge = 0.0255

        if moving_forward:
            dx = (math.cos(current_player.angle) + wall_nudge) * move_speed
            dy = (math.sin(current_player.angle) + wall_nudge) * move_speed
            if not world.is_wall(current_player.x + dx, current_player.y):
                current_player.move(dx, 0)
            if not world.is_wall(current_player.x, current_player.y + dy):
                current_player.move(0, dy)

        if moving_back:
            dx = -(math.cos(current_player.angle) + wall_nudge) * move_speed
            dy = -(math.sin(current_player.angle) + wall_nudge) * move_speed
            if not world.is_wall(current_player.x + dx, current_player.y):
                current_player.move(dx, 0)
            if not world.is_wall(current_player.x, current_player.y + dy):
                current_player.move(0, dy)

        if game_state[0] == "playing":
            udp_broadcaster.update_state(current_player.x, current_player.y,
                                         current_player.angle, current_player.hp)

        if _hitscan_result[0] is not None:
            target_pid, full_pid, wsnap, px_snap, py_snap, angle_snap, dbuf_snap = _hitscan_result[0]
            _hitscan_result[0] = None
            if target_pid:
                for sp in world.SPRITES:
                    if sp.get("pid") == target_pid:
                        sp["hit_until"] = time.time() + 2.0
                        world.add_tracer(sp["x"], sp["y"], sp["x"], sp["y"], duration=2.0)
                        break
            else:
                wall_dist = dbuf_snap[len(dbuf_snap) // 2] if dbuf_snap else wsnap.range
                wx = px_snap + math.cos(angle_snap) * wall_dist
                wy = py_snap + math.sin(angle_snap) * wall_dist
                world.add_tracer(wx, wy, wx, wy, duration=3.0)
            xf = px_snap + math.cos(angle_snap) * wsnap.range
            yf = py_snap + math.sin(angle_snap) * wsnap.range
            outgoing_queue.put(game_pb2.GameEvent(
                bullet_fired=game_pb2.Bullet(
                    attacker_id=str(player_id),
                    xi=px_snap, yi=py_snap,
                    xf=xf, yf=yf,
                )
            ))
            if target_pid and full_pid:
                threading.Thread(
                    target=udp_broadcaster.send_attack,
                    args=(full_pid, wsnap.damage),
                    daemon=True
                ).start()

        if mouse_clicked and _pending_shot[0] is None:
            px_snap = current_player.x
            py_snap = current_player.y
            angle_snap = current_player.angle
            wsnap = weapon
            dbuf_snap = list(depth_buf)
            sprites_snap = [dict(sp) for sp in world.SPRITES if "pid" in sp]

            def _do_hitscan(px, py, pa, ws, dbuf, sprites):
                best_target = None
                closest_dist = ws.range
                for sp in sprites:
                    dx = sp["x"] - px
                    dy = sp["y"] - py
                    dist = math.sqrt(dx * dx + dy * dy)
                    if dist < 0.001 or dist > ws.range:
                        continue
                    diff = (math.atan2(dy, dx) - pa + math.pi) % (math.pi * 2) - math.pi
                    if abs(diff) < math.atan2(0.5, dist) and dist < closest_dist:
                        best_target = sp["pid"]
                        closest_dist = dist
                full_pid = next((sp.get("full_pid") for sp in sprites if sp.get("pid") == best_target), None) if best_target else None
                _hitscan_result[0] = (best_target, full_pid, ws, px, py, pa, dbuf)
                _pending_shot[0] = None

            _pending_shot[0] = True
            _do_hitscan(px_snap, py_snap, angle_snap, wsnap, dbuf_snap, sprites_snap)

        if ord('e') in pressed or ord('E') in pressed:
            current_player.look_timer = min(current_player.look_timer + 10.0 * dt, 3.0)
        if ord('q') in pressed or ord('Q') in pressed:
            current_player.look_timer = max(current_player.look_timer - 10.0 * dt, -3.0)

        if current_player.hp <= 0 and game_state[0] == "playing":
            game_state[0] = "spectating"
            udp_broadcaster.set_dead()
            outgoing_queue.put(game_pb2.GameEvent(
                player_death=game_pb2.PlayerDeath(
                    player_id=player_id,
                    killer_id=last_attacker_name[0] or "?",
                )
            ))

        if time.time() - last_shrink_time >= ZONE_SHRINK_INTERVAL:
            safe_zone.active = True
            safe_zone.shrink(1.0)
            last_shrink_time = time.time()

        if world.map_tile(current_player.x, current_player.y) == 'X':
            try:
                world.load_level(world.NEXT_LEVEL)
                px2, py2, pa2 = world.PLAYER_START
                current_player = Player(px2, py2, pa2)
                player_ref[0] = current_player
            except Exception:
                pass

        world.update_sprite_distances(current_player.x, current_player.y)
        world.move_sprites()

        safe_zone.update_damage(current_player)

        stdscr.bkgd(' ', curses.color_pair(1))
        stdscr.erase()

        shake_angle = 0.0
        if time.time() < current_player.hit_until:
            shake_angle = math.sin(time.time() * 60) * 0.03

        depth_buf, num_cols = renderer.cast_rays(
            stdscr, current_player.x, current_player.y,
            current_player.angle + shake_angle,
            current_player.jump_timer, current_player.look_timer,
            max_rows, max_cols
        )

        if not show_map:
            renderer.draw_sprites(
                stdscr, current_player.x, current_player.y, current_player.angle,
                depth_buf, num_cols, max_rows,
                current_player.jump_timer, current_player.look_timer, anim_timer
            )
            renderer.draw_hud(
                stdscr, current_player.x, current_player.y, current_player.angle,
                fps, current_player.jump_timer, current_player.look_timer, max_rows, max_cols,
                player_hp=current_player.hp,
                outside_zone=safe_zone.active and not safe_zone.is_safe(current_player.x, current_player.y),
                zone_dps=safe_zone.dps(),
                safe_zone_cx=safe_zone.x + safe_zone.width / 2 if safe_zone.active else None,
                safe_zone_cy=safe_zone.y + safe_zone.height / 2 if safe_zone.active else None,
                weapon=weapon,
                last_shot_time=last_shot_time,
                kill_feed=kill_feed,
            )
            renderer.draw_tracers(
                stdscr, current_player.x, current_player.y, current_player.angle,
                depth_buf, num_cols, max_rows,
                current_player.jump_timer, current_player.look_timer,
                weapon_range=weapon.range, spread=weapon.spread,
            )
            world.clear_old_tracers()
        else:
            renderer.draw_minimap(stdscr, current_player.x, current_player.y,
                                  max_rows, max_cols, fullscreen=True, safe_zone=safe_zone,
                                  pa=current_player.angle)

        stdscr.refresh()

    grpc_stop_event.set()
    grpc_thread.join(timeout=3.0)
    udp_broadcaster.stop()
    udp_receiver.stop()
    _unlock_mouse()

    if player_wants_rematch[0]:
        return "rematch"
    return None
