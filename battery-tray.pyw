"""
Battery Tray - System tray icons for Bluetooth/HID peripheral battery levels.

Devices:
  - DA V2 Pro (Razer mouse) — Bluetooth PnP battery (queried by name)
  - ROG Keyboard via Omni Receiver (VID 0x0B05, PID 0x1ACE) — HID output report on MI_02&Col02
"""

import subprocess
import threading
import time

import hid
import pystray
from PIL import Image, ImageDraw, ImageFont


# ── Config ────────────────────────────────────────────────────────────────────

REFRESH_INTERVAL_DEFAULT = 30   # seconds — used for mouse (PowerShell, slow)
REFRESH_INTERVAL_FAST = 2       # seconds — used for keyboard (HID, instant)
LOW_BATTERY_THRESHOLD = 20

# ROG Omni Receiver — keyboard on MI_02&Col02 (Usage Page 0xFF00)
OMNI_VID = 0x0B05
OMNI_PID = 0x1ACE
OMNI_KB_USAGE_PAGE = 0xFF00
OMNI_KB_REPORT_ID = 0x02

# DA V2 Pro Bluetooth name (as seen by Windows PnP)
DA_V2_BT_NAME = "DA V2 Pro"

# ── Battery Query Functions ───────────────────────────────────────────────────

def get_da_v2_battery():
    """Query DA V2 Pro battery via PowerShell PnP (targeted by name, ~3s)."""
    script = (
        f"(Get-PnpDevice -FriendlyName '{DA_V2_BT_NAME}' -Class Bluetooth "
        f"-ErrorAction SilentlyContinue | Select-Object -First 1 | "
        f"Get-PnpDeviceProperty -KeyName '{{104EA319-6EE2-4701-BD47-8DDBF425BBE5}} 2' "
        f"-ErrorAction SilentlyContinue | "
        f"Where-Object {{ $_.Type -ne 'Empty' }}).Data"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True, text=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        value = result.stdout.strip()
        if value and value.isdigit():
            return min(int(value), 100)
        return None
    except Exception:
        return None


def get_omni_keyboard_battery():
    """Query ROG keyboard battery via Omni Receiver MI_02&Col02 (0xFF00).

    Sends command [0x02, 0x12, 0x01] and reads battery % from byte[6],
    charging flag from byte[9].
    Returns (percent, charging) tuple or (None, False).
    """
    try:
        for dev in hid.enumerate(OMNI_VID, OMNI_PID):
            if dev["usage_page"] == OMNI_KB_USAGE_PAGE:
                d = hid.device()
                d.open_path(dev["path"])
                d.set_nonblocking(True)
                # Drain any pending async notifications
                while d.read(64):
                    pass
                # Send keyboard battery query
                pkt = [OMNI_KB_REPORT_ID, 0x12, 0x01] + [0] * 61
                d.write(pkt)
                # Read response (wait up to 1s)
                for _ in range(20):
                    time.sleep(0.05)
                    resp = d.read(64)
                    if resp and len(resp) > 9 and resp[1] == 0x12 and resp[2] == 0x01:
                        d.close()
                        return (min(resp[6], 100), resp[9] > 0)
                d.close()
                return (None, False)
        return (None, False)
    except Exception:
        return (None, False)


# ── Icon Drawing ──────────────────────────────────────────────────────────────

def _bar_color(percent):
    """Return fill color for the charge bar based on level."""
    if percent is None:
        return (100, 100, 100, 255)
    if percent <= LOW_BATTERY_THRESHOLD:
        return (220, 50, 50, 255)     # red
    if percent <= 50:
        return (220, 180, 30, 255)    # yellow
    return (50, 200, 80, 255)         # green


def _draw_charge_bar(draw, percent, x, y, w, h):
    """Draw a vertical charge bar: outline + fill from bottom up."""
    outline_color = (180, 180, 180, 255)
    draw.rectangle([x, y, x + w, y + h], outline=outline_color, width=1)

    if percent is not None and percent > 0:
        fill_h = int((h - 2) * min(percent, 100) / 100)
        fill_color = _bar_color(percent)
        draw.rectangle(
            [x + 1, y + h - 1 - fill_h, x + w - 1, y + h - 1],
            fill=fill_color,
        )


def _draw_mouse(draw, size):
    """Draw a mouse silhouette filling most of the icon."""
    s = size / 64  # scale factor
    cx = int(22 * s)  # center of mouse body (left portion of icon)

    # Body — tall rounded rectangle
    body_l = cx - int(14 * s)
    body_r = cx + int(14 * s)
    body_t = int(6 * s)
    body_b = int(58 * s)
    draw.rounded_rectangle(
        [body_l, body_t, body_r, body_b],
        radius=int(12 * s),
        outline=(200, 200, 200, 255), width=max(1, int(2 * s)),
    )

    # Center divider line (top half)
    mid_y = body_t + int((body_b - body_t) * 0.4)
    draw.line([cx, body_t + int(4*s), cx, mid_y], fill=(160, 160, 160, 255), width=max(1, int(1.5*s)))

    # Scroll wheel
    wh = int(5 * s)
    ww = int(3 * s)
    wy = body_t + int(10 * s)
    draw.rounded_rectangle(
        [cx - ww, wy, cx + ww, wy + wh],
        radius=int(1.5 * s),
        fill=(160, 160, 160, 255),
    )


def _draw_keyboard(draw, size):
    """Draw a keyboard silhouette filling most of the icon."""
    s = size / 64

    # Body — wide rounded rectangle
    body_l = int(2 * s)
    body_r = int(44 * s)
    body_t = int(12 * s)
    body_b = int(52 * s)
    draw.rounded_rectangle(
        [body_l, body_t, body_r, body_b],
        radius=int(4 * s),
        outline=(200, 200, 200, 255), width=max(1, int(2 * s)),
    )

    # Key grid — 4 rows
    key_color = (180, 180, 180, 255)
    pad_x = int(5 * s)
    pad_y = int(16 * s)
    kw = int(5 * s)   # key width
    kh = int(5 * s)   # key height
    gap = int(2 * s)

    rows = [5, 5, 5, 3]  # keys per row (last row has spacebar)
    for row_i, n_keys in enumerate(rows):
        ky = pad_y + row_i * (kh + gap)
        row_width = n_keys * kw + (n_keys - 1) * gap
        start_x = body_l + (body_r - body_l - row_width) // 2
        for col in range(n_keys):
            kx = start_x + col * (kw + gap)
            w = kw
            if row_i == 3 and col == 1:
                # Spacebar — wide middle key
                w = kw * 2 + gap
            if row_i == 3 and col == 2:
                continue  # skip — absorbed by spacebar
            draw.rounded_rectangle(
                [kx, ky, kx + w, ky + kh],
                radius=max(1, int(1 * s)),
                fill=key_color,
            )


DEVICE_DRAWERS = {
    "mouse": _draw_mouse,
    "keyboard": _draw_keyboard,
}


def _draw_lightning(draw, cx, cy, size):
    """Draw a bold lightning bolt centered at (cx, cy), visible at 16px."""
    s = size / 64
    # Bold bolt over the device silhouette
    h = int(44 * s)
    w = int(22 * s)
    top = cy - h // 2
    bot = cy + h // 2
    mid = cy + int(2 * s)
    color = (255, 220, 50, 255)
    outline = (180, 150, 0, 255)
    # Bold zigzag shape
    points = [
        (cx + int(2*s), top),                  # top right
        (cx - w//2, mid),                      # left middle
        (cx - int(1*s), mid),                  # notch left
        (cx - int(2*s), bot),                  # bottom left
        (cx + w//2, mid - int(4*s)),           # right middle
        (cx + int(1*s), mid - int(4*s)),       # notch right
    ]
    draw.polygon(points, fill=color, outline=outline)


def make_battery_icon(percent, device_type=None, charging=False, size=64):
    """Draw device silhouette + vertical charge bar on the right."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw the device silhouette (left ~70% of icon)
    drawer = DEVICE_DRAWERS.get(device_type)
    if drawer:
        drawer(draw, size)

    # Vertical charge bar on the right edge
    bar_w = max(int(size * 0.15), 6)
    bar_margin = int(size * 0.06)
    bar_x = size - bar_w - bar_margin
    bar_y = bar_margin
    bar_h = size - bar_margin * 2

    _draw_charge_bar(draw, percent, bar_x, bar_y, bar_w, bar_h)

    # Lightning bolt overlay when charging — centered on device silhouette
    if charging:
        bolt_cx = (bar_x) // 2  # center of the device area (left of bar)
        bolt_cy = size // 2
        _draw_lightning(draw, bolt_cx, bolt_cy, size)

    return img


# ── Tray Icon Manager ─────────────────────────────────────────────────────────

class BatteryTrayIcon:
    def __init__(self, name, query_fn, device_type=None, refresh_interval=None):
        self.name = name
        self.query_fn = query_fn
        self.device_type = device_type
        self.refresh_interval = refresh_interval or REFRESH_INTERVAL_DEFAULT
        self.level = None
        self.charging = False
        self.icon = None
        self._warned_low = False

    def update(self):
        result = self.query_fn()
        # Query functions return int or (int, bool) for charging-aware devices
        if isinstance(result, tuple):
            self.level, self.charging = result
        else:
            self.level = result
            self.charging = False

        if self.level is not None:
            charge_str = " (charging)" if self.charging else ""
            tooltip = f"{self.name}: {self.level}%{charge_str}"
        else:
            tooltip = f"{self.name}: Unknown"

        image = make_battery_icon(self.level, self.device_type, self.charging)
        if self.icon:
            self.icon.icon = image
            self.icon.title = tooltip
            if self.level is not None and self.level <= LOW_BATTERY_THRESHOLD and not self._warned_low and not self.charging:
                self.icon.notify(f"{self.name} battery low: {self.level}%", "Low Battery")
                self._warned_low = True
            elif self.level is not None and (self.level > LOW_BATTERY_THRESHOLD or self.charging):
                self._warned_low = False

    def create_icon(self):
        menu = pystray.Menu(
            pystray.MenuItem("Refresh", lambda _: self.update()),
            pystray.MenuItem("Exit All", lambda _: exit_all()),
        )
        image = make_battery_icon(None, self.device_type)
        self.icon = pystray.Icon(self.name, image, f"{self.name}: ...", menu)
        return self.icon


# ── App ───────────────────────────────────────────────────────────────────────

tray_icons = []
stop_event = threading.Event()


def exit_all():
    stop_event.set()
    for t in tray_icons:
        try:
            t.icon.stop()
        except Exception:
            pass


def _refresh_device(tray_dev):
    """Refresh loop for a single device at its own interval."""
    while not stop_event.is_set():
        try:
            tray_dev.update()
        except Exception:
            pass
        stop_event.wait(tray_dev.refresh_interval)


def main():
    mouse = BatteryTrayIcon("DA V2 Pro", get_da_v2_battery, "mouse",
                             refresh_interval=REFRESH_INTERVAL_DEFAULT)
    keyboard = BatteryTrayIcon("ROG Keyboard", get_omni_keyboard_battery, "keyboard",
                               refresh_interval=REFRESH_INTERVAL_FAST)
    tray_icons.extend([mouse, keyboard])

    mouse_icon = mouse.create_icon()
    kb_icon = keyboard.create_icon()

    # pystray needs icon.run() on the main thread; run the second in a thread.
    threading.Thread(target=kb_icon.run, daemon=True).start()

    # Start per-device refresh loops
    for t in tray_icons:
        threading.Thread(target=_refresh_device, args=(t,), daemon=True).start()

    # Initial update after icons have had a moment to initialize
    def delayed_first_refresh():
        time.sleep(2)
        for t in tray_icons:
            try:
                t.update()
            except Exception:
                pass

    threading.Thread(target=delayed_first_refresh, daemon=True).start()

    # Block on main icon
    mouse_icon.run()


if __name__ == "__main__":
    main()
