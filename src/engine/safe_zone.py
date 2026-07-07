import time

DAMAGE_INTERVAL_SECONDS = 2.0

LOW_PHASE_SHRINKS = 8
MID_PHASE_SHRINKS = 15
HIGH_PHASE_SHRINKS = 20

DPS_LOW = 1
DPS_MID = 2
DPS_HIGH = 5
DPS_MAX = 10


class SafeZone:
    def __init__(self, x, y, width, height):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.active = False
        self.shrink_count = 0
        self.last_damage_time = time.time()

    def is_safe(self, px, py):
        if not self.active:
            return True
        return (self.x <= px <= self.x + self.width and
                self.y <= py <= self.y + self.height)

    def dps(self):
        if self.shrink_count >= HIGH_PHASE_SHRINKS:
            return DPS_MAX
        if self.shrink_count >= MID_PHASE_SHRINKS:
            return DPS_HIGH
        if self.shrink_count >= LOW_PHASE_SHRINKS:
            return DPS_MID
        return DPS_LOW

    def shrink(self, amount=1.0):
        self.active = True
        if self.width <= 0:
            return
        if self.width > 2 and self.height > 2:
            self.x += amount / 2
            self.y += amount / 2
            self.width -= amount
            self.height -= amount
            self.shrink_count += 1

    def update_damage(self, player):
        if not self.active:
            return
        now = time.time()
        if now - self.last_damage_time >= DAMAGE_INTERVAL_SECONDS:
            if not self.is_safe(player.x, player.y):
                player.take_damage(self.dps())
            self.last_damage_time = now
