import asyncio
import curses

from src.network.matchmaking import start_scan

MENU_ITEMS = [
    "Host Match",
    "Join Match (Public)",
    "Join Match (Private Key)",
    "Play Solo",
    "Exit",
]


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(5, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(8, curses.COLOR_RED,   curses.COLOR_BLACK)


def draw_screen(stdscr, title, lines, hint=None):
    stdscr.erase()
    max_rows, max_cols = stdscr.getmaxyx()
    try:
        stdscr.addstr(max_rows // 2 - len(lines) // 2 - 2,
                      max(0, (max_cols - len(title)) // 2),
                      title, curses.color_pair(2) | curses.A_BOLD)
    except curses.error:
        pass
    for i, (text, pair, bold) in enumerate(lines):
        row  = max_rows // 2 - len(lines) // 2 + i
        attr = curses.color_pair(pair) | (curses.A_BOLD if bold else 0)
        try:
            stdscr.addstr(row, max(0, (max_cols - len(text)) // 2), text, attr)
        except curses.error:
            pass
    if hint:
        try:
            stdscr.addstr(max_rows - 2, max(0, (max_cols - len(hint)) // 2),
                          hint, curses.color_pair(5))
        except curses.error:
            pass
    stdscr.refresh()


def show_status(stdscr, title, lines):
    draw_screen(stdscr, title, [(l, 5, False) for l in lines])


def show_lobby_wait(stdscr, title, static_lines, players, hint="ENTER to start   ESC to cancel"):
    lines = [(l, 5, False) for l in static_lines]
    lines.append(("", 2, False))
    lines.append(("Players in lobby:", 2, True))
    for p in players:
        lines.append((f"  {p}", 2, False))
    draw_screen(stdscr, title, lines, hint=hint)


def prompt_text(stdscr, title, prompt, max_len=30):
    curses.curs_set(1)
    chars = []
    while True:
        display = "".join(chars)
        draw_screen(stdscr, title, [
            (prompt, 5, False),
            (display + "_", 2, False),
        ], hint="ENTER to confirm   ESC to cancel")
        key = stdscr.getch()
        if key in (curses.KEY_ENTER, 10, 13):
            curses.curs_set(0)
            return "".join(chars).strip()
        elif key == 27:
            curses.curs_set(0)
            return ""
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            if chars:
                chars.pop()
        elif 32 <= key <= 126 and len(chars) < max_len:
            chars.append(chr(key))


def pick_from_list(stdscr, title, items, hint="UP/DOWN   ENTER to select   ESC to cancel"):
    selected = 0
    while True:
        lines = []
        for i, item in enumerate(items):
            prefix = "> " if i == selected else "  "
            pair   = 8 if i == selected else 2
            lines.append((prefix + item, pair, i == selected))
        draw_screen(stdscr, title, lines, hint=hint)
        key = stdscr.getch()
        if key in (curses.KEY_UP, ord('w'), ord('W')):
            selected = (selected - 1) % len(items)
        elif key in (curses.KEY_DOWN, ord('s'), ord('S')):
            selected = (selected + 1) % len(items)
        elif key in (curses.KEY_ENTER, 10, 13):
            return selected
        elif key == 27:
            return -1


async def scan_with_spinner(stdscr, title, label, timeout=10.0, tick=0.25):
    _SPINNER = ('|', '/', '-', '\\')
    scanner = await start_scan()
    stdscr.nodelay(True)
    elapsed = 0.0
    frame   = 0
    while elapsed < timeout:
        peers = scanner.get_peers()
        spin  = _SPINNER[frame % len(_SPINNER)]
        peer_lines = [(f"  {ip}:{port}", 3, False) for ip, port in peers]
        found_line = (f"Found: {len(peers)} host(s)", 4, False) if peers else (f"{spin}  searching...  {spin}", 2, False)
        draw_screen(stdscr, title, [
            (label, 5, False),
            found_line,
            *peer_lines,
            (f"({int(elapsed)}s / {int(timeout)}s)", 2, False),
        ], hint="ESC to cancel  ENTER to use found hosts")
        key = stdscr.getch()
        if key == 27:
            stdscr.nodelay(False)
            return None
        if key in (10, 13) and peers:
            stdscr.nodelay(False)
            return peers
        await asyncio.sleep(tick)
        elapsed += tick
        frame   += 1
    stdscr.nodelay(False)
    return scanner.get_peers() or []


def prompt_player_name(stdscr) -> str:
    init_colors()
    curses.curs_set(1)
    stdscr.nodelay(False)
    chars = []
    while True:
        display = "".join(chars)
        draw_screen(stdscr, " S H O O T", [
            ("Enter your name:", 5, False),
            (display, 2, False),
        ])
        key = stdscr.getch()
        if key in (curses.KEY_ENTER, 10, 13):
            result = "".join(chars).strip()
            if result:
                curses.curs_set(0)
                return result
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            if chars:
                chars.pop()
        elif 32 <= key <= 126 and len(chars) < 20:
            chars.append(chr(key))


def show_main_menu(stdscr) -> int:
    curses.curs_set(0)
    stdscr.nodelay(False)
    init_colors()
    return pick_from_list(stdscr, " S H O O T", MENU_ITEMS,
                          hint="UP/DOWN to select   ENTER to confirm")
