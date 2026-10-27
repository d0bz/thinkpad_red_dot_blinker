#!/usr/bin/env python3
import argparse
import os
import sys
from pathlib import Path

LEDS_DIR = Path("/sys/class/leds")

def list_leds():
    leds = []
    if LEDS_DIR.exists():
        for p in LEDS_DIR.iterdir():
            if (p / "brightness").exists():
                leds.append(p.name)
    return sorted(leds)

def read(path):
    try:
        return Path(path).read_text().strip()
    except Exception as e:
        return f"<error: {e}>"

def write(path, value):
    try:
        Path(path).write_text(str(value))
        return True, None
    except Exception as e:
        return False, str(e)

def set_brightness(led_name, value):
    led_path = LEDS_DIR / led_name
    bfile = led_path / "brightness"
    maxfile = led_path / "max_brightness"

    if not bfile.exists():
        print(f"LED '{led_name}' not found or no brightness file.")
        return 1

    # Clamp to max_brightness if present
    maxv = None
    if maxfile.exists():
        try:
            maxv = int(read(maxfile))
        except Exception:
            pass

    try:
        v = int(value)
    except ValueError:
        print("Brightness must be an integer (usually 0..1 or 0..255).")
        return 1

    if maxv is not None:
        v = max(0, min(v, maxv))

    ok, err = write(bfile, v)
    if not ok:
        print(f"Failed to write brightness: {err}\n"
              f"(Tip: you probably need sudo.)")
        return 1

    # Report back current state
    cur = read(bfile)
    mx = read(maxfile) if maxfile.exists() else "?"
    print(f"LED '{led_name}' brightness now {cur} (max {mx})")
    return 0

def set_trigger(led_name, trigger):
    led_path = LEDS_DIR / led_name
    tfile = led_path / "trigger"
    if not tfile.exists():
        print(f"LED '{led_name}' has no trigger file.")
        return 1
    ok, err = write(tfile, trigger)
    if not ok:
        print(f"Failed to write trigger: {err}\n"
              f"(Tip: you probably need sudo.)")
        return 1
    print(f"LED '{led_name}' trigger set to '{trigger}'. Current triggers:\n{read(tfile)}")
    return 0

def main():
    ap = argparse.ArgumentParser(
        description="Toggle LEDs via /sys/class/leds (ThinkPad & others)."
    )
    ap.add_argument("--list", action="store_true", help="List available LEDs")
    ap.add_argument("--name", help="LED name from /sys/class/leds")
    ap.add_argument("--brightness", type=int, help="Set brightness (e.g., 0 or 1/255)")
    ap.add_argument("--trigger", help="Set trigger string (advanced)")
    args = ap.parse_args()

    if args.list or not args.name:
        leds = list_leds()
        if not leds:
            print("No LEDs found under /sys/class/leds.")
        else:
            print("Available LEDs:")
            for n in leds:
                b = read(LEDS_DIR / n / "brightness")
                mx = read(LEDS_DIR / n / "max_brightness") if (LEDS_DIR / n / "max_brightness").exists() else "?"
                print(f"  {n}  (brightness={b}, max={mx})")
        if not args.name:
            return 0

    rc = 0
    if args.brightness is not None:
        rc |= set_brightness(args.name, args.brightness)
    if args.trigger is not None:
        rc |= set_trigger(args.name, args.trigger)
    if args.brightness is None and args.trigger is None:
        print("Nothing to do. Use --brightness or --trigger.")
    return rc

if __name__ == "__main__":
    sys.exit(main())

