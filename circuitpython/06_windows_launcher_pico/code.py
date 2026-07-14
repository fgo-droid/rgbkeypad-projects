import time

import board
import busio
import digitalio
import usb_cdc


WIDTH = 4
HEIGHT = 4
NUM_PADS = WIDTH * HEIGHT
KEYPAD_ADDRESS = 0x20
BRIGHTNESS = 0.30
LONG_PRESS_SECONDS = 0.75
DEBOUNCE_SECONDS = 0.035
HEARTBEAT_SECONDS = 5.0

IDLE_COLORS = (
    (20, 90, 255), (20, 90, 255), (0, 190, 255), (0, 190, 255),
    (0, 220, 150), (0, 220, 150), (170, 255, 35), (170, 255, 35),
    (255, 210, 25), (255, 210, 25), (255, 125, 25), (255, 125, 25),
    (255, 45, 75), (255, 45, 75), (205, 70, 255), (205, 70, 255),
)
idle_colors = [color for color in IDLE_COLORS]

PRESS_COLOR = (255, 255, 255)
LONG_COLOR = (255, 210, 40)

serial = usb_cdc.data
serial_buffer = bytearray()

i2c = busio.I2C(scl=board.GP5, sda=board.GP4, frequency=400000)
spi = busio.SPI(clock=board.GP18, MOSI=board.GP19)
cs = digitalio.DigitalInOut(board.GP17)
cs.direction = digitalio.Direction.OUTPUT
cs.value = True

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


def get_button_states():
    result = bytearray(2)
    while not i2c.try_lock():
        pass
    try:
        i2c.writeto_then_readfrom(KEYPAD_ADDRESS, bytes((0,)), result)
    finally:
        i2c.unlock()
    return (~(result[0] | (result[1] << 8))) & 0xFFFF


def send(*parts):
    message = " ".join(str(part) for part in parts) + "\n"
    try:
        if serial is not None:
            serial.write(message.encode("utf-8"))
        else:
            print(message, end="")
    except OSError:
        pass


def read_serial_commands():
    if serial is None:
        return

    try:
        waiting = serial.in_waiting
    except OSError:
        return

    while waiting:
        try:
            char = serial.read(1)
        except OSError:
            return

        if not char:
            return

        if char in (b"\n", b"\r"):
            if serial_buffer:
                process_command(bytes(serial_buffer).decode("utf-8", errors="ignore").strip())
                serial_buffer.clear()
        elif len(serial_buffer) < 80:
            serial_buffer.extend(char)

        try:
            waiting = serial.in_waiting
        except OSError:
            return


def process_command(command):
    parts = command.split()
    if not parts:
        return

    if parts[0] == "COLOR" and len(parts) == 5:
        try:
            pad = int(parts[1])
            r = clamp(int(parts[2]))
            g = clamp(int(parts[3]))
            b = clamp(int(parts[4]))
        except ValueError:
            send("ERR BAD_COLOR")
            return

        if 0 <= pad < NUM_PADS:
            idle_colors[pad] = (r, g, b)
            send("OK COLOR", pad)
        else:
            send("ERR BAD_PAD", pad)
    elif parts[0] == "RESET_COLORS":
        for pad in range(NUM_PADS):
            idle_colors[pad] = IDLE_COLORS[pad]
        send("OK RESET_COLORS")
    elif parts[0] == "SHOW":
        draw_idle()
        send("OK SHOW")
    else:
        send("ERR UNKNOWN", command)


def draw_idle(active_pad=-1, active_color=PRESS_COLOR):
    for pad in range(NUM_PADS):
        if pad == active_pad:
            set_led(pad, *active_color)
        else:
            set_led(pad, *idle_colors[pad])
    show()


def startup():
    for pad in range(NUM_PADS):
        set_led(pad, *IDLE_COLORS[pad])
        show()
        time.sleep(0.025)
    send("READY PicoRGBKeyPadLauncher")


def first_pressed(buttons):
    for pad in range(NUM_PADS):
        if buttons & (1 << pad):
            return pad
    return -1


startup()
draw_idle()
last_heartbeat = time.monotonic()

while True:
    read_serial_commands()

    now = time.monotonic()
    if now - last_heartbeat >= HEARTBEAT_SECONDS:
        send("PING")
        last_heartbeat = now

    buttons = get_button_states()
    pad = first_pressed(buttons)

    if pad < 0:
        time.sleep(0.02)
        continue

    start = time.monotonic()
    sent_long = False
    draw_idle(pad, PRESS_COLOR)
    send("BTN", pad)

    while get_button_states() & (1 << pad):
        if not sent_long and time.monotonic() - start >= LONG_PRESS_SECONDS:
            sent_long = True
            draw_idle(pad, LONG_COLOR)
            send("LONG", pad)
        time.sleep(0.02)

    time.sleep(DEBOUNCE_SECONDS)
    send("UP", pad)
    draw_idle()
