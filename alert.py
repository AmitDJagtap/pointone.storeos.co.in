"""
Alert popup for Hermes: image + text + ACK / Cancel buttons + repeating sound.
Usage:
  python alert.py --title "..." --text "..." --image "C:\path\img.png" --interval 10 --test
  - Window is always-on-top, centered.
  - ACK (yes)  -> exit code 0
  - Cancel (no)-> exit code 1
  - Sound plays every `--interval` seconds until ACKed or Cancelled.
  - --test : auto-close after 6 seconds (for smoke testing, exit code 0)
"""
import argparse, sys, threading, time, os, platform, subprocess
import tkinter as tk

IS_WINDOWS = platform.system() == "Windows"
if IS_WINDOWS:
    import winsound

def beep_once():
    """Play a beep. Windows: winsound. Linux: graceful fallback (paplay/beep), else silent."""
    try:
        if IS_WINDOWS:
            winsound.Beep(1000, 700)
        else:
            subprocess.run(["paplay", "/usr/share/sounds/freedesktop/stereo/complete.oga"],
                           check=False, timeout=5)
    except Exception:
        pass  # sound skipped silently on non-Windows / non-PulseAudio
from PIL import Image, ImageTk

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--title", default="ALERT")
    p.add_argument("--text", default="Check this")
    p.add_argument("--image", default=None)
    p.add_argument("--interval", type=float, default=10.0, help="seconds between sound repeats")
    p.add_argument("--test", action="store_true", help="auto-close after 6s")
    return p.parse_args()

def main():
    args = parse_args()
    root = tk.Tk()
    root.title(args.title)
    root.attributes("-topmost", True)
    root.configure(bg="#1e1e1e")
    root.resizable(False, False)

    result = {"code": 0}

    # ---- image ----
    img_ref = None
    if args.image and os.path.exists(args.image):
        try:
            pil = Image.open(args.image)
            pil.thumbnail((320, 240))  # max width 320, keep aspect
            img_ref = ImageTk.PhotoImage(pil)
            lbl = tk.Label(root, image=img_ref, bg="#1e1e1e")
            lbl.pack(padx=20, pady=(15, 8))
        except Exception as e:
            print("image load failed:", e)

    # ---- text ----
    tk.Label(root, text=args.title, font=("Segoe UI", 16, "bold"),
             fg="#ffffff", bg="#1e1e1e").pack(padx=30, pady=(6, 4))
    tk.Label(root, text=args.text, font=("Segoe UI", 11),
             fg="#cccccc", bg="#1e1e1e", wraplength=340, justify="center").pack(padx=30, pady=(0, 15))

    # ---- buttons ----
    btn_row = tk.Frame(root, bg="#1e1e1e")
    btn_row.pack(pady=(0, 20))

    def ack():
        result["code"] = 0
        stop_sound()
        root.destroy()

    def cancel():
        result["code"] = 1
        stop_sound()
        root.destroy()

    ack_btn = tk.Button(btn_row, text="ACK", command=ack, font=("Segoe UI", 12, "bold"),
                        bg="#2e7d32", fg="#ffffff", activebackground="#1b5e20",
                        activeforeground="#ffffff", width=10, height=2, bd=0, relief="flat", cursor="hand2")
    ack_btn.pack(side="left", padx=10)
    cancel_btn = tk.Button(btn_row, text="Cancel", command=cancel, font=("Segoe UI", 12),
                           bg="#555555", fg="#ffffff", activebackground="#777777",
                           activeforeground="#ffffff", width=10, height=2, bd=0, relief="flat", cursor="hand2")
    cancel_btn.pack(side="left", padx=10)

    root.bind("<Return>", lambda e: ack())
    root.bind("<Escape>", lambda e: cancel())

    # ---- sound loop (thread) ----
    stop_flag = threading.Event()

    def beep():
        # loop until acked/cancelled
        while not stop_flag.is_set():
            beep_once()
            stop_flag.wait(args.interval)

    def stop_sound():
        stop_flag.set()

    threading.Thread(target=beep, daemon=True).start()

    # ---- center on screen ----
    root.update_idletasks()
    w, h = root.winfo_width(), root.winfo_height()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"+{(sw - w)//2}+{(sh - h)//2 - 100}")

    if args.test:
        root.after(6000, ack)

    root.mainloop()
    sys.exit(result["code"])

if __name__ == "__main__":
    main()
