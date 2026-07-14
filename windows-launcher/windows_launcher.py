import json
import os
import subprocess
import sys
import time
from pathlib import Path


CONFIG_PATH = Path(__file__).with_name("launcher_config.json")
PICO_HINTS = ("Pico", "CircuitPython", "USB Serial", "CDC")
IGNORED_ACTION_PREFIXES = ("PING", "READY ", "OK ", "ERR ")


def load_config():
    with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
        return json.load(config_file)


def import_serial():
    try:
        import serial
        from serial.tools import list_ports
    except ImportError:
        print("Module pyserial manquant.")
        print("Installe-le avec: py -m pip install pyserial")
        raise SystemExit(1)
    return serial, list_ports


def choose_port(config, list_ports):
    configured = config.get("port", "auto")
    ports = list(list_ports.comports())

    print("Ports serie detectes:")
    if ports:
        for port in ports:
            manufacturer = f" / {port.manufacturer}" if port.manufacturer else ""
            print(f"  {port.device}: {port.description}{manufacturer}")
    else:
        print("  aucun")

    if configured and configured != "auto":
        return configured

    data_candidates = []
    other_candidates = []
    for port in ports:
        text = f"{port.device} {port.description} {port.manufacturer or ''}"
        lower_text = text.lower()
        if "data" in lower_text and any(hint.lower() in lower_text for hint in PICO_HINTS):
            data_candidates.append(port.device)
        elif any(hint.lower() in lower_text for hint in PICO_HINTS):
            other_candidates.append(port.device)

    if data_candidates:
        return data_candidates[0]

    if other_candidates:
        return other_candidates[0]

    if len(ports) == 1:
        return ports[0].device

    print("Port serie Pico introuvable automatiquement.")
    print("Ports detectes:")
    for port in ports:
        print(f"  {port.device}: {port.description}")
    print("Indique le port COM dans launcher_config.json, par exemple \"COM7\".")
    raise SystemExit(1)


def launch(action):
    command = action["command"]
    args = action.get("args", [])
    label = action.get("label", command)

    print(f"Lancement: {label}")
    if isinstance(command, str) and command.startswith(("http://", "https://")):
        os.startfile(command)
        return

    if args:
        subprocess.Popen([command, *args])
    else:
        subprocess.Popen(command, shell=True)


def event_pad(event_name):
    parts = event_name.split()
    if len(parts) == 2 and parts[1].isdigit():
        return int(parts[1])
    return None


def color_for_action(action):
    color = action.get("color")
    if (
        isinstance(color, list)
        and len(color) == 3
        and all(isinstance(value, int) for value in color)
    ):
        return [max(0, min(255, value)) for value in color]
    return None


def send_pico_palette(connection, actions):
    colors = {}
    for event_name, action in actions.items():
        if not event_name.startswith("BTN "):
            continue

        pad = event_pad(event_name)
        color = color_for_action(action)
        if pad is not None and color is not None:
            colors[pad] = color

    if not colors:
        return

    connection.write(b"RESET_COLORS\n")
    time.sleep(0.05)
    for pad, color in sorted(colors.items()):
        r, g, b = color
        connection.write(f"COLOR {pad} {r} {g} {b}\n".encode("utf-8"))
        time.sleep(0.02)
    connection.write(b"SHOW\n")
    print(f"Palette envoyee au Pico: {len(colors)} couleur(s).")


def listen():
    config = load_config()
    serial, list_ports = import_serial()
    port = choose_port(config, list_ports)
    baudrate = int(config.get("baudrate", 115200))
    actions = config.get("actions", {})

    print(f"Ecoute du Pico sur {port} a {baudrate} bauds.")
    print("Ctrl+C pour quitter.")
    print("Si rien ne s'affiche quand tu appuies, verifie que Thonny/Mu/VS Code ne garde pas le port serie ouvert.")

    while True:
        try:
            with serial.Serial(port, baudrate, timeout=1, dsrdtr=False, rtscts=False) as connection:
                time.sleep(1.0)
                palette_sent = False
                while True:
                    raw = connection.readline()
                    if not raw:
                        continue

                    line = raw.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue

                    print(f"Pico: {line}")
                    if not palette_sent and (line.startswith("READY ") or line == "PING"):
                        send_pico_palette(connection, actions)
                        palette_sent = True

                    if line.startswith(IGNORED_ACTION_PREFIXES):
                        continue

                    action = actions.get(line)
                    if action:
                        launch(action)
        except serial.SerialException as error:
            print(f"Port serie indisponible: {error}")
            print("Nouvelle tentative dans 3 secondes...")
            time.sleep(3)


if __name__ == "__main__":
    try:
        listen()
    except KeyboardInterrupt:
        print()
        print("Launcher arrete.")
        sys.exit(0)
