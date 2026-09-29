# Hi-Lo: is the next card higher or lower? The deck is shuffled by the secure chip's hardware random
# generator (wedgie.rand_below), and the screen says which chip did it. Joystick up: higher, down: lower.
# A tie is a free pass. One wrong guess ends the streak; A deals a fresh deck. Best streak is saved.
#
# Patterns worth copying (https://wedgie.dev/code.md):
#   - Randomness that matters comes from the chip: wedgie.rand_below(n) is fair (no modulo bias) and
#     reads the Trust M or ATECC608's true random generator. wedgie.rand_source() says where it came
#     from; with no chip it's the Pico's own generator, and the game says that too.
#   - Nothing moves between key presses, so it only draws and pushes the screen when something changes.
import time, framebuf
from lcd import LCD, Keys, color
import save
from wedgie import rand_below, rand_source

lcd = LCD()
keys = Keys()
FELT, FELT_D, INK, WHITE = color(18, 110, 60), color(10, 70, 38), color(26, 27, 26), color(254, 254, 250)
RED, GOLD, BACK, BACK_D = color(210, 40, 40), color(255, 210, 60), color(40, 70, 170), color(25, 45, 120)
KEY = color(255, 0, 255)
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]

SUITS = [  # 12x12, drawn at 2x: hearts, diamonds, clubs, spades
    ["............", ".11......11.", "1111....1111", "111111111111", "111111111111", "111111111111",
     ".1111111111.", "..11111111..", "...111111...", "....1111....", ".....11.....", "............"],
    [".....11.....", "....1111....", "...111111...", "..11111111..", ".1111111111.", "111111111111",
     ".1111111111.", "..11111111..", "...111111...", "....1111....", ".....11.....", "............"],
    ["....1111....", "...111111...", "...111111...", "....1111....", ".11..11..11.", "111111111111",
     "111111111111", ".11..11..11.", ".....11.....", "....1111....", "...111111...", "............"],
    [".....11.....", "....1111....", "...111111...", "..11111111..", ".1111111111.", "111111111111",
     "111111111111", ".1111111111.", "..11.11.11..", ".....11.....", "....1111....", "............"],
]


def suit_sprite(rows, s):
    fb = framebuf.FrameBuffer(bytearray(12 * s * 12 * s // 2), 12 * s, 12 * s, framebuf.GS4_HMSB)
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            if ch == "1":
                fb.fill_rect(x * s, y * s, s, s, 1)
    return fb


BIG = [suit_sprite(r, 3) for r in SUITS]       # 36x36, the middle of the card
SMALL = [suit_sprite(r, 1) for r in SUITS]     # 12x12, its corner
PALS = []
for c in (RED, RED, INK, INK):
    p = framebuf.FrameBuffer(bytearray(4), 2, 1, framebuf.RGB565)
    p.pixel(0, 0, KEY); p.pixel(1, 0, c)
    PALS.append(p)

deck = list(range(52))                         # card = rank * 4 + suit
pos = 0                                        # the next card to deal
cur = nxt = 0
streak = best = 0
state = "guess"                                # guess | shown | over
msg = ""
source = ""


def shuffle():
    """Fisher-Yates, every swap chosen by the chip: all 52! orders equally likely."""
    global pos
    for i in range(51, 0, -1):
        j = rand_below(i + 1)
        deck[i], deck[j] = deck[j], deck[i]
    pos = 0


def deal():
    global pos
    if pos >= 52:
        shuffle()
    pos += 1
    return deck[pos - 1]


def card(x, y, c):
    lcd.fill_rect(x + 2, y + 2, 84, 116, FELT_D)             # shadow
    lcd.fill_rect(x, y, 84, 116, WHITE)
    lcd.rect(x, y, 84, 116, INK)
    rank, suit = c // 4, c % 4
    col = RED if suit < 2 else INK
    lcd.big_text(RANKS[rank], x + 6, y + 6, col, 2)
    lcd.blit(SMALL[suit], x + 6, y + 24, KEY, PALS[suit])
    lcd.blit(BIG[suit], x + 24, y + 50, KEY, PALS[suit])


def back(x, y):
    lcd.fill_rect(x + 2, y + 2, 84, 116, FELT_D)
    lcd.fill_rect(x, y, 84, 116, BACK)
    lcd.rect(x + 5, y + 5, 74, 106, BACK_D)
    for i in range(10, 110, 10):
        lcd.hline(x + 8, y + i, 68, BACK_D)
    lcd.big_text("?", x + 34, y + 48, GOLD, 2)


def draw():
    lcd.fill(FELT)
    lcd.fill_rect(0, 0, 240, 22, FELT_D)
    lcd.text("HI-LO", 6, 7, GOLD)
    s = "streak %d  best %d" % (streak, best)
    lcd.text(s, 234 - 8 * len(s), 7, WHITE)
    card(22, 40, cur)
    if state == "guess":
        back(134, 40)
    else:
        card(134, 40, nxt)
    lcd.center_text(msg, 170, GOLD if state != "over" else WHITE)
    lcd.center_text("A: new deck" if state == "over" else "up: higher  down: lower", 190, WHITE)
    lcd.fill_rect(0, 214, 240, 26, FELT_D)
    lcd.center_text("shuffled by", 216, color(150, 200, 170))
    lcd.center_text(source[:29], 227, WHITE)
    lcd.show()                                  # only when something changed: nothing moves in between


def new_game():
    global cur, nxt, streak, state, msg, source
    lcd.fill(FELT)
    lcd.center_text("shuffling...", 112, WHITE, 2)
    lcd.show()
    shuffle()
    source = rand_source()
    print("shuffled by", source)
    cur, streak, state, msg = deal(), 0, "guess", "higher or lower?"
    draw()


def guess(up):
    global nxt, cur, streak, best, state, msg
    nxt = deal()
    a, b = cur // 4, nxt // 4
    if a == b:
        msg = "same: a free pass"
    elif (b > a) == up:
        streak += 1
        msg = "right!"
    else:
        state, msg = "over", "wrong: %s is %s" % (RANKS[b], "lower" if up else "higher")
        if streak > best:
            best = streak
            try:
                save.store("best", best)
            except OSError:
                pass
        draw()
        return
    state = "shown"
    draw()
    time.sleep_ms(700)
    cur, state, msg = nxt, "guess", "higher or lower?"
    draw()


def run():
    global best
    best = save.load("best", 0)
    new_game()
    while True:
        for k in keys.pressed():
            if state == "guess" and k in ("up", "down"):
                guess(k == "up")
            elif state == "over" and k == "A":
                new_game()
        time.sleep_ms(30)
