import curses
import math
import textwrap
import time

from . import assets
from . import world

PI = math.pi
PI2 = PI * 2.0
PI_05 = PI * 0.5
PI_025 = PI * 0.25
PI_075 = PI * 0.75
PI_15 = PI * 1.5

MAX_RENDER_DEPTH = 16.0

_SHADE_CHARS = ('█', '▓', '▒', '░', ' ')
_B100, _B75, _B50, _B25, _B0 = _SHADE_CHARS

_DIRECTION_ARROWS = ['↑', '↗', '→', '↘', '↓', '↙', '←', '↖']


def _shade_wall_pixel(distance, is_north_south, pixel):
    if is_north_south:
        if distance < MAX_RENDER_DEPTH / 5.5:
            table = {_B100: _B100, _B75: _B75, _B50: _B50, 'else': _B25}
        elif distance < MAX_RENDER_DEPTH / 3.66:
            table = {_B100: _B75, _B75: _B50, _B50: _B25, 'else': _B0}
        elif distance < MAX_RENDER_DEPTH / 2.33:
            table = {_B100: _B50, _B75: _B25, _B50: _B25, 'else': _B0}
        elif distance < MAX_RENDER_DEPTH:
            table = {_B100: _B25, _B75: _B25, _B50: _B25, 'else': _B0}
        else:
            return _B0
    else:
        if distance < MAX_RENDER_DEPTH / 5.5:
            table = {_B100: _B75, _B75: _B50, _B50: _B25, 'else': _B0}
        elif distance < MAX_RENDER_DEPTH / 3.66:
            table = {_B100: _B50, _B75: _B50, _B50: _B25, 'else': _B0}
        elif distance < MAX_RENDER_DEPTH / 2.33:
            table = {_B100: _B50, _B75: _B25, _B50: _B25, 'else': _B0}
        elif distance < MAX_RENDER_DEPTH:
            table = {_B100: _B25, _B75: _B25, _B50: _B0, 'else': _B0}
        else:
            return _B0
    return table.get(pixel, table['else'])


def _floor_brightness(row, horizon_mid):
    h = max(1.0, horizon_mid)
    return 1.0 - (row - h) / h


def _floor_char(row, col, horizon_mid):
    b = _floor_brightness(row, horizon_mid)
    if b < 0.25:
        return 'x'
    if b < 0.5:
        return '='
    if b < 0.75:
        return '-'
    if b < 0.9:
        return '`'
    return ' '


def _horizon_bounds(screen_h, distance, jump_timer, look_timer):
    mid = screen_h / ((2.0 - jump_timer * 0.15) - look_timer * 0.15)
    return mid - screen_h / distance, mid + screen_h / distance, mid


def draw_minimap(stdscr, px, py, max_rows, max_cols, fullscreen=False, safe_zone=None, pa=0.0):
    if fullscreen:
        stdscr.erase()
        ox = max((max_cols - world.MAP_W) // 2, 0)
        oy = max((max_rows - world.MAP_H) // 2, 0)
    else:
        ox = max_cols - world.MAP_W - 2 if (world.MAP_W + 3) < max_cols else 1
        oy = 1

    for my in range(world.MAP_H):
        for mx in range(world.MAP_W):
            sy, sx = oy + my, ox + mx
            if not (0 <= sy < max_rows and 0 <= sx < max_cols - 1):
                continue

            tile = world.MAP[my][mx]
            ch = '·'
            if tile == 'X':
                ch = 'X'
            elif tile not in ('.', ' ', 'o', ','):
                ch = '█'

            color = curses.color_pair(5) | curses.A_DIM

            if safe_zone and safe_zone.active:
                if not safe_zone.is_safe(mx, my):
                    ch = '/'
                    color = curses.color_pair(6) | curses.A_DIM

                zx, zy, zw, zh = safe_zone.x, safe_zone.y, safe_zone.width, safe_zone.height
                is_top = int(zy) == my and int(zx) <= mx <= int(zx + zw)
                is_bot = int(zy + zh) == my and int(zx) <= mx <= int(zx + zw)
                is_lft = int(zx) == mx and int(zy) <= my <= int(zy + zh)
                is_rgt = int(zx + zw) == mx and int(zy) <= my <= int(zy + zh)

                if is_top or is_bot:
                    ch, color = '-', curses.color_pair(6) | curses.A_BOLD
                elif is_lft or is_rgt:
                    ch, color = '|', curses.color_pair(6) | curses.A_BOLD

            try:
                stdscr.addch(sy, sx, ch, color)
            except curses.error:
                pass

    for sp in world.SPRITES:
        if "pid" not in sp:
            continue
        spm_y, spm_x = oy + int(sp["y"]), ox + int(sp["x"])
        label = sp.get("label", "?")
        if 0 <= spm_y < max_rows and 0 <= spm_x < max_cols - 1:
            try:
                stdscr.addch(spm_y, spm_x, label[0] if label else '?', curses.color_pair(6) | curses.A_BOLD)
            except curses.error:
                pass

    pm_y, pm_x = oy + int(py), ox + int(px)
    if 0 <= pm_y < max_rows and 0 <= pm_x < max_cols - 1:
        arrow_idx = int((pa + math.pi / 8) / (math.pi / 4)) % 8
        screen_idx = (arrow_idx + 2) % 8
        try:
            stdscr.addstr(pm_y, pm_x, _DIRECTION_ARROWS[screen_idx], curses.color_pair(2) | curses.A_BOLD)
        except curses.error:
            pass


def _draw_hp_bar(stdscr, hp, max_hp=100):
    bar_width = 20
    filled = max(0, min(bar_width, int((hp / max_hp) * bar_width)))
    bar = "█" * filled + "░" * (bar_width - filled)
    color = curses.color_pair(5) if hp >= 25 else curses.color_pair(2)
    try:
        stdscr.addstr(1, 2, f"HP [{bar}] {hp}%", color | curses.A_BOLD)
    except curses.error:
        pass


def _draw_weapon_hud(stdscr, weapon, last_shot_time, row, max_cols):
    now = time.time()
    elapsed = now - last_shot_time
    frac = min(1.0, elapsed / weapon.reload) if weapon.reload > 0 else 1.0
    bar_w = 12
    filled = int(frac * bar_w)
    bar = "█" * filled + "░" * (bar_w - filled)
    ready_label = " RDY" if frac >= 1.0 else f" {weapon.reload - elapsed:.1f}s"
    line = f" {weapon.name} [{bar}]{ready_label} [1-5/scroll] "
    color = curses.color_pair(5) if frac >= 1.0 else curses.color_pair(8)
    try:
        stdscr.addstr(row, max_cols - len(line) - 1, line[:max_cols - 1], color | curses.A_BOLD)
    except curses.error:
        pass


def draw_hud(stdscr, px, py, pa, fps, jump_timer, look_timer, max_rows, max_cols,
             player_hp=100, outside_zone=False, zone_dps=1,
             safe_zone_cx=None, safe_zone_cy=None, weapon=None, last_shot_time=0.0,
             kill_feed=None):
    _draw_hp_bar(stdscr, player_hp)

    if weapon is not None:
        _draw_weapon_hud(stdscr, weapon, last_shot_time, 1, max_cols)

    cx, cy = max_cols // 2, max_rows // 2
    for (dy, dx, ch) in [(-1, 0, '|'), (1, 0, '|'), (0, -2, '-'), (0, -3, '-'), (0, 2, '-'), (0, 3, '-')]:
        try:
            stdscr.addch(cy + dy, cx + dx, ch, curses.color_pair(8) | curses.A_BOLD)
        except curses.error:
            pass

    feed_start_row = 3
    if outside_zone and safe_zone_cx is not None and safe_zone_cy is not None:
        world_angle = math.atan2(safe_zone_cy - py, safe_zone_cx - px)
        rel = (world_angle - pa + math.pi) % (2 * math.pi) - math.pi
        arrow_idx = int(rel / (math.pi / 4) + 0.5) % 8
        arrow = _DIRECTION_ARROWS[arrow_idx]
        warning = f" {arrow} <RETURN TO SAFE ZONE> {arrow} "
        col = max(0, (max_cols - len(warning)) // 2)
        try:
            stdscr.addstr(1, col, warning, curses.color_pair(2) | curses.A_BOLD | curses.A_BLINK)
        except curses.error:
            pass
        feed_start_row = 4

    if kill_feed:
        now = time.time()
        active = [entry for entry in kill_feed if entry[1] > now]
        kill_feed[:] = active
        for i, entry in enumerate(active[-5:]):
            row = feed_start_row + i
            if row >= max_rows - 1:
                break
            try:
                stdscr.addstr(row, 2, entry[0][:max_cols - 4],
                              curses.color_pair(8) | curses.A_BOLD)
            except curses.error:
                pass

    info = (f" POS({px:.1f},{py:.1f}) ANG({math.degrees(pa):.0f}°)"
            f" LK:{look_timer:.1f} FPS:{fps:.0f}"
            f" | W/S=move A/D=turn E/Q=look ESC=quit ")
    try:
        stdscr.addstr(max_rows - 1, 0,
                      info[:max_cols - 1].ljust(max_cols - 1),
                      curses.color_pair(5) | curses.A_REVERSE)
    except curses.error:
        pass


def cast_rays(stdscr, px, py, pa, jump_timer, look_timer, max_rows, max_cols):
    fov = PI / 2.25
    num_cols = max(10, max_cols - 1)
    depth_buf = []

    for col in range(num_cols):
        ray_angle = pa + (col / num_cols - 0.5) * fov
        eye_x = math.cos(ray_angle)
        eye_y = math.sin(ray_angle)

        map_x = int(px)
        map_y = int(py)

        inv_x = 1e30 if eye_x == 0 else abs(1.0 / eye_x)
        inv_y = 1e30 if eye_y == 0 else abs(1.0 / eye_y)

        step_x = 1 if eye_x >= 0 else -1
        step_y = 1 if eye_y >= 0 else -1

        side_x = (map_x + 1 - px) * inv_x if eye_x >= 0 else (px - map_x) * inv_x
        side_y = (map_y + 1 - py) * inv_y if eye_y >= 0 else (py - map_y) * inv_y

        hit_side = 0
        tile_char = '#'
        distance = MAX_RENDER_DEPTH

        for _ in range(64):
            if side_x < side_y:
                side_x += inv_x
                map_x  += step_x
                hit_side = 0
            else:
                side_y += inv_y
                map_y  += step_y
                hit_side = 1

            if map_x < 0 or map_x >= world.MAP_W or map_y < 0 or map_y >= world.MAP_H:
                break

            tile = world.MAP[map_y][map_x]
            if world.is_wall(map_x, map_y):
                tile_char = tile
                if hit_side == 0:
                    distance = (map_x - px + (1 - step_x) / 2) / eye_x if eye_x != 0 else MAX_RENDER_DEPTH
                else:
                    distance = (map_y - py + (1 - step_y) / 2) / eye_y if eye_y != 0 else MAX_RENDER_DEPTH
                distance = max(0.1, distance)
                break

        is_ns = hit_side == 1

        if hit_side == 0:
            sample_x = py + distance * eye_y
        else:
            sample_x = px + distance * eye_x
        sample_x -= math.floor(sample_x)

        depth_buf.append(distance)

        tex = assets.WALL_TEX.get(tile_char)
        ceiling_y, floor_y, horizon_mid = _horizon_bounds(max_rows, distance, jump_timer, look_timer)
        ceiling_y = max(0, int(ceiling_y))
        floor_y   = min(max_rows - 2, int(floor_y))

        for row in range(0, ceiling_y):
            try:
                stdscr.addch(row, col, ' ', curses.color_pair(6))
            except curses.error:
                pass

        wall_span = floor_y - ceiling_y
        for row in range(ceiling_y, floor_y):
            if tex:
                sy = (row - ceiling_y) / wall_span if wall_span > 0 else 0.0
                use_tex = tex
                if tex.get('texture') == 'DIRECTIONAL':
                    raw = tex.get('N', '') if is_ns else tex.get('S', '')
                    use_tex = {'texture': raw, 'width': tex.get('width', 16),
                               'height': tex.get('height', 16), 'scale': tex.get('scale', 1)}
                pixel = assets.sample_shaded(use_tex, sample_x, sy)
                ch = _shade_wall_pixel(distance, is_ns, pixel)
            else:
                if distance < MAX_RENDER_DEPTH / 6.5:
                    ch = _B100 if is_ns else _B75
                elif distance < MAX_RENDER_DEPTH / 4.66:
                    ch = _B75 if is_ns else _B50
                elif distance < MAX_RENDER_DEPTH / 3.33:
                    ch = _B50
                elif distance < MAX_RENDER_DEPTH:
                    ch = _B25
                else:
                    ch = _B0
            pair = curses.color_pair(2) if distance < MAX_RENDER_DEPTH / 4 else curses.color_pair(1)
            try:
                stdscr.addch(row, col, ch, pair)
            except curses.error:
                pass

        for row in range(floor_y, max_rows - 1):
            try:
                stdscr.addch(row, col, _floor_char(row, col, horizon_mid), curses.color_pair(5))
            except curses.error:
                pass

    return depth_buf, num_cols


def _pick_sprite_tex(sprite_def, angle_key, anim_timer):
    ang = sprite_def['angles'].get(angle_key, sprite_def['angles']['F'])
    frame = 'W1' if anim_timer < 5 else ('W2' if anim_timer < 10 else None)
    if frame and frame in ang:
        return ang[frame]
    return ang


def draw_sprites(stdscr, px, py, pa, depth_buf, num_cols, max_rows, jump_timer, look_timer, anim_timer):
    fov = PI / 2.25
    eye_x = math.cos(pa)
    eye_y = math.sin(pa)

    def horizon_mid(h):
        return h / ((2.0 - jump_timer * 0.15) - look_timer * 0.15)

    for sp in world.SPRITES:
        if "pid" not in sp:
            continue
        dist = sp["z"]
        if dist < 0.5:
            continue

        dx = sp["x"] - px
        dy = sp["y"] - py
        sprite_angle = math.atan2(dy, dx) - math.atan2(eye_y, eye_x)
        while sprite_angle < -PI:
            sprite_angle += PI2
        while sprite_angle > PI:
            sprite_angle -= PI2

        if abs(sprite_angle) >= fov / 2:
            continue

        sp_def = assets.SPRITE_DEFS.get(sp["name"])

        facing = pa - sp["r"] + PI / 4.0
        while facing < 0:
            facing += PI2
        while facing > PI2:
            facing -= PI2
        if facing < PI_05:
            angle_key = "B"
        elif facing < PI:
            angle_key = "L"
        elif facing < PI_15:
            angle_key = "F"
        else:
            angle_key = "R"
        sp["a"] = angle_key

        mid = horizon_mid(max_rows)
        height_factor = sp_def['height_factor'] if sp_def else 1.0
        aspect_ratio  = sp_def['aspect_ratio']  if sp_def else 1.0
        sprite_ceil  = round(mid - max_rows / dist * height_factor)
        sprite_floor = round(mid + max_rows / dist)
        sprite_h     = sprite_floor - sprite_ceil
        sprite_w     = round(sprite_h / (sp_def['height'] / (sp_def['width'] * aspect_ratio))) if sp_def else 3
        sprite_w     = max(1, sprite_w)

        screen_x = int((0.5 * (sprite_angle / (fov / 2.0)) + 0.5) * num_cols)
        proj_dist = dist * math.cos(sprite_angle)

        tex = _pick_sprite_tex(sp_def, angle_key, anim_timer) if sp_def else None
        is_hit = sp.get("hit_until", 0) > time.time()
        pair = curses.color_pair(9) if is_hit else curses.color_pair(2)

        for sx in range(sprite_w):
            c = screen_x + sx - sprite_w // 2
            if c < 0 or c >= num_cols:
                continue
            if proj_dist > depth_buf[c]:
                continue
            for sy_i in range(max(0, sprite_ceil), min(max_rows - 2, sprite_floor)):
                fsx = sx / sprite_w
                fsy = (sy_i - sprite_ceil) / sprite_h if sprite_h > 0 else 0.0
                if tex:
                    raw_px = assets.sample_raw(tex, fsx, fsy)
                    if raw_px in (' ', '.', '0', '+', '~'):
                        continue
                    pixel = assets.char_to_shade(raw_px)
                    glyph = _shade_wall_pixel(dist, True, pixel)
                else:
                    glyph = sp["name"][0]
                if glyph in (' ', ''):
                    continue
                try:
                    stdscr.addch(sy_i, c, glyph, pair | curses.A_BOLD)
                except curses.error:
                    pass


def draw_tracers(stdscr, px, py, pa, depth_buf, num_cols, max_rows, jump_timer, look_timer,
                 weapon_range=MAX_RENDER_DEPTH, spread=1):
    fov = PI / 2.25

    def horizon_mid(h):
        return h / ((2.0 - jump_timer * 0.15) - look_timer * 0.15)

    mid = horizon_mid(max_rows)

    for tracer in world.ACTIVE_TRACERS:
        tx, ty = tracer[0], tracer[1]
        dx, dy = tx - px, ty - py
        dist = math.sqrt(dx * dx + dy * dy)
        if dist < 0.2 or dist > min(weapon_range, MAX_RENDER_DEPTH):
            continue
        angle = math.atan2(dy, dx) - pa
        while angle < -PI:
            angle += PI2
        while angle > PI:
            angle -= PI2
        if abs(angle) >= fov / 2:
            continue
        col = int((0.5 * (angle / (fov / 2.0)) + 0.5) * num_cols)
        ceiling = mid - max_rows / max(dist, 0.1)
        floor_y = mid + max_rows / max(dist, 0.1)
        row = int((ceiling + floor_y) / 2)
        half = spread // 2
        for offset in range(-half, half + 1):
            c = col + offset
            if 0 <= c < num_cols and dist <= depth_buf[c]:
                if 0 <= row < max_rows - 1:
                    try:
                        stdscr.addch(row, c, '·', curses.color_pair(8) | curses.A_BOLD)
                    except curses.error:
                        pass
