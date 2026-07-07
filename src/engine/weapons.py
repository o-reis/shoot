from dataclasses import dataclass


@dataclass
class Weapon:
    name: str
    damage: int
    reload: float
    range: float
    spread: int = 1


WEAPONS = [
    Weapon("Pistol",  15, 0.4,  12.0, 1),
    Weapon("Shotgun", 40, 1.2,  6.0,  3),
    Weapon("SMG",      4, 0.2, 10.0, 1),
    Weapon("Sniper",  80, 3.0,  50.0, 1),
    Weapon("Knife",   25, 0.8,  2.0,  1),
]
