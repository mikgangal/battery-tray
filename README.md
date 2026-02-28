# battery-tray

Windows system tray battery icons for wireless peripherals that don't have native battery indicators (e.g. after disabling OEM bloatware like Armoury Crate).

Two tray icons show battery level with device silhouettes, color-coded charge bars, and a charging indicator.

## Supported Devices

| Device | Connection | Method | Poll Interval |
|--------|-----------|--------|---------------|
| ROG STRIX SCOPE II 96 WIRELESS | ASUS Omni Receiver (2.4GHz) | HID output report | 2s |
| Razer DA V2 Pro | Bluetooth | Windows PnP property | 30s |

## Features

- Per-device tray icon with mouse/keyboard silhouette
- Vertical charge bar (green > 50%, yellow 20-50%, red < 20%)
- Lightning bolt overlay when charging (keyboard)
- Low battery notification at 20%
- Hover tooltip with exact percentage and charging state
- Right-click menu: Refresh / Exit

## Requirements

- Windows 10/11
- Python 3.10+

```
pip install hidapi pystray Pillow
```

## Usage

```
pythonw battery-tray.pyw
```

Or use the VBS launcher for a completely silent start (no console flash):

```
wscript battery-tray.vbs
```

### Auto-start at login

Copy `battery-tray.vbs` to `shell:startup`, editing the path inside to point to your `battery-tray.pyw` location.

## ASUS Omni Receiver Protocol

The keyboard battery protocol was reverse-engineered for this project. No existing open-source tool (G-Helper, OpenRGB, etc.) supports keyboard battery via the Omni Receiver — only mice.

**Interface:** MI_02&Col02 (Usage Page `0xFF00`), report ID `0x02`

**Battery query:** `[0x02, 0x12, 0x01, 0x00 * 61]`

**Response:**

| Byte | Value |
|------|-------|
| 0 | `0x02` (report ID) |
| 1 | `0x12` (echo) |
| 2 | `0x01` (echo) |
| 6 | Battery percentage (0-100) |
| 9 | Charging flag (0 = discharging, 1 = charging) |

For comparison, mice use subcommand `0x07` on MI_02&Col03 (Usage Page `0xFF01`) with report ID `0x03`, and battery at byte 5. The keyboard uses a different interface, report ID, subcommand, and byte offset.
