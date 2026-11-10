---
name: desktop-alerter
description: Use when an agent needs to raise a desktop alert popup on the local PC with image, text, custom ACK/Cancel buttons, and a repeating sound until acknowledged.
---

# Desktop Alerter (alert.py)

A desktop popup that shows an image + text with ACK / Cancel buttons. Beeps every N seconds until acknowledged. Works on Windows (winsound) and Linux (paplay fallback, sound silently skipped if unavailable).

## Install

Requirements: Python 3 with `tkinter` and `Pillow`.

```bash
pip install pillow   # tkinter ships with Python on Windows
```

## Run

```bash
python alert.py --title "KITCHEN CHECK" --text "Check the new order on POS" --image cafe_terrace.png --interval 10
```

- Window is always-on-top, centered.
- **ACK** = green button (Enter). **Cancel** = grey button (Esc).
- Sound repeats every `--interval` seconds until ACK or Cancel.
- Exit code: `0` = ACKed, `1` = Cancelled.

## Options

| Flag | Default | Meaning |
|---|---|---|
| `--title` | `ALERT` | Window title / bold headline |
| `--text` | `Check this` | Body text (wraps at ~340px) |
| `--image` | none | PNG/JPG image path (max 320x240, aspect preserved) |
| `--interval` | `10` | Seconds between sound repeats |
| `--test` | off | Auto-close after 6s with exit code 0 (smoke test) |

## Agent integration

```python
import subprocess, sys
r = subprocess.run([sys.executable, "alert.py", "--title", "...", "--text", "...", "--interval", "10"])
if r.returncode == 0:
    print("ACKed")
else:
    print("Cancelled")
```

## Notes

- Linux: tkinter alert still shows; sound plays via `paplay` if available, otherwise silently skipped.
- Keep the image small (max 320x240) so the popup stays compact.
- The default `cafe_terrace.png` is a sample artifact; agents should use their own relevant images.
