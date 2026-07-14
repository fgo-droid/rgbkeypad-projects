# Windows Launcher

This listener receives button events from the Pico over USB serial and launches Windows actions configured in `launcher_config.json`.

Example events:

- `BTN 0`: short press on key 0.
- `LONG 15`: long press on key 15.
- `UP 0`: key release, usually not mapped.

Example action:

```json
"BTN 4": {
  "label": "YouTube",
  "command": "https://www.youtube.com",
  "color": [255, 0, 0]
}
```

For the launcher, copy these files to the Pico:

- `circuitpython/06_windows_launcher_pico/boot.py` -> `D:\boot.py`
- `circuitpython/06_windows_launcher_pico/code.py` -> `D:\code.py`
- `windows-launcher/launcher_config.json` -> `D:\launcher_config.json`

Then unplug and replug the Pico.
