#!/usr/bin/env python3
"""ubs_guard.py — rung 3 defense: default-deny.

Behaviour can be faked. Rung 3's attacker (attack/rogue_slow.py) types slowly,
with human-like jitter, so the cadence detector in usb_watch.py — which waited to
measure inter-key timing — is blind to it. Timing is a signal the attacker
controls.

Authorization is not. So we stop judging *how* a new keyboard behaves and instead
block *every* new keyboard the moment it appears — before it can deliver a single
keystroke anywhere — and keep it blocked until a human approves it.

Why this is safe: your real keyboard was already present when the guard started,
so it never fires the "add" event we react to. Only a device that shows up AFTER
we begin watching is treated as untrusted. That is the one thing the attacker
cannot avoid: to type, it must first register, and registration always shows.

Step 1: block on arrival.
Step 2: ask a human to approve, then release. The prompt is answered on the
real keyboard — which was present first and so was never grabbed — so a device
cannot approve itself. Default-deny in full: silent until a human vouches for it.
"""

import pyudev
import evdev

# A keyboard advertises the letter keys. A mouse or touchpad advertises buttons
# and movement, not KEY_A..KEY_Z — so we check both ends of the alphabet to tell
# a text-injecting device apart from a pointer, and leave pointers alone. We do
# NOT require Enter: typing is injection enough (rung 3's slow attacker never
# sends Enter), and under default-deny arrival is cause by itself.
def looks_like_keyboard(dev):
    caps = dev.capabilities().get(evdev.ecodes.EV_KEY, [])
    return evdev.ecodes.KEY_A in caps and evdev.ecodes.KEY_Z in caps


context = pyudev.Context()
monitor = pyudev.Monitor.from_netlink(context)
monitor.filter_by(subsystem="input")

print("[*] Default-deny guard armed.")
print("[*] Every keyboard that appears from now on is blocked on arrival.")
print("[*] Your current keyboard was here first — it is left untouched.")

# Keep references so grabbed/approved devices are not garbage-collected (which
# would close them and silently release the grab).
held = []


def ask_human(dev, node):
    """Prompt on the real keyboard. Return True to approve (release) the device."""
    print(f"[?] Approve new keyboard {dev.name!r} ({node})?")
    print("    A device cannot answer this — only you can, on the keyboard you")
    print("    were already using. [y = release / anything else = keep blocked]")
    try:
        answer = input("    approve> ").strip().lower()
    except EOFError:
        answer = ""
    return answer == "y"

for udev_device in iter(monitor.poll, None):
    if udev_device.action != "add":
        continue
    node = udev_device.device_node
    if node is None or not node.startswith("/dev/input/event"):
        continue

    try:
        dev = evdev.InputDevice(node)
    except OSError:
        # Node announced but not yet openable — nothing we can act on.
        continue

    if not looks_like_keyboard(dev):
        continue

    # Default-deny: take the device exclusively the instant it registers, before
    # it reaches its typing loop. No timing is measured — arrival alone is cause.
    try:
        dev.grab()
    except OSError:
        print(f"[-] {dev.name} vanished before it could be blocked.")
        continue

    held.append(dev)
    print(f"[!] BLOCKED on arrival: {dev.name}  ({node})")
    print("    Not one keystroke from it reaches any application.")

    if ask_human(dev, node):
        dev.ungrab()
        print(f"[+] APPROVED: {dev.name} released — its keystrokes now flow.")
    else:
        print(f"[x] DENIED: {dev.name} stays blocked.")
