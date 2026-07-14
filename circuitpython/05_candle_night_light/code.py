import random
import time

import board
import busio
import digitalio


WIDTH = 4
HEIGHT = 4
NUM_PADS = WIDTH * HEIGHT
KEYPAD_ADDRESS = 0x20

# Durations are intentionally short enough to test. Raise to 20 * 60 or
# 30 * 60 for a real bedtime fade-out.
FADE_OUT_SECONDS = 10 * 60
STEP_SECONDS = 0.055

BRIGHTNESS_LEVELS = (0.18, 0.28, 0.42)
brightness_index = 1

i2c = busio.I2C(scl=board.GP5, sda=board.GP4, frequency=400000)
spi = busio.SPI(clock=board.GP18, MOSI=board.GP19)
cs = digitalio.DigitalInOut(board.GP17)
cs.direction = digitalio.Direction.OUTPUT
cs.value = True

# APA102 packet: 4-byte start frame, 4 bytes per LED, 4-byte end frame.
led_buffer = bytearray(4 + (NUM_PADS * 4) + 4)


def clamp(value, low=0, high=255):
    return min(high, max(low, int(value)))


def set_brightness(brightness):
    byte = 0b11100000 | int(max(0, min(1, brightness)) * 31)
    for pad in range(NUM_PADS):
        led_buffer[4 + (pad * 4)] = byte


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


def button_hold_seconds():
    if not get_button_states():
        return 0

    start = time.monotonic()
    while get_button_states():
        time.sleep(0.02)
    return time.monotonic() - start


def candle_color(level, warmth, ember):
    red = 255 * level
    green = (92 + warmth * 88) * level
    blue = (3 + ember * 22) * level
    return red, green, blue


def draw_candle(master_level=1.0):
    for pad in range(NUM_PADS):
        row = pad // WIDTH
        column = pad % WIDTH

        base = 0.50 + (HEIGHT - 1 - row) * 0.07
        centre_boost = 0.12 if column in (1, 2) else 0.0
        flutter = random.uniform(-0.15, 0.20)
        occasional_spark = 0.22 if random.random() < 0.035 else 0.0

        level = max(0.03, min(1.0, base + centre_boost + flutter + occasional_spark))
        level *= master_level

        warmth = random.random()
        ember = random.random()
        set_led(pad, *candle_color(level, warmth, ember))

    show()


def breathe_feedback():
    for level in (0.25, 0.55, 0.85, 0.55, 0.25):
        for pad in range(NUM_PADS):
            set_led(pad, 255 * level, 150 * level, 20 * level)
        show()
        time.sleep(0.08)


def fade_out():
    start = time.monotonic()
    while True:
        elapsed = time.monotonic() - start
        remaining = max(0, 1 - (elapsed / FADE_OUT_SECONDS))
        draw_candle(remaining)

        if remaining <= 0:
            break

        if get_button_states():
            wait_for_release()
            breathe_feedback()
            return

        time.sleep(STEP_SECONDS)

    clear_leds()
    while True:
        if get_button_states():
            wait_for_release()
            breathe_feedback()
            return
        time.sleep(0.1)


set_brightness(BRIGHTNESS_LEVELS[brightness_index])
breathe_feedback()

while True:
    draw_candle()

    hold = button_hold_seconds()
    if hold > 1.0:
        breathe_feedback()
        fade_out()
        set_brightness(BRIGHTNESS_LEVELS[brightness_index])
    elif hold > 0:
        brightness_index = (brightness_index + 1) % len(BRIGHTNESS_LEVELS)
        set_brightness(BRIGHTNESS_LEVELS[brightness_index])
        breathe_feedback()

    time.sleep(STEP_SECONDS)
