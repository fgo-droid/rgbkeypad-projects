import random
import time

import board
import busio
import digitalio


WIDTH = 4
HEIGHT = 4
NUM_PADS = WIDTH * HEIGHT
KEYPAD_ADDRESS = 0x20
BRIGHTNESS = 0.36
WIN_EXPONENT = 11  # 2 ** 11 == 2048

EMPTY_COLOR = (0, 0, 0)
PRESS_COLOR = (255, 255, 255)
SPAWN_COLOR = (255, 255, 255)
MERGE_COLOR = (255, 245, 190)
WIN_COLOR = (255, 210, 40)
GAME_OVER_COLOR = (255, 35, 55)

# Board stores exponents: 0 = empty, 1 = 2, 2 = 4, 3 = 8, ...
VALUE_COLORS = (
    EMPTY_COLOR,
    (20, 70, 255),     # 2
    (0, 190, 255),     # 4
    (0, 235, 150),     # 8
    (170, 255, 40),    # 16
    (255, 215, 25),    # 32
    (255, 125, 25),    # 64
    (255, 45, 65),     # 128
    (230, 45, 255),    # 256
    (130, 80, 255),    # 512
    (230, 245, 255),   # 1024
    (255, 230, 80),    # 2048
    (255, 255, 255),   # beyond
)

UP_KEYS = (1, 2)
DOWN_KEYS = (13, 14)
LEFT_KEYS = (4, 8)
RIGHT_KEYS = (7, 11)

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


def color_for_value(value):
    if value < len(VALUE_COLORS):
        return VALUE_COLORS[value]
    return VALUE_COLORS[-1]


def draw_board(board, flash_pads=(), flash_color=PRESS_COLOR, level=1.0):
    flash_pads = tuple(flash_pads)
    for pad in range(NUM_PADS):
        if pad in flash_pads:
            color = flash_color
        else:
            color = color_for_value(board[pad])
        set_led(pad, color[0] * level, color[1] * level, color[2] * level)
    show()


def pulse_pads(board, pads, color, times=1, delay=0.04):
    for _ in range(times):
        draw_board(board, flash_pads=pads, flash_color=color)
        time.sleep(delay)
        draw_board(board)
        time.sleep(delay)


def startup_animation():
    clear_leds()
    for value in range(1, min(WIN_EXPONENT, len(VALUE_COLORS) - 1) + 1):
        color = color_for_value(value)
        for pad in range(NUM_PADS):
            set_led(pad, *color)
        show()
        time.sleep(0.055)
    clear_leds()
    time.sleep(0.12)


def compress_and_merge(line):
    compact = [value for value in line if value]
    result = []
    merged_indices = []
    i = 0

    while i < len(compact):
        if i + 1 < len(compact) and compact[i] == compact[i + 1]:
            result.append(compact[i] + 1)
            merged_indices.append(len(result) - 1)
            i += 2
        else:
            result.append(compact[i])
            i += 1

    while len(result) < WIDTH:
        result.append(0)

    return result, merged_indices


def read_line(board, direction, index):
    if direction == "left":
        return [board[xy_to_pad(x, index)] for x in range(WIDTH)]
    if direction == "right":
        return [board[xy_to_pad(x, index)] for x in range(WIDTH - 1, -1, -1)]
    if direction == "up":
        return [board[xy_to_pad(index, y)] for y in range(HEIGHT)]
    return [board[xy_to_pad(index, y)] for y in range(HEIGHT - 1, -1, -1)]


def write_line(board, direction, index, line):
    pads = []
    for offset, value in enumerate(line):
        if direction == "left":
            pad = xy_to_pad(offset, index)
        elif direction == "right":
            pad = xy_to_pad(WIDTH - 1 - offset, index)
        elif direction == "up":
            pad = xy_to_pad(index, offset)
        else:
            pad = xy_to_pad(index, HEIGHT - 1 - offset)
        board[pad] = value
        pads.append(pad)
    return pads


def move(board, direction):
    original = board[:]
    merged_pads = []

    for index in range(WIDTH):
        old_line = read_line(original, direction, index)
        new_line, merged_indices = compress_and_merge(old_line)
        pads = write_line(board, direction, index, new_line)
        for merged_index in merged_indices:
            merged_pads.append(pads[merged_index])

    return board != original, merged_pads


def empty_pads(board):
    return [pad for pad, value in enumerate(board) if value == 0]


def spawn_tile(board):
    empties = empty_pads(board)
    if not empties:
        return -1

    pad = empties[random.randrange(len(empties))]
    board[pad] = 2 if random.random() < 0.1 else 1
    return pad


def can_move(board):
    if empty_pads(board):
        return True

    for y in range(HEIGHT):
        for x in range(WIDTH):
            value = board[xy_to_pad(x, y)]
            if x + 1 < WIDTH and board[xy_to_pad(x + 1, y)] == value:
                return True
            if y + 1 < HEIGHT and board[xy_to_pad(x, y + 1)] == value:
                return True
    return False


def button_to_direction(buttons):
    if any(buttons & (1 << pad) for pad in UP_KEYS):
        return "up", UP_KEYS
    if any(buttons & (1 << pad) for pad in DOWN_KEYS):
        return "down", DOWN_KEYS
    if any(buttons & (1 << pad) for pad in LEFT_KEYS):
        return "left", LEFT_KEYS
    if any(buttons & (1 << pad) for pad in RIGHT_KEYS):
        return "right", RIGHT_KEYS
    return None, ()


def win_animation(board):
    for _ in range(5):
        draw_board(board, level=0.2)
        time.sleep(0.06)
        draw_board(board, flash_pads=range(NUM_PADS), flash_color=WIN_COLOR)
        time.sleep(0.08)
    draw_board(board)


def game_over_animation(board):
    for _ in range(4):
        draw_board(board, flash_pads=range(NUM_PADS), flash_color=GAME_OVER_COLOR)
        time.sleep(0.09)
        draw_board(board, level=0.25)
        time.sleep(0.09)
    draw_board(board)
    time.sleep(0.8)


def new_game():
    board = [0] * NUM_PADS
    first = spawn_tile(board)
    second = spawn_tile(board)
    draw_board(board)
    pulse_pads(board, (first, second), SPAWN_COLOR, times=2)
    return board


startup_animation()
game = new_game()
won = False

while True:
    buttons = get_button_states()
    direction, command_pads = button_to_direction(buttons)

    if direction is None:
        time.sleep(0.02)
        continue

    pulse_pads(game, command_pads, PRESS_COLOR)
    moved, merged = move(game, direction)

    if moved:
        draw_board(game)
        if merged:
            pulse_pads(game, merged, MERGE_COLOR)

        new_pad = spawn_tile(game)
        if new_pad >= 0:
            draw_board(game)
            pulse_pads(game, (new_pad,), SPAWN_COLOR)

        if not won and max(game) >= WIN_EXPONENT:
            won = True
            win_animation(game)

        if not can_move(game):
            game_over_animation(game)
            game = new_game()
            won = False
    else:
        pulse_pads(game, command_pads, GAME_OVER_COLOR)

    draw_board(game)
    wait_for_release()
