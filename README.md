# ThinkDot (`thinkpad_red_dot_blinker`) 🔴💻

**ThinkDot** is a lightweight, zero-dependency Python utility and daemon for Linux ThinkPads that controls the iconic red LED dot on the exterior ThinkPad lid logo (`/sys/class/leds/tpacpi::lid_logo_dot`).

Turn your ThinkPad's outer lid LED into a **lid-closed AI agent notification beacon**, a **Morse code messenger**, a **Morse code minute clock**, or control any Linux `/sys/class/leds` indicator directly from the command line.

---

## ✨ What It Does

1. **AI Agent / CLI Lid-Closed Alert Daemon (`alert` / `trigger` / `clear`)**
   - Keeps the exterior ThinkPad red dot steadily **ON** during normal operation.
   - When a long-running background task or AI coding agent (such as **Antigravity CLI (`agy`)**) finishes a task or pauses to ask a question, it triggers the alert state (`thinkdot.py trigger`).
   - The red dot on the outside of the lid **blinks continuously**—letting you see from across the room (even when the laptop lid is closed!) that your agent needs your input.
   - **Auto-dismiss on Lid Open or Desktop Notification Clear**:
     - **Lid Open**: As soon as you walk over and **open the laptop lid** (monitored via `/proc/acpi/button/lid/*/state`), the blinking automatically stops and returns to a steady glow.
     - **Desktop Notification Clear**: When you dismiss or click **"Clear"** on the desktop notification (monitored via `org.freedesktop.Notifications` on D-Bus), or send your next prompt (`thinkdot.py clear`), the blinking immediately stops and returns to solid ON.

2. **Morse Code Transmitter (`morse`)**
   - Blinks any text message (`a–z`, `0–9`) in international Morse code on the ThinkPad lid LED.
   - Great for boot notifications (e.g., blinking `"system up"` when Linux finishes booting) or custom status signals.

3. **Morse Code Clock (`clock`)**
   - Every minute on the minute boundary, blinks the current 24-hour time (`HHMM`) in Morse code digits, then keeps the LED steadily lit until the next minute.

4. **General Linux LED Inspector & Controller (`light_control.py` & `thinkdot.py list/on/off/status`)**
   - Discover all controllable LEDs under `/sys/class/leds` (keyboard backlight, power button, mic mute, audio mute, Capslock, ThinkPad lid dot, etc.) and change their brightness or kernel triggers.

---

## 🛠️ Requirements

- **OS**: Linux with the `thinkpad_acpi` kernel module loaded (standard on all modern Linux distributions running on Lenovo ThinkPads).
- **Python**: Python 3.8+ (uses only the Python standard library—**zero external dependencies**).
- **Hardware**: Lenovo ThinkPad with a controllable lid logo LED (`/sys/class/leds/tpacpi::lid_logo_dot`), or any Linux laptop/machine exposing LEDs under `/sys/class/leds`.

---

## 🚀 Quick Start & Installation

Clone the repository and run the installer script:

```bash
git clone https://github.com/d0bz/thinkpad_red_dot_blinker.git
cd thinkpad_red_dot_blinker
chmod +x install.sh thinkdot.py light_control.py
```

### Option A: Full Automated Setup (Alert Daemon + Udev + Boot Greeting + AGY Hooks)

```bash
./install.sh --all
```

### Option B: Selective Installation

```bash
# Install thinkdot.py and light_control.py to /usr/local/bin only
./install.sh

# Install udev rule so you can control the LED without sudo
./install.sh --udev

# Install & start the lid-closed Alert daemon systemd service
./install.sh --service alert

# Or install & start the Morse Clock systemd service instead
./install.sh --service clock

# Enable the "system up" Morse greeting at boot
./install.sh --greet

# Install Antigravity CLI (agy) notification hooks into ~/.gemini/config/hooks.json
./install.sh --agy-hooks
```

---

## 📖 Usage (`thinkdot.py`)

### 1. Inspect Available LEDs & Current Status

```bash
# List all controllable LEDs on your system
thinkdot.py list

# Show current LED brightness, laptop lid state (open/closed), and alert status
thinkdot.py status

# Manually turn the lid dot ON or OFF
thinkdot.py on
thinkdot.py off
```

### 2. Alert Mode (AI Agent / Background Task Notification)

Run the alert daemon (either in a terminal or via `systemd`):

```bash
sudo thinkdot.py alert
```

From any other terminal, script, or hook, trigger or clear the blinking alert:

```bash
# Start blinking the lid LED (and optionally send a tracked desktop notification)
thinkdot.py trigger --reason "build_finished" --notify "Build finished!"

# Stop blinking manually (or simply open the laptop lid / clear the desktop notification!)
thinkdot.py clear
```

**How Auto-Dismiss Works (Lid Open & Desktop Notification Clear):**
- **Lid Open**: If the laptop lid is **closed** when `trigger` is called (or closed while blinking), the outer red dot blinks continuously. The moment you **open the lid**, `thinkdot.py` detects the ACPI lid state transition (`closed` → `open`), clears `/tmp/thinkdot/alert`, and returns the LED to solid ON.
- **Desktop Notification Clear**: While an alert is active, a lightweight background D-Bus watcher listens to `org.freedesktop.Notifications` (`NotificationClosed` / `ActionInvoked`). When you click the notification, click its `×` button, or click **"Clear"** in the desktop notification tray, the alert is automatically cleared and the LED returns to solid ON.

### 3. Blink Text in Morse Code

```bash
# Blink "sos" once with default speed (0.35s per dot unit)
sudo thinkdot.py morse "sos"

# Blink "system up" faster (0.1s per dot unit)
sudo thinkdot.py --unit 0.1 morse "system up"

# Repeat a message continuously until Ctrl+C
sudo thinkdot.py morse "hello world" --repeat
```

### 4. Morse Code Clock

```bash
# Blink the current time (HHMM) once and exit
sudo thinkdot.py clock --once

# Run continuously, blinking HHMM at the start of every minute
sudo thinkdot.py clock
```

### 5. Environment Variables & Custom LEDs

If your laptop uses a different LED path under `/sys/class/leds`, pass `--led` or set environment variables:

| Variable | CLI Flag | Default | Description |
| :--- | :--- | :--- | :--- |
| `THINKDOT_LED` | `--led` | `/sys/class/leds/tpacpi::lid_logo_dot` | Sysfs path to the target LED directory |
| `THINKDOT_LID_STATE` | `--lid-state` | `/proc/acpi/button/lid/LID/state` | ACPI lid state file (auto-falls back to `/proc/acpi/button/lid/*/state`) |
| `THINKDOT_ALERT_FILE` | `--alert-file` | `/tmp/thinkdot/alert` | Path to the shared alert state file |

---

## 🔍 General LED Utility (`light_control.py`)

`light_control.py` lets you list and manipulate any LED under `/sys/class/leds`:

```bash
# List all LEDs with current and max brightness
./light_control.py --list

# Set ThinkPad lid dot brightness (0 or 1)
sudo ./light_control.py --name "tpacpi::lid_logo_dot" --brightness 1

# Set keyboard backlight brightness (0, 1, or 2)
sudo ./light_control.py --name "tpacpi::kbd_backlight" --brightness 2

# Set kernel trigger for an LED (e.g., 'none', 'heartbeat', 'timer', 'default-on')
sudo ./light_control.py --name "tpacpi::lid_logo_dot" --trigger none
```

---

## 🤖 Antigravity CLI (`agy`) Integration

Included in [`examples/agy-hooks.json`](examples/agy-hooks.json) is a ready-to-use hook configuration for **Antigravity CLI** (`~/.gemini/config/hooks.json`):

- **`PreInvocation`**: Automatically runs `thinkdot.py clear` whenever you send a new message to the agent, stopping any active blinking.
- **`Stop`**: When the agent finishes its turn (`fullyIdle` with `NO_TOOL_CALL` in interactive mode), sends a desktop notification (`notify-send`) and triggers `thinkdot.py trigger --reason finished`.
- **`PreToolUse` (`ask_question`)**: When the agent asks you a multiple-choice or clarifying question, sends a desktop notification and triggers `thinkdot.py trigger --reason waiting_answer`.

To install the hooks manually:

```bash
mkdir -p ~/.gemini/config
cp examples/agy-hooks.json ~/.gemini/config/hooks.json
```

---

## ⚙️ Permissions & Udev Rules (Running Without `sudo`)

By default, Linux restricts `/sys/class/leds/tpacpi::lid_logo_dot/brightness` and `trigger` to `root`.
To allow local user scripts to control the LED without `sudo`, install the included udev rule:

```bash
sudo cp udev/99-thinkdot.rules /etc/udev/rules.d/99-thinkdot.rules
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=leds
```

> **Note:** Even if the `thinkdot-alert.service` daemon runs as `root` via `systemd`, any non-root user can run `thinkdot.py trigger` and `thinkdot.py clear` without `sudo` because those commands communicate via `/tmp/thinkdot/alert`.

---

## 🧪 Testing Without Hardware (`mock_led`)

You can test `thinkdot.py` on any system without physical ThinkPad LED hardware using the included `mock_led` directory:

```bash
./thinkdot.py --led ./mock_led status
./thinkdot.py --led ./mock_led --unit 0.05 morse "hi"
```

---

## 📄 License

Released under the [MIT License](LICENSE).
