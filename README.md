# Bacman

A recreation of PAC-MAN built with Python and Pygame, developed as an A-Level Computer Science non-exam assessment.

## Features

- **Classic Pac-Man gameplay** with ghost AI
- **Multiplayer** — local (up to 5 players) and online via LAN with UPnP support
- **Maze creator** — design and play custom mazes
- **Replay system** — record and replay games
- **Leaderboard** — local account registry with match history
- **Configurable controls and performance settings** via `config.ini`

## Download

Download the zip for your platform from the [latest release](https://github.com/hhzks/Bacman/releases/latest), extract it, and run the executable:

- **Windows** — `Bacman.exe`
- **macOS** — `Bacman` (you may need to allow it in System Settings > Privacy & Security)
- **Linux** — `./Bacman`

## Requirements

- Python 3.12+
- Dependencies listed in `requirements.txt`

## Getting Started

```bash
pip install -r requirements.txt
python menu.py
```

Set FPS to 240+ in settings for correct collision detection.

## Packaging

Build a standalone Windows executable using [PyInstaller](https://pyinstaller.org):

```bash
pip install pyinstaller
pyinstaller Bacman.spec --noconfirm
```

The output is written to `dist/Bacman/`. Run `Bacman.exe` from that folder.
