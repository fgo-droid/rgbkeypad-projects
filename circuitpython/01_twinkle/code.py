import random
import time

import board
import busio
import digitalio


WIDTH = 4
HEIGHT = 4
NUM_PADS = WIDTH * HEIGHT
KEYPAD_ADDRESS = 0x20
BRIGHTNESS = 0.35

PALETTES = (
    ((20, 110, 255), (0, 255, 190), (255, 255, 255)),
    ((255, 42, 82), (255, 180, 25), (255, 245, 190)),
    ((155, 65, 255), (30, 220, 255), (255, 255, 255)),
    ((30, 255, 85), (250, 255, 50), (255, 255, 255)),
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

levels = [0] * NUM_PADS
targets = [0] * NUM_PADS
colors = [PALETTES[0][0] for _ in range(NUM_PADS)]
palette_index = 0
last_buttons = 0
last_palette_change = time.monotonic()


def clamp(value, low=0, high=255):
    return min(high, max(low, value))


def choose_color():
    palette = PALETTES[palette_index]
    return palette[random.randrange(len(palette))]


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


def get_button_states():
    result = bytearray(2)
    while not i2c.try_lock():
        pass
    try:
        i2c.writeto_then_readfrom(KEYPAD_ADDRESS, bytes((0,)), result)
    finally:
        i2c.unlock()
    return (~(result[0] | (result[1] << 8))) & 0xFFFF


def scale_color(rgb, level):
    return (
        (rgb[0] * level) // 255,
        (rgb[1] * level) // 255,
        (rgb[2] * level) // 255,
    )


def sparkle(pad, strength=None):
    if strength is None:
        strength = random.randint(80, 255)
    targets[pad] = strength
    colors[pad] = choose_color()


def fade_step(current, target):
    if current < target:
        return min(target, current + max(4, (target - current) // 3))
    return max(0, current - max(2, current // 10))


while True:
    buttons = get_button_states()
    pressed = buttons & (buttons ^ last_buttons)

    if pressed:
        for pad in range(NUM_PADS):
            if pressed & (1 << pad):
                sparkle(pad, 255)
                x = pad % WIDTH
                y = pad // WIDTH
                for other in range(NUM_PADS):
                    ox = other % WIDTH
                    oy = other // WIDTH
                    if abs(x - ox) + abs(y - oy) == 1:
                        sparkle(other, random.randint(90, 170))

    now = time.monotonic()
    if now - last_palette_change > 9:
        palette_index = (palette_index + 1) % len(PALETTES)
        last_palette_change = now

    if random.random() < 0.22:
        sparkle(random.randrange(NUM_PADS))

    for pad in range(NUM_PADS):
        levels[pad] = fade_step(levels[pad], targets[pad])
        targets[pad] = max(0, targets[pad] - random.randint(8, 24))
        set_led(pad, *scale_color(colors[pad], levels[pad]))

    show()
    last_buttons = buttons
    time.sleep(0.035)
