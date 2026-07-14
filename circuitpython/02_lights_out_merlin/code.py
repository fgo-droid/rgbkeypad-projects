import random
import time

import board
import busio
import digitalio


WIDTH = 4
HEIGHT = 4
NUM_PADS = WIDTH * HEIGHT
FULL_BOARD = (1 << NUM_PADS) - 1
KEYPAD_ADDRESS = 0x20
BRIGHTNESS = 0.35

OFF_COLOR = (0, 0, 0)
ON_COLOR = (0, 170, 255)
PRESS_COLOR = (255, 255, 255)
START_COLOR = (255, 140, 25)
WIN_COLOR = (20, 255, 110)
PERFECT_COLOR = (255, 210, 40)
MISS_COLOR = (255, 35, 55)

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


def xy_to_pad(x, y):
    return x + (y * WIDTH)


def build_target_board():
    target = 0
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if x == 0 or x == WIDTH - 1 or y == 0 or y == HEIGHT - 1:
                target |= 1 << xy_to_pad(x, y)
    return target


TARGET_BOARD = build_target_board()


def set_led(pad, r, g, b):
    offset = 4 + (pad * 4)
    led_buffer[offset + 1] = clamp(b)
    led_buffer[offset + 2] = clamp(g)
    led_buffer[offset + 3] = clamp(r)


def clear_leds():
    for pad in range(NUM_PADS):
        set_led(pad, 0, 0, 0)


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
    return (~(result[0] | (result[1] << 8))) & FULL_BOARD


def build_toggle_masks():
    masks = []
    for pad in range(NUM_PADS):
        x = pad % WIDTH
        y = pad // WIDTH
        mask = 0

        # Merlin Magic Square rule adapted to 4x4: a button reverses itself
        # and all adjacent buttons, including diagonals.
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                nx = x + dx
                ny = y + dy
                if 0 <= nx < WIDTH and 0 <= ny < HEIGHT:
                    mask |= 1 << xy_to_pad(nx, ny)

        masks.append(mask)
    return masks


TOGGLE_MASKS = build_toggle_masks()


def popcount(value):
    count = 0
    while value:
        value &= value - 1
        count += 1
    return count


def board_after_presses(press_mask):
    board = 0
    for pad in range(NUM_PADS):
        if press_mask & (1 << pad):
            board ^= TOGGLE_MASKS[pad]
    return board


def best_solution_length(start_board):
    best = NUM_PADS + 1
    for press_mask in range(1 << NUM_PADS):
        moves = popcount(press_mask)
        if moves >= best:
            continue

        result = start_board ^ board_after_presses(press_mask)
        if result == TARGET_BOARD:
            best = moves

    return best


def draw_board(board, flash_pad=-1, flash_color=PRESS_COLOR):
    for pad in range(NUM_PADS):
        if pad == flash_pad:
            set_led(pad, *flash_color)
        elif board & (1 << pad):
            set_led(pad, *ON_COLOR)
        else:
            set_led(pad, *OFF_COLOR)
    show()


def wait_for_release():
    while get_button_states():
        time.sleep(0.02)


def startup_animation():
    clear_leds()
    show()
    for pad in range(NUM_PADS):
        set_led(pad, *START_COLOR)
        show()
        time.sleep(0.025)
    draw_board(TARGET_BOARD)
    time.sleep(0.65)
    clear_leds()
    show()
    time.sleep(0.12)


def pulse(color, repeats=2, delay=0.055):
    for _ in range(repeats):
        for level in (0.2, 0.45, 0.75, 1.0, 0.6, 0.25, 0):
            for pad in range(NUM_PADS):
                set_led(
                    pad,
                    color[0] * level,
                    color[1] * level,
                    color[2] * level,
                )
            show()
            time.sleep(delay)


def perfect_reward():
    for cycle in range(28):
        for pad in range(NUM_PADS):
            sparkle = 1.0 if random.random() < 0.35 else 0.25
            wave = 0.35 + (((pad + cycle) % WIDTH) / 5)
            level = min(1.0, sparkle * wave)
            set_led(
                pad,
                PERFECT_COLOR[0] * level,
                PERFECT_COLOR[1] * level,
                PERFECT_COLOR[2] * level,
            )
        show()
        time.sleep(0.045)
    pulse(PERFECT_COLOR, repeats=2)


def win_animation(perfect):
    if perfect:
        perfect_reward()
    else:
        pulse(WIN_COLOR, repeats=3)


def too_many_moves_hint():
    for pad in range(NUM_PADS):
        set_led(pad, *MISS_COLOR)
    show()
    time.sleep(0.08)


def make_puzzle():
    while True:
        presses = 0
        for _ in range(random.randint(3, 9)):
            presses ^= 1 << random.randrange(NUM_PADS)

        board = TARGET_BOARD ^ board_after_presses(presses)
        if board != TARGET_BOARD:
            best = best_solution_length(board)
            if 3 <= best <= 9:
                return board, best


startup_animation()

while True:
    board, minimum_moves = make_puzzle()
    moves = 0
    draw_board(board)
    wait_for_release()

    while board != TARGET_BOARD:
        buttons = get_button_states()
        if not buttons:
            time.sleep(0.015)
            continue

        for pad in range(NUM_PADS):
            if buttons & (1 << pad):
                board ^= TOGGLE_MASKS[pad]
                moves += 1
                draw_board(board, flash_pad=pad)
                time.sleep(0.09)
                draw_board(board)

                if moves == minimum_moves + 1 and board != TARGET_BOARD:
                    too_many_moves_hint()
                    draw_board(board)
                break

        wait_for_release()

    win_animation(moves == minimum_moves)
    time.sleep(0.5)
