# StudyClock

StudyClock is a **minimal, distraction-free study timer for Windows**.
It is designed to stay always on top, keep you focused, and provide clear
feedback about your study efficiency without unnecessary complexity.

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
`python -m studyclock`

### Build standalone executable (Windows)
`pyinstaller --onedir --noconsole --name StudyClock src/studyclock/app.py`


### The executable will be located in:
`dist/StudyClock/StudyClock.exe`

