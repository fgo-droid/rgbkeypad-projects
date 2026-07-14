import random
import time

import board
import busio
import digitalio


WIDTH = 4
HEIGHT = 4
NUM_PADS = WIDTH * HEIGHT
KEYPAD_ADDRESS = 0x20
BRIGHTNESS = 0.34
PREVIEW_HOLD_SECONDS = 3.0
MISS_HOLD_SECONDS = 1.35
MATCH_FLASH_SECONDS = 0.12

HIDDEN_COLOR = (0, 8, 18)
SELECT_COLOR = (255, 255, 255)
MISS_COLOR = (255, 35, 55)
WIN_COLOR = (255, 220, 70)

PAIR_COLORS = (
    (20, 90, 255),
    (0, 210, 255),
    (0, 230, 130),
    (180, 255, 35),
    (255, 210, 25),
    (255, 120, 25),
    (255, 45, 75),
    (205, 70, 255),
)

i2c = busio.I2C(scl=board.GP5, sda=board.GP4, frequency=400000)
spi = busio.SPI(clock=board.GP18, MOSI=board.GP19)
cs = digitalio.DigitalInOut(board.GP17)
cs.direction = digitalio.Direction.OUTPUT
cs.value = True

# APA102 packet: 4-byte start frame, 4 bytes per LED, 4-byte end frame.
led_buffer = bytearray(4 + (NUM_PADS * 4) + 4)
brightness_byte = 0b11100000 | int(max(0, min(1, BRIGHTNESS)) * 31)

for pad in range(NUM_PADS):
    led_buffer[4 + (pad * 4)] = brightness_byte


def clamp(value, low=0, high=255):
    return min(high, max(low, int(value)))


def set_led(pad, r, g, b):
    offset = 4 + (pad * 4)
    led_buffer[offset + 1] = clamp(b)
    led_buffer[offset + 2] = clamp(g)
    led_buffer[offset + 3] = clamp(r)


def show():
    while not spi.try_lock():
        pass
    try:
        spi.configure(baudrate=4_000_000, phase=0, polarity=0)
        cs.value = False
        spi.write(led_buffer)
        cs.value = True
    finally:
        spi.unlock()


def clear_leds():
    for pad in range(NUM_PADS):
        set_led(pad, 0, 0, 0)
    show()


def get_button_states():
    result = bytearray(2)
    while not i2c.try_lock():
        pass
    try:
        i2c.writeto_then_readfrom(KEYPAD_ADDRESS, bytes((0,)), result)
    finally:
        i2c.unlock()
    return (~(result[0] | (result[1] << 8))) & 0xFFFF


def wait_for_release():
    while get_button_states():
        time.sleep(0.02)


def first_pressed_pad(buttons):
    for pad in range(NUM_PADS):
        if buttons & (1 << pad):
            return pad
    return -1


def make_deck():
    deck = list(PAIR_COLORS) + list(PAIR_COLORS)
    for index in range(len(deck) - 1, 0, -1):
        swap = random.randrange(index + 1)
        deck[index], deck[swap] = deck[swap], deck[index]
    return deck


def draw_board(deck, revealed, selected=(), flash_color=None):
    selected = tuple(selected)
    for pad in range(NUM_PADS):
        if flash_color is not None and pad in selected:
            set_led(pad, *flash_color)
        elif revealed[pad] or pad in selected:
            set_led(pad, *deck[pad])
        else:
            set_led(pad, *HIDDEN_COLOR)
    show()


def pulse_hidden(deck, revealed):
    for level in (0.15, 0.35, 0.65, 1.0, 0.45, 0.2):
        for pad in range(NUM_PADS):
            if revealed[pad]:
                color = deck[pad]
            else:
                color = HIDDEN_COLOR
            set_led(pad, color[0] * level, color[1] * level, color[2] * level)
        show()
        time.sleep(0.055)


def preview(deck):
    clear_leds()
    time.sleep(0.15)
    for pad in range(NUM_PADS):
        set_led(pad, *deck[pad])
        show()
        time.sleep(0.08)
    time.sleep(PREVIEW_HOLD_SECONDS)
    clear_leds()
    time.sleep(0.35)


def miss_animation(deck, revealed, pads):
    draw_board(deck, revealed, selected=pads, flash_color=MISS_COLOR)
    time.sleep(0.25)
    draw_board(deck, revealed, selected=pads)
    time.sleep(MISS_HOLD_SECONDS)


def match_animation(deck, revealed, pads):
    for _ in range(2):
        draw_board(deck, revealed, selected=pads, flash_color=SELECT_COLOR)
        time.sleep(MATCH_FLASH_SECONDS)
        draw_board(deck, revealed, selected=pads)
        time.sleep(MATCH_FLASH_SECONDS)


def win_animation(deck):
    for sweep in range(24):
        for pad in range(NUM_PADS):
            if random.random() < 0.25:
                color = WIN_COLOR
            else:
                color = deck[(pad + sweep) % NUM_PADS]
            set_led(pad, *color)
        show()
        time.sleep(0.055)
    clear_leds()


def new_game():
    deck = make_deck()
    revealed = [False] * NUM_PADS
    preview(deck)
    pulse_hidden(deck, revealed)
    draw_board(deck, revealed)
    return deck, revealed


deck, revealed = new_game()
selection = []

while True:
    buttons = get_button_states()
    pad = first_pressed_pad(buttons)

    if pad < 0:
        time.sleep(0.02)
        continue

    if not revealed[pad] and pad not in selection:
        selection.append(pad)
        draw_board(deck, revealed, selected=selection)

        if len(selection) == 2:
            first, second = selection
            if deck[first] == deck[second]:
                revealed[first] = True
                revealed[second] = True
                match_animation(deck, revealed, selection)
            else:
                miss_animation(deck, revealed, selection)

            selection = []
            draw_board(deck, revealed)

            if all(revealed):
                win_animation(deck)
                deck, revealed = new_game()

    wait_for_release()
