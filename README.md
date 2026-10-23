<div align="center">

# badusb-offense-defense

**A red/blue escalation lab for the one USB weakness that was never really patched.**

<sub>one process pretends to be a keyboard · another process refuses to trust it · on my own machine, with a harmless payload</sub>

</div>

---

## Where this came from

A friend handed me a flash drive that had "stopped working." It hadn't died — the
controller had locked itself **read-only**. Three independent checks agreed: the drive
was declaring `WP=1` in its own `MODE SENSE` header, `blockdev --setrw` wouldn't clear
it, and the bridge silently refused a `FORMAT UNIT`. The NAND was fine — a full surface
read came back with **zero errors at a steady 98 MB/s** — so this was the recoverable
kind of failure: the controller firmware, not the memory.

The controller was a **Phison** (`PMAP` in its INQUIRY string). To rewrite that firmware
and clear the lock, the tool is **MPALL** — a mass-production utility that reflashes the
controller.

And that is exactly where a repair job turned into a security question. Because the tool
that *fixes* the drive by rewriting its controller firmware is the same class of tool
that, in **2014**, was used to *weaponize* one — the **BadUSB** work (Nohl & Lell,
Black Hat 2014; the public Phison PoC, "Psychson," Caudill & Wilson, later that year,
targeting the very same PS2251 controller family).

> Fixing my friend's drive needs the same primitive an attacker uses to weaponize one:
> **rewriting controller firmware the host cannot see or verify.** The difference is
> intent, not mechanism.

I wanted to actually understand that primitive instead of reading about it. So this repo.
The full diagnosis of the drive lives as a casefile in
[field-notes](https://github.com/volkansync/field-notes); this repo is the hands-on half.

---

## The idea

USB has a trust bug baked into its foundation: **a device announces what it is, and the
host believes it.** Plug in a stick and it can also declare itself a keyboard — the host
loads a keyboard driver and starts obeying keystrokes, no questions asked. The malware,
when it's real, lives in the controller firmware: reprogrammable, unsigned, invisible to
the OS, and untouched by reformatting. Ten-plus years later this is still essentially
unfixed on commodity hardware, because the fix costs silicon nobody wants to pay for and
breaks the universality that makes USB useful. So the defense moved off the device and
onto the host: **you can't make the device honest, so you stop trusting it by default.**

This lab makes that concrete as a ladder. Each rung adds one attacker technique; the
defense then has to grow a new answer. When the defense stops every technique I can build
and I can't invent a new one, the project is done.

Everything runs **on my own machine, with a benign payload, as a virtual device** — the
attacker side is a demonstrator, never a weapon (see [Rules](#rules-i-hold-to)).

---

## The mechanism, in one screen

- **Enumeration.** On connect the host asks "what are you?" and the device answers with
  *descriptors* (`idVendor`, `bInterfaceClass`, …). The host **does not verify** them. A
  single physical device can declare several interfaces at once — storage *and* keyboard.
- **Where the lie lives.** In the controller firmware, below the storage the OS can see.
  Reformatting doesn't touch it; the host can't read it.
- **Why it's still open.** Signing firmware needs a hardware root of trust the cent-margin
  controller market won't buy, and authentication breaks USB's plug-anything promise
  (USB-IF's Type-C Authentication went almost nowhere). The cost lands on the victim, not
  the vendor — a textbook security externality.
- **So the defense lives one layer down from the screen.** An attacker controls what you
  *see* — it can hide a terminal, flash it on another workspace. It **cannot** hide that a
  new input device registered with the kernel. That registration is the thing that always
  happens and always shows. The detector watches there.
- **The same shape shows up in AI security.** You can't verify a prompt is honest any more
  than a descriptor is; so you constrain what the untrusted side is *allowed to do*
  (least privilege, capability gating) instead of trying to detect the lie. Same bug,
  same medicine.

---

## The ladder

Attacker gets stronger going down. Defense has to answer each rung to move on.

| # | Attacker technique | Defense answer | Status |
|---|---|---|---|
| 1 | Keystroke injection at machine speed (visible typing) | Watch the device layer for a new keyboard; measure inter-key timing; **grab** the device when it types faster than any human | ✅ done |
| 2 | **Execution**, not just typing — drive a focused shell to run a benign command | Same detector; the command is cut off mid-keystroke before it completes | ✅ done |
| 3 | **Evade the timing signal** — type slowly, with human-like jitter | Timing alone fails → **default-deny**: block every new keyboard the instant it registers, before it can type; release only on explicit human approval | ✅ done |
| 4 | **Impersonate** a real keyboard (spoof the name / a real VID:PID) | Identity is forgeable → don't trust the name; require explicit authorization | ⬜ planned |
| 5 | **Physical** device (Raspberry Pi Pico), composite storage + HID | Move to the USB layer: USBGuard allow-list + composite-interface anomaly | ⬜ hardware stage |

**Currently: rungs 1–3 complete; rung 4 (impersonation) next.**

---

## How it works

Two small Python programs, no special hardware for the software rungs.

**`attack/rogue_keyboard.py`** — uses `evdev.UInput` to register a virtual keyboard with
the kernel (the software form of a malicious descriptor), then "types" a harmless payload
at machine speed. It is a local process, not a portable device — it can demonstrate the
mechanism but cannot be carried to another machine.

**`defense/usb_watch.py`** — uses `pyudev` to watch for a new input device appearing
(signal 1), then `evdev` to open it and time its keystrokes (signal 2). When the cadence
is inhuman it calls `dev.grab()` to take the device exclusively, so its keystrokes stop
reaching every other application.

```
attack  →  a new keyboard registers  →  detector sees it (can't be hidden)
        →  it types at ~10 ms/key, metronome-even  →  no human does that
        →  grab: further keystrokes are swallowed  →  the payload is cut off mid-word
```

**`attack/rogue_exec.py`** (rung 2) — the same virtual keyboard, but instead of typing into
a text field it drives a focused shell to run a benign command (`echo … > /tmp/labbadusb.txt`).
It proves HID injection can *execute*, not just type.

**`attack/rogue_slow.py`** (rung 3) — the same payload typed slowly, with random human-like
gaps between keys. The inter-key timing in `usb_watch.py` never trips, so it walks straight
past the cadence detector. This is the rung that breaks signal 2.

**`defense/usb_guard.py`** (rung 3's answer) — stops judging behaviour at all. Timing can be
faked; authorization cannot. So it **default-denies**: it `grab()`s every new keyboard the
instant it registers — before a single key is sent — and releases it only when a human
approves, answering on the keyboard that was already present. A device cannot vouch for itself.

```
rung 3  →  attacker types slowly, human-like  →  timing detector sees nothing wrong
        →  but it still had to register        →  guard grabs it on arrival anyway
        →  blocked until a human says yes       →  a device cannot approve itself
```

---

## Run it

```bash
python -m venv .venv
.venv/bin/pip install evdev pyudev

# terminal 1 — the defender
.venv/bin/python defense/usb_watch.py

# terminal 2 — the attacker
.venv/bin/python attack/rogue_keyboard.py
```

For **rung 3**, swap both sides: run the default-deny guard against the slow attacker —
`defense/usb_guard.py` in terminal 1, `attack/rogue_slow.py` in terminal 2. The timing
detector in `usb_watch.py` would see nothing wrong; the guard blocks it on arrival anyway,
then asks you to approve it.

Reading and creating input devices needs access to `/dev/uinput` and `/dev/input/event*`.
The clean way is to be in the `input` group (no `sudo`); otherwise run with `sudo`.

To watch the interception with your own eyes: focus an empty text field before running the
attacker. Only the first few characters land — the rest are gone.

---

## Rules I hold to

1. **My machine, my payload.** The attacker only ever runs against my own system, and the
   payload is inert — it proves a keystroke arrived, it does not do harm.
2. **A demonstrator, not a weapon.** The software attacker is a virtual, local device with
   no way to travel. I do **not** reflash a real controller to build a covert one.
3. **Defense is the point.** Every attacker rung exists so the defender has something real
   to stop. The interesting artifact is the one that says *no*.
4. **Name the trade.** Every defense costs something; the honest limits are written down,
   not hidden.

---

## Honest limits

- **`grab` is aggressive.** If the detector ever misjudged a *real* keyboard as inhuman it
  would lock it. It's safe here because the threshold is well clear of human speed and it
  only grabs the flagged device — but a production tool would ask a human first.
- **The virtual attacker has no USB identity.** It isn't on the USB bus, so USBGuard has
  nothing to act on. That's why the software rungs defend at the input/evdev layer and
  USBGuard is deferred to the physical (Pico) stage — two layers, two tools, kept separate.
- **Timing is only the first signal.** Rung 3 breaks it: an attacker patient enough to type
  slowly walks past the cadence detector. The answer isn't a cleverer timing test — it's to
  give up on behaviour entirely and default-deny, since arrival is the one thing the attacker
  can't avoid. That trades convenience (every new keyboard now needs a yes) for a signal that
  can't be faked.

---

<div align="center">

<sub><b>Volkan Çevik</b> · Eskişehir, TR · <a href="https://github.com/volkansync">github.com/volkansync</a><br/>
started from a friend's broken flash drive · <a href="https://github.com/volkansync/field-notes">the diagnosis is a field-note</a></sub>

</div>
