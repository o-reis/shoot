import sys
import asyncio
import logging
import random
import curses
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

_generated_path = Path(__file__).resolve().parent / "network" / "generated"
sys.path.append(str(_generated_path))

logging.getLogger("grpc").setLevel(logging.CRITICAL)
logging.getLogger("grpc._channel").setLevel(logging.CRITICAL)

_DATA_DIR = Path.home() / ".shoot"
_DATA_DIR.mkdir(exist_ok=True)
_GENERATED_MAP = str(_DATA_DIR / "generated.map")

from src.engine import game_loop
from src.engine import world
from src.map.map_generator import generate_map
from src.ui.screens import init_colors, prompt_player_name, show_main_menu, MENU_ITEMS
from src.network.lobby import host_match, join_public, join_private, host_rematch, join_rematch
from src.network.matchmaking_helpers import get_local_ip

P2P_PORT = 50152


def _load_or_create_player_id() -> int:
    id_file = Path.home() / ".shoot_id"
    if id_file.exists():
        try:
            return int(id_file.read_text().strip())
        except ValueError:
            pass
    pid = random.randint(1, 10 ** 8 - 1)
    id_file.write_text(str(pid))
    return pid


PLAYER_ID = _load_or_create_player_id()


def run_game(stdscr, peers, map_seed, player_name, is_host=False):
    curses.endwin()
    generate_map(map_seed, outpath=_GENERATED_MAP)
    world.load_level(_GENERATED_MAP)
    return game_loop.game(
        stdscr,
        map_path=_GENERATED_MAP,
        peers=peers,
        player_id=PLAYER_ID,
        player_name=player_name,
        local_port=P2P_PORT,
        map_seed=map_seed,
        is_host=is_host,
    )


def _run_rematch_loop(stdscr, result, peers, player_name, is_host, host_ip):
    while result == "rematch":
        if is_host:
            node, peers, seed = asyncio.run(
                host_rematch(stdscr, PLAYER_ID, player_name, len(peers))
            )
        else:
            node, peers, seed = asyncio.run(
                join_rematch(stdscr, PLAYER_ID, player_name, host_ip)
            )
        if peers is None:
            return None
        result = run_game(stdscr, peers, seed, player_name, is_host=is_host)
        if node:
            node.stop()
    return result


def main(stdscr):
    init_colors()
    stdscr.nodelay(False)

    player_name = prompt_player_name(stdscr)

    while True:
        choice = show_main_menu(stdscr)

        if choice == -1 or choice == len(MENU_ITEMS) - 1:
            return

        if choice == 0:
            node, peers, seed, host_ip = asyncio.run(host_match(stdscr, PLAYER_ID, player_name))
            if peers is not None:
                result = run_game(stdscr, peers, seed, player_name, is_host=True)
                if node:
                    node.stop()
                result = _run_rematch_loop(stdscr, result, peers, player_name, is_host=True, host_ip=host_ip)
                if result is True:
                    return

        elif choice == 1:
            node, peers, seed, host_ip = asyncio.run(join_public(stdscr, PLAYER_ID, player_name))
            if peers is not None:
                result = run_game(stdscr, peers, seed, player_name, is_host=False)
                if node:
                    node.stop()
                result = _run_rematch_loop(stdscr, result, peers, player_name, is_host=False, host_ip=host_ip)
                if result is True:
                    return

        elif choice == 2:
            node, peers, seed, host_ip = asyncio.run(join_private(stdscr, PLAYER_ID, player_name))
            if peers is not None:
                result = run_game(stdscr, peers, seed, player_name, is_host=False)
                if node:
                    node.stop()
                result = _run_rematch_loop(stdscr, result, peers, player_name, is_host=False, host_ip=host_ip)
                if result is True:
                    return

        elif choice == 3:
            result = run_game(stdscr, [], str(random.randint(1, 10**8-1)), player_name, is_host=False)
            if result is True:
                return


if __name__ == "__main__":
    curses.wrapper(main)
