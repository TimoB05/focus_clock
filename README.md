# FocusClock

FocusClock is a **minimal, distraction-free focus timer for Windows**.
It is designed to stay always on top, keep you focused, and provide clear
feedback about your focus efficiency without unnecessary complexity.

## Features

- Focus / break / lunch sessions
- Always-on-top compact window
- Skip, rewind, reset controls
- Session-based unit tracking
- Automatic statistics & efficiency calculation
- Persistent state (resume where you stopped)
- Built with PySide6 (Qt)

## Installation (from source)

### Requirements
- Python 3.10+
- Windows 10 / 11

`pip install -r requirements.txt`

### Run locally
`python -m focusclock`

### Build standalone executable (Windows)
`pyinstaller --onedir --noconsole --name FocusClock src/focusclock/app.py --icon=favicon.ico`

macOS:
`pyinstaller --onedir --noconsole --name FocusClock src/focusclock/app.py --icon=favicon.icns`


### The executable will be located in:
`dist/FocusClock/FocusClock.exe`

