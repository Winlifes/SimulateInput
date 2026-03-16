# Cross-Platform Installation

This document describes how to prepare `SimulateInput` on Windows, macOS, Linux X11, and Linux Wayland.

## Common Python Setup

From the project root:

```powershell
python -m pip install -e .
```

If you prefer a plain install:

```powershell
python -m pip install PyYAML opencv-python-headless pillow pytesseract pywinauto
```

Core runtime Python dependencies:

- `PyYAML`
- `opencv-python-headless`
- `pillow`
- `pytesseract`
- `pywinauto`

Platform-specific Python dependency:

- macOS: `pyobjc-framework-Quartz`

## Windows

### System requirements

- Windows desktop session
- UI automation target running in the same interactive session

### Optional tools

- `Tesseract OCR` for OCR lookup

Install:

```powershell
winget install --source winget --id tesseract-ocr.tesseract --accept-source-agreements --accept-package-agreements --silent
```

Default auto-detected path:

- `C:\Program Files\Tesseract-OCR\tesseract.exe`

Optional override:

```powershell
$env:TESSERACT_CMD='C:\Program Files\Tesseract-OCR\tesseract.exe'
```

## macOS

### Python dependency

Install Quartz bindings:

```bash
python3 -m pip install pyobjc-framework-Quartz
```

### Permissions

Grant these permissions to the terminal or app that launches `SimulateInput`:

- `Accessibility`
- `Automation`
- `Screen Recording` for screenshots and OCR/image locators

### Optional tools

- `Tesseract OCR`

Homebrew example:

```bash
brew install tesseract
```

If `tesseract` is not on `PATH`, set:

```bash
export TESSERACT_CMD=/opt/homebrew/bin/tesseract
```

### Notes

- `find_uia` uses `System Events` UI scripting and depends on Accessibility permission
- `find_ocr_text` and `find_image` depend on screenshots plus local OCR/OpenCV libraries

## Linux X11

### Required system tools

Install these packages:

- `wmctrl`
- `xdotool`

One screenshot tool:

- `imagemagick` (`import`)
- or `gnome-screenshot`
- or `scrot`

### Optional tools

- `Tesseract OCR`
- `python3-pyatspi` for AT-SPI lookup behind `find_uia`

Ubuntu/Debian example:

```bash
sudo apt-get update
sudo apt-get install -y wmctrl xdotool scrot tesseract-ocr python3-pyatspi
```

Fedora example:

```bash
sudo dnf install -y wmctrl xdotool scrot tesseract python3-pyatspi
```

### Notes

- `find_uia` is implemented as a best-effort AT-SPI lookup through `python3` and `pyatspi`
- `find_text` combines window-title matching with AT-SPI lookup when available

## Linux Wayland

Wayland support is a compatibility layer, not full parity.

### Recommended helper tools

- `ydotool`
- `wtype`
- `grim`
- `tesseract-ocr` for OCR

Ubuntu example:

```bash
sudo apt-get update
sudo apt-get install -y ydotool wtype grim tesseract-ocr
```

### Notes

- Generic window enumeration and focus are not portable across compositors
- `click`, `drag`, and some key actions depend on local compositor permissions and helper tools
- `screenshot`, `find_ocr_text`, and `find_image` depend on `grim`

## Validation

Run:

```powershell
$env:PYTHONPATH='src'
python -m simulateinput.cli.main doctor
```

Expected result:

- driver availability report
- capability list for the current platform

## First Smoke Test

You can start with the platform smoke cases in:

- `tests/e2e/cases/windows-smoke.yaml`
- `tests/e2e/cases/macos-smoke.yaml`
- `tests/e2e/cases/linux-x11-smoke.yaml`
- `tests/e2e/cases/linux-wayland-smoke.yaml`
