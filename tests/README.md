# Tests

Unit tests for the pure-logic and side-effect-free parts of the project: weapons, player, safe zone, map generation, world collision and spawns, the UDP packet codec, and the `kademlia-dynamic` DHT helpers. Curses rendering and live network I/O are not covered here, since they need a terminal and open sockets.

## Running

```bash
pip install pytest
python -m pytest tests/ -q
```

`conftest.py` puts the repository root, `src/`, and `src/network/generated/` on `sys.path` so the tests can import the modules the same way the running game does.
