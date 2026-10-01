#!/usr/bin/env python3
"""rogue_keyboard.py — a BadUSB demonstrator (software form, LAB only).
Registers itself as a VIRTUAL KEYBOARD; the host does not object.
Then 'types' a harmless payload at machine speed."""

import time
import random
from evdev import UInput, ecodes as e

# 1) Declare which keys we can press — the software form of a descriptor.
keys = {c: e.ecodes[f"KEY_{c.upper()}"] for c in "abcdefghijklmnopqrstuvwxyz"}
keys[" "] = e.KEY_SPACE

# 2) Register with the host: "I am a keyboard that has these keys."
ui = UInput({e.EV_KEY: list(keys.values())}, name="lab-rogue-slow")
print("[*] Virtual keyboard registered. The host did not object.")
time.sleep(2)  # 2 seconds for you to focus a text field

# 3) One key = press + release + send
def press(key):
    ui.write(e.EV_KEY, key, 1)   # 1 = press down
    ui.write(e.EV_KEY, key, 0)   # 0 = release
    ui.syn()                     # flush the events to the kernel

# 4) Type the harmless payload at machine speed
payload = "lab badusb demo"
print(f"[*] Typing: {payload!r}")
for ch in payload:
    press(keys[ch])
    time.sleep(random.uniform(0.2, 0.83))   # random within the min-max range keys/sec --

ui.close()
print("[*] Done.")
