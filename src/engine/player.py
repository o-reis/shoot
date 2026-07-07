import math
import time


class Player:
    def __init__(self, x, y, angle, hp=100, model='P'):
        self.x = x
        self.y = y
        self.angle = angle
        self.hp = hp
        self.model = model
        self.jump_timer = 0
        self.look_timer = 0.0
        self.hit_until = 0.0

    def move(self, dx, dy):
        self.x += dx
        self.y += dy

    def rotate(self, delta):
        self.angle += delta
        self.angle %= (2.0 * math.pi)

    def take_damage(self, amount):
        self.hp = max(0, self.hp - amount)
        self.hit_until = time.time() + 0.4
