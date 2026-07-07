import logging
import sys
from pathlib import Path

LOG_MODE = 1

_LOG_FILE = Path(__file__).resolve().parent.parent.parent / "net.log"

_logger = logging.getLogger("net")
_logger.propagate = False
_logger.setLevel(logging.DEBUG)

_handler = None

def _ensure_handler():
    global _handler
    if _handler is not None:
        return
    if LOG_MODE == 0:
        _handler = logging.NullHandler()
    elif LOG_MODE == 1:
        _handler = logging.FileHandler(_LOG_FILE, encoding="utf-8")
    else:
        _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(logging.Formatter("%(asctime)s.%(msecs)03d [%(name)s] %(message)s",
                                            datefmt="%H:%M:%S"))
    _logger.addHandler(_handler)

_ensure_handler()


def _log(subsystem: str, direction: str, msg: str):
    if LOG_MODE == 0:
        return
    _logger.debug("[%s] %s %s", subsystem, direction, msg)


def udp_sent(to_ip: str, to_port: int, ptype: str, detail: str = ""):
    _log("UDP", "SEND", f"→ {to_ip}:{to_port}  type={ptype}  {detail}")

def udp_recv(from_ip: str, from_port: int, ptype: str, detail: str = ""):
    _log("UDP", "RECV", f"← {from_ip}:{from_port}  type={ptype}  {detail}")

def grpc_sent(to_addr: str, method: str, detail: str = ""):
    _log("gRPC", "SEND", f"→ {to_addr}  {method}  {detail}")

def grpc_recv(from_addr: str, method: str, detail: str = ""):
    _log("gRPC", "RECV", f"← {from_addr}  {method}  {detail}")

def lan_sent(to_addr: str, detail: str = ""):
    _log("LAN", "SEND", f"→ {to_addr}  {detail}")

def lan_recv(from_ip: str, from_port: int, detail: str = ""):
    _log("LAN", "RECV", f"← {from_ip}:{from_port}  {detail}")
