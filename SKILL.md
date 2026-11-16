---
name: point-one
description: PointOne Windows desktop app — alert popup + POS webview + device activation.
---

# PointOne desktop app

Windows desktop app for store PCs: alert popup engine + POS (pos.storeos.co.in) in a webview + device activation via admin approval on store.chaikaapi.co.in.

## Install (one-time)
1. Download `PointOne.exe` from this skill's artifacts (presigned URL from `GET /skills/point-one/artifacts`).
2. Run it. First run shows the activation screen: enter the store staff email.
3. The app sends hostname / local + public IP / MAC / city-location with an approval request.
4. Admin approves on store.chaikaapi.co.in. The app picks it up within ~5s and opens.
5. Token is saved in `%APPDATA%\pointone\device.json`. Delete that file to re-activate.

## Use
- Tabs: **POS** (opens pos.storeos.co.in in-window), **Alerts** (test alert popup), **This device** (device info + deactivate).
- Alert popup: image + text + ACK/Cancel buttons, repeating beep until acknowledged. Exit code 0 = ACK, 1 = Cancel.
- CLI alert mode: `PointOne.exe --alert --title "..." --text "..." [--image img.png] [--interval 10]`.

## Flags
| Flag | Default | Meaning |
|---|---|---|
| `--title` | ALERT | popup headline |
| `--text` | Check this | body text |
| `--image` | none | PNG/JPG, max 320x240 |
| `--interval` | 10 | seconds between beeps |
| `--test` | — | auto-close after 6s (smoke test) |

## Requirements
- Windows 10/11 x64 (WebView2 runtime ships with Win11 / Edge).
- Single 16 MB exe, no installer, no admin rights needed.

## Source
- Repo: `github.com/AmitDJagtap/pointone.storeos.co.in` (alert.py popup engine + pointone.py shell).
