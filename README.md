# Pico RGB Keypad Projects

Small CircuitPython projects for a Raspberry Pi Pico fitted with the Pimoroni Pico RGB Keypad Base.

The keypad hardware uses:

- I2C SDA: `GP4`
- I2C SCL: `GP5`
- SPI CS: `GP17`
- SPI SCK: `GP18`
- SPI MOSI: `GP19`
- Keypad I2C address: `0x20`

## Projects

| Folder | Description |
| --- | --- |
| `circuitpython/01_twinkle` | LED twinkle demo with reactive key ripples. |
| `circuitpython/02_lights_out_merlin` | Merlin/Lights Out inspired frame puzzle. |
| `circuitpython/03_2048` | 2048 using colors instead of numbers. |
| `circuitpython/04_memory_pairs` | Memory pairs with 8 hidden color pairs. |
| `circuitpython/05_candle_night_light` | Candle-like night light with fade-out. |
| `circuitpython/06_windows_launcher_pico` | Pico-side code for the Windows launcher. |
| `windows-launcher` | Windows serial listener and JSON action config. |

## Running a CircuitPython Project

Copy the chosen project's `code.py` to the root of the `CIRCUITPY` drive:

```powershell
Copy-Item .\circuitpython\03_2048\code.py D:\code.py -Force
```

The Windows launcher project also needs `boot.py` on the Pico:

```powershell
Copy-Item .\circuitpython\06_windows_launcher_pico\boot.py D:\boot.py -Force
Copy-Item .\circuitpython\06_windows_launcher_pico\code.py D:\code.py -Force
Copy-Item .\windows-launcher\launcher_config.json D:\launcher_config.json -Force
```

After changing `boot.py`, unplug and replug the Pico.

## Windows Launcher

Install `pyserial`:

```powershell
python -m pip install pyserial
```

Run:

```powershell
cd windows-launcher
python windows_launcher.py
```

Configure actions and colors in `windows-launcher/launcher_config.json`.
