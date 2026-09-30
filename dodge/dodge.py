# Dodge: the wedgie starter game. Joystick left/right moves your ship; don't get hit by the rocks.
# A starts again. Your best score is saved.
#
# Fork this repo to make your own app: rename the mod and its files (wedgie.json), keep the patterns.
# Every one of them is explained in https://wedgie.dev/code.md:
#   1. The frame goes out by DMA: lcd.show_start() returns at once and the ~18 ms push runs while the
#      next frame's game logic does. lcd.show_wait() before drawing again. (Firmware 0.2.3+, which also
#      runs the screen at 62.5 MHz: wedgie.json says "fw": "0.2.3".)
#   2. An entry loop (wedgie.json "entry": "run") at a fixed frame rate: keys, update, draw, push, sleep.
#      The sleep is when the firmware answers USB.
#   3. Sprites are 4-bit framebufs drawn through a palette: C speed, a quarter of the RAM of RGB565.
#   4. Nothing new is made inside the loop (lists are reused, text only changes when the number does),
#      so the garbage collector never stalls a frame.
#   5. Save at game over, never every frame.
import time, framebuf, random
from lcd import LCD, Keys, color
import save
import ui                               # the wedgie's own look: game over is ui.page (wedgie.dev/code.md)

lcd = LCD()
keys = Keys()
FRAME = 25                                  # ms per frame: 40 fps
BG, INK, DIM = color(8, 10, 24), color(240, 240, 235), color(120, 125, 150)
KEY = color(255, 0, 255)                    # palette slot 0: never drawn (blit's transparent color)


def palette(*rgb):
    p = framebuf.FrameBuffer(bytearray(32), 16, 1, framebuf.RGB565)
    for i, c in enumerate((KEY,) + rgb):
        p.pixel(i, 0, c)
    return p


def sprite(rows):
    """Pixel art as strings: '.' is transparent, 1-9 a palette color. Built once, at import."""
    w, h = len(rows[0]), len(rows)
    fb = framebuf.FrameBuffer(bytearray((w * h + 1) // 2), w, h, framebuf.GS4_HMSB)
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            fb.pixel(x, y, 0 if ch == "." else int(ch))
    return fb


SHIP = sprite([
    ".......11.......",
    "......1221......",
    "......1221......",
    ".....122221.....",
    ".....123321.....",
    "....12333321....",
    "....12333321....",
    "...1222222221...",
    "..122222222221..",
    ".12221222212221.",
    "1222114224112221",
    "122211.44.112221",
    "1111...55...1111",
    ".......55.......",
    "......5..5......",
    "................"])
SHIP_PAL = palette(color(20, 60, 120), color(60, 150, 255), color(200, 240, 255), color(255, 210, 60), color(255, 90, 40))

ROCK = sprite([
    ".....111111.....",
    "...1122222211...",
    "..122223322221..",
    ".12222333322221.",
    ".12232222222221.",
    "1222333222222221",
    "1222222222332221",
    "1222222223333221",
    "1222322222332221",
    "1223332222222221",
    "1222322222222221",
    ".12222222322221.",
    ".12222223332221.",
    "..122222232221..",
    "...1122222211...",
    ".....111111....."])
ROCK_PAL = palette(color(70, 50, 40), color(150, 110, 80), color(200, 160, 120))

W = 16
rocks = [[0, 0, 0] for _ in range(7)]      # x, y, speed: reused forever
stars = [[random.randint(0, 239), random.randint(20, 239), random.randint(1, 3)] for _ in range(30)]
x = 112
score = best = 0
over = False
t0 = 0
shown, score_txt, best_txt = -1, "", ""     # the score text is only rebuilt when the score changes


def reset():
    global x, score, over, t0, shown
    x, score, over, t0, shown = 112, 0, False, time.ticks_ms(), -1
    for i, r in enumerate(rocks):
        r[0], r[1], r[2] = random.randint(0, 240 - W), -40 - i * 36, 2


def update():
    global x, score, over
    if keys.held("left"):
        x = max(0, x - 4)
    if keys.held("right"):
        x = min(240 - W, x + 4)
    level = 2 + time.ticks_diff(time.ticks_ms(), t0) // 8000     # faster every 8 s
    for r in rocks:
        r[1] += r[2]
        if r[1] > 240:
            r[0], r[1], r[2] = random.randint(0, 240 - W), -W - random.randint(0, 60), random.randint(level, level + 2)
            score += 1
        # hit: boxes overlap, 3 px of mercy on each side
        if r[1] + W - 3 > 206 and r[1] + 3 < 222 and r[0] + W - 3 > x and r[0] + 3 < x + W:
            over = True
    for s in stars:
        s[1] += s[2]
        if s[1] > 239:
            s[1] = 20


def draw():
    global shown, score_txt, best_txt
    lcd.fill(BG)
    for s in stars:
        lcd.pixel(s[0], s[1], DIM)
    for r in rocks:
        lcd.blit(ROCK, r[0], r[1], KEY, ROCK_PAL)
    lcd.blit(SHIP, x, 206, KEY, SHIP_PAL)
    if score != shown:
        shown, score_txt, best_txt = score, str(score), "best %d" % best
    lcd.fill_rect(0, 0, 240, 16, 0)
    lcd.text(score_txt, 4, 4, INK)
    lcd.text(best_txt, 236 - 8 * len(best_txt), 4, DIM)


def game_over():
    global best
    if score > best:
        best = score
        try:
            save.store("best", best)
        except OSError:
            pass                        # flash full: play on without saving
    lcd.show_wait()                     # never draw while a frame is going out
    ui.page(lcd, "Game over", [("score %d" % score, ui.INK), ("best %d" % best, ui.MUTED)], "A  play again")
    while "A" not in keys.pressed():
        time.sleep_ms(30)
    reset()


def run():
    global best
    best = save.load("best", 0)
    reset()
    while True:
        t = time.ticks_ms()
        keys.pressed()                  # drop presses we don't use, so they don't pile up
        update()                        # while the last frame is still going out
        lcd.show_wait()                 # the buffer is ours again
        draw()
        lcd.show_start()                # this frame goes out while the next one's update runs
        if over:
            game_over()
        left = FRAME - time.ticks_diff(time.ticks_ms(), t)
        if left > 0:
            time.sleep_ms(left)
