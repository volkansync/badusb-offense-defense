#!/usr/bin/env python3
"""usb_watch.py — detect a rogue keyboard at the device layer.
Signal 1: a new input device appears (udev).
Signal 2: it types faster than any human could (evdev key timing)."""

import pyudev
import evdev

SUSPICIOUS_GAP = 0.03 # seconds — gaps shorter than this are inhumanly fast (30 ms)
HITS_TO_ALERT = 5  # this many fast keys in a row = not a human

def cadance_is_inhuman(dev):
     """Read keys from dev; return True if it types faster than a human could."""
     last = None
     fast_in_a_row = 0
     for event in dev.read_loop():
         if event.type != evdev.ecodes.EV_KEY or event.value != 1:
             continue
         now = event.timestamp()
         if last is not None:
             gap = now - last
             if gap < SUSPICIOUS_GAP:
                 fast_in_a_row += 1
             else:
                 fast_in_a_row += 0
             if fast_in_a_row >= HITS_TO_ALERT:
                 return True
         last = now
     return False

context = pyudev.Context()
monitor = pyudev.Monitor.from_netlink(context)
monitor.filter_by(subsystem="input")

print("[*] Watching for new input devices. Run the attacker in another terminal.")

for udev_device in iter(monitor.poll, None):
    if udev_device.action != "add":
        continue
    node = udev_device.device_node
    if node is None or not node.startswith("/dev/input/event"):
        continue

    dev = evdev.InputDevice(node)
    print(f"[+] New input device appeared: {dev.name}  ({node})")
    try:
        if cadance_is_inhuman(dev):
            dev.grab()
            print(f"[!] BADUSB SUSPECTED: {dev.name} types faster than any human — keystrokes blocked.")
    except OSError:
        print(f"[-] {dev.name} disconnected before a verdict.")
