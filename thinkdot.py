#!/usr/bin/env python3
"""
thinkdot.py — Control the ThinkPad lid-logo red dot LED (tpacpi::lid_logo_dot).

Supports:
  - AI Agent / Antigravity CLI alert daemon (`alert` / `trigger` / `clear`)
    that stays steadily lit and blinks when attention is needed until the
    laptop lid is opened.
  - Morse code text blinker (`morse`)
  - Morse code minute clock (`clock`)
  - Direct LED control & inspection (`on`, `off`, `status`, `list`)
"""

import argparse
import glob
import os
import signal
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

DEFAULT_LED = os.environ.get("THINKDOT_LED", "/sys/class/leds/tpacpi::lid_logo_dot")
BRIGHTNESS = "brightness"
TRIGGER = "trigger"
DEFAULT_UNIT_SECONDS = 0.35
DEFAULT_BLINK_INTERVAL = 0.35
CLOCK_REPEATS = 1

DEFAULT_LID_STATE = os.environ.get("THINKDOT_LID_STATE", "/proc/acpi/button/lid/LID/state")
DEFAULT_ALERT_FILE = os.environ.get("THINKDOT_ALERT_FILE", "/tmp/thinkdot/alert")

MORSE = {
    # Letters
    "a": ".-",   "b": "-...", "c": "-.-.", "d": "-..",  "e": ".",    "f": "..-.",
    "g": "--.",  "h": "....", "i": "..",   "j": ".---", "k": "-.-",  "l": ".-..",
    "m": "--",   "n": "-.",   "o": "---",  "p": ".--.", "q": "--.-", "r": ".-.",
    "s": "...",  "t": "-",    "u": "..-",  "v": "...-", "w": ".--",  "x": "-..-",
    "y": "-.--", "z": "--..",
    # Numbers
    "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-",
    "5": ".....", "6": "-....", "7": "--...", "8": "---..", "9": "----.",
    # Word separator
    " ": " "
}


def _handle_signal(signum, _frame):
    raise SystemExit(0)


def write_file(path, data):
    with open(path, "w") as f:
        f.write(data)


def read_file(path):
    with open(path, "r") as f:
        return f.read()


def ensure_led(led_path):
    if not os.path.isdir(led_path):
        raise FileNotFoundError(
            f"LED path not found: {led_path}\n"
            f"Tip: Run 'thinkdot.py list' to see available LEDs on this system."
        )
    trig = os.path.join(led_path, TRIGGER)
    if os.path.exists(trig):
        # Put LED under manual control
        try:
            write_file(trig, "none")
        except PermissionError:
            raise PermissionError(
                f"No permission to set trigger at {trig}. Run as root or install udev rules."
            )
    # Quick sanity check: some drivers require 0/1 writes only
    mb = os.path.join(led_path, "max_brightness")
    if os.path.exists(mb):
        try:
            max_b = int(read_file(mb).strip())
            if max_b < 1:
                raise RuntimeError("max_brightness < 1 — LED may not be writable.")
        except ValueError:
            pass


def led_on(led_path):
    try:
        write_file(os.path.join(led_path, BRIGHTNESS), "1")
    except PermissionError:
        raise PermissionError(
            "No permission to write brightness. Run as root or install udev rules."
        )


def led_off(led_path):
    try:
        write_file(os.path.join(led_path, BRIGHTNESS), "0")
    except PermissionError:
        raise PermissionError(
            "No permission to write brightness. Run as root or install udev rules."
        )


def sleep_units(units, unit_sec):
    # Use monotonic sleep for better accuracy
    end = time.monotonic() + units * unit_sec
    while True:
        remaining = end - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(remaining, 0.05))


def blink_symbol(sym, unit, led_path):
    # dot: 1 unit on, dash: 3 units on, between parts of same letter: 1 unit off
    if sym == ".":
        led_on(led_path)
        sleep_units(1, unit)
        led_off(led_path)
    elif sym == "-":
        led_on(led_path)
        sleep_units(3, unit)
        led_off(led_path)
    else:
        return
    sleep_units(1, unit)


def blink_letter(letter, unit, led_path):
    code = MORSE.get(letter.lower())
    if not code or code == " ":
        return
    for s in code:
        blink_symbol(s, unit, led_path)
    # Between letters: additional 2 units off (we already waited 1 between symbols)
    sleep_units(2, unit)


def blink_word(word, unit, led_path):
    for ch in word:
        blink_letter(ch, unit, led_path)
    # Between words: total 7 units off. We already waited 1 after last symbol and +2 after letter,
    # so add 4 more units to reach 7.
    sleep_units(4, unit)


def blink_text(text, unit, led_path, repeat=False, gap_units=7):
    ensure_led(led_path)
    words = text.split()
    try:
        while True:
            for w in words:
                blink_word(w, unit, led_path)
            # Pause between full message repeats
            sleep_units(gap_units, unit)
            if not repeat:
                break
    finally:
        led_off(led_path)


def time_to_morse_chunks(now=None):
    # Return a list of strings representing HH:MM as blocks to blink
    if not now:
        now = datetime.now()
    hh = f"{now.hour:02d}"
    mm = f"{now.minute:02d}"
    return list(hh + mm)


def blink_digit(d, unit, led_path):
    for s in MORSE[d]:
        blink_symbol(s, unit, led_path)
    # Between digits, add 2 extra units (symbol gap already 1) -> total inter-letter 3
    sleep_units(2, unit)


def run_clock(unit, led_path, once=False, repeats=CLOCK_REPEATS):
    """
    Every minute, blink HHMM in Morse (digits), then leave the LED lit
    until the next minute boundary. Use --once to blink the current time a single
    set of repetitions and exit.
    """
    ensure_led(led_path)
    try:
        while True:
            now = datetime.now()
            digits = time_to_morse_chunks(now)
            for repeat in range(repeats):
                for d in digits:
                    blink_digit(d, unit, led_path)
                # Word-like gap between repeats, but leave LED lit after the last set
                if repeat < repeats - 1:
                    sleep_units(4, unit)
            led_on(led_path)

            if once:
                break

            # Sleep until next minute boundary to stay in sync
            next_min = (now.replace(second=0, microsecond=0) + timedelta(minutes=1)).timestamp()
            while True:
                rem = next_min - time.time()
                if rem <= 0:
                    break
                time.sleep(min(rem, 0.5))
    finally:
        led_on(led_path)


def resolve_lid_state_path(lid_state_path=DEFAULT_LID_STATE):
    if os.path.exists(lid_state_path):
        return lid_state_path
    matches = glob.glob("/proc/acpi/button/lid/*/state")
    if matches:
        return matches[0]
    return lid_state_path


def is_lid_open(lid_state_path=DEFAULT_LID_STATE):
    """Return True if the laptop lid is open, False if closed."""
    path = resolve_lid_state_path(lid_state_path)
    if not os.path.exists(path):
        return True
    try:
        content = read_file(path).strip().lower()
        return "open" in content
    except Exception:
        return True


def ensure_alert_dir(alert_file=DEFAULT_ALERT_FILE):
    alert_dir = os.path.dirname(os.path.abspath(alert_file))
    if alert_dir:
        os.makedirs(alert_dir, exist_ok=True)
        try:
            os.chmod(alert_dir, 0o777)
        except OSError:
            pass


def trigger_alert(reason="alert", alert_file=DEFAULT_ALERT_FILE):
    """Signal that an agent/process is waiting for an answer or has finished."""
    ensure_alert_dir(alert_file)
    write_file(alert_file, f"{time.time()}:{reason}\n")
    try:
        os.chmod(alert_file, 0o666)
    except OSError:
        pass


def clear_alert(alert_file=DEFAULT_ALERT_FILE):
    """Clear the active alert flag."""
    try:
        os.remove(alert_file)
    except FileNotFoundError:
        pass
    except OSError:
        pass


def get_alert_mtime(alert_file=DEFAULT_ALERT_FILE):
    try:
        return os.path.getmtime(alert_file)
    except OSError:
        return None


def run_alert(led_path, blink_interval=DEFAULT_BLINK_INTERVAL,
              lid_state_path=DEFAULT_LID_STATE, alert_file=DEFAULT_ALERT_FILE):
    """
    Keep the LED stable ON. When an alert is triggered (e.g. Antigravity CLI waiting
    for an answer or finished), blink the LED continuously until the laptop lid is
    opened or the alert is cleared.
    """
    ensure_led(led_path)
    ensure_alert_dir(alert_file)
    led_on(led_path)

    blinking = False
    saw_closed = False
    last_mtime = None
    led_state = True

    try:
        while True:
            mtime = get_alert_mtime(alert_file)
            if mtime is not None:
                lid_open = is_lid_open(lid_state_path)
                if not blinking or mtime != last_mtime:
                    blinking = True
                    last_mtime = mtime
                    saw_closed = not lid_open
                else:
                    if not lid_open:
                        saw_closed = True
                    elif saw_closed:
                        # Lid was closed and is now opened -> stop blinking and stay stable on
                        clear_alert(alert_file)
                        blinking = False
                        saw_closed = False
                        last_mtime = None
                        led_on(led_path)
                        led_state = True
                        time.sleep(0.1)
                        continue

                # Toggle LED for blinking
                led_state = not led_state
                if led_state:
                    led_on(led_path)
                else:
                    led_off(led_path)

                # Wait for blink_interval while polling lid state for immediate response
                end = time.monotonic() + blink_interval
                while True:
                    rem = end - time.monotonic()
                    if rem <= 0:
                        break
                    if get_alert_mtime(alert_file) is None:
                        break
                    cur_open = is_lid_open(lid_state_path)
                    if not cur_open:
                        saw_closed = True
                    elif saw_closed:
                        break
                    time.sleep(min(0.05, rem))
            else:
                if blinking or not led_state:
                    blinking = False
                    saw_closed = False
                    last_mtime = None
                    led_on(led_path)
                    led_state = True
                time.sleep(0.1)
    finally:
        led_on(led_path)


def list_leds():
    leds_dir = Path("/sys/class/leds")
    if not leds_dir.exists():
        print("No /sys/class/leds directory found on this system.")
        return 1
    leds = sorted(p for p in leds_dir.iterdir() if (p / BRIGHTNESS).exists())
    if not leds:
        print("No controllable LEDs found under /sys/class/leds.")
        return 1
    print("Available LEDs under /sys/class/leds:")
    for p in leds:
        try:
            b = (p / BRIGHTNESS).read_text().strip()
        except Exception:
            b = "?"
        try:
            mx = (p / "max_brightness").read_text().strip()
        except Exception:
            mx = "?"
        marker = "  <-- default ThinkPad lid dot" if str(p) == DEFAULT_LED else ""
        print(f"  {p}  (brightness={b}/{mx}){marker}")
    return 0


def show_status(led_path, lid_state_path=DEFAULT_LID_STATE, alert_file=DEFAULT_ALERT_FILE):
    print(f"LED path:       {led_path} ({'exists' if os.path.isdir(led_path) else 'NOT FOUND'})")
    b_path = os.path.join(led_path, BRIGHTNESS)
    if os.path.exists(b_path):
        try:
            print(f"LED brightness: {read_file(b_path).strip()}")
        except Exception as e:
            print(f"LED brightness: <error: {e}>")
    resolved_lid = resolve_lid_state_path(lid_state_path)
    lid_status = "open" if is_lid_open(lid_state_path) else "closed"
    print(f"Lid state:      {lid_status} ({resolved_lid})")
    if os.path.exists(alert_file):
        try:
            raw = read_file(alert_file).strip()
        except Exception:
            raw = "active"
        print(f"Alert state:    ACTIVE ({raw}) [{alert_file}]")
    else:
        print(f"Alert state:    inactive [{alert_file}]")


def main():
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    ap = argparse.ArgumentParser(
        description="Control the ThinkPad lid-logo red dot LED for Morse, clock, or AI/CLI alerts."
    )
    ap.add_argument("--led", default=DEFAULT_LED,
                    help="LED sysfs path (default: %(default)s, or $THINKDOT_LED)")
    ap.add_argument("--unit", type=float, default=DEFAULT_UNIT_SECONDS,
                    help="Morse unit seconds (dot = 1 unit). Default: %(default)s")
    sub = ap.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("morse", help="Blink a text message in Morse code.")
    m.add_argument("message", help="Text to blink")
    m.add_argument("--repeat", action="store_true", help="Repeat message forever")

    c = sub.add_parser("clock", help="Blink current time (HHMM) in Morse once per minute.")
    c.add_argument("--once", action="store_true", help="Blink current time once then exit")
    c.add_argument("--repeats", type=int, default=CLOCK_REPEATS,
                   help="Number of times to repeat HHMM each minute (default: %(default)s)")

    a = sub.add_parser("alert", aliases=["agy"],
                       help="Stay stable on; blink when alerted until laptop lid is opened.")
    a.add_argument("--interval", type=float, default=DEFAULT_BLINK_INTERVAL,
                   help="Blink interval in seconds (default: %(default)s)")
    a.add_argument("--lid-state", default=DEFAULT_LID_STATE,
                   help="ACPI lid state path (default: %(default)s)")
    a.add_argument("--alert-file", default=DEFAULT_ALERT_FILE,
                   help="Alert state file path (default: %(default)s)")

    t = sub.add_parser("trigger", help="Trigger the alert blinking state.")
    t.add_argument("--reason", default="agy", help="Reason for the alert (default: %(default)s)")
    t.add_argument("--alert-file", default=DEFAULT_ALERT_FILE,
                   help="Alert state file path (default: %(default)s)")

    cl = sub.add_parser("clear", help="Clear the alert blinking state.")
    cl.add_argument("--alert-file", default=DEFAULT_ALERT_FILE,
                    help="Alert state file path (default: %(default)s)")

    sub.add_parser("on", help="Turn the LED steadily ON.")
    sub.add_parser("off", help="Turn the LED OFF.")

    st = sub.add_parser("status", help="Show current LED, lid, and alert status.")
    st.add_argument("--lid-state", default=DEFAULT_LID_STATE,
                    help="ACPI lid state path (default: %(default)s)")
    st.add_argument("--alert-file", default=DEFAULT_ALERT_FILE,
                    help="Alert state file path (default: %(default)s)")

    sub.add_parser("list", help="List available controllable LEDs under /sys/class/leds.")

    args = ap.parse_args()

    try:
        if args.cmd == "morse":
            blink_text(args.message, args.unit, args.led, repeat=args.repeat)
        elif args.cmd == "clock":
            run_clock(args.unit, args.led, once=args.once, repeats=args.repeats)
        elif args.cmd in ("alert", "agy"):
            run_alert(args.led, blink_interval=args.interval,
                      lid_state_path=args.lid_state, alert_file=args.alert_file)
        elif args.cmd == "trigger":
            trigger_alert(reason=args.reason, alert_file=args.alert_file)
        elif args.cmd == "clear":
            clear_alert(alert_file=args.alert_file)
        elif args.cmd == "on":
            ensure_led(args.led)
            led_on(args.led)
        elif args.cmd == "off":
            ensure_led(args.led)
            led_off(args.led)
        elif args.cmd == "status":
            show_status(args.led, lid_state_path=args.lid_state, alert_file=args.alert_file)
        elif args.cmd == "list":
            sys.exit(list_leds())
    except SystemExit:
        raise
    except KeyboardInterrupt:
        pass
    except (FileNotFoundError, PermissionError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
