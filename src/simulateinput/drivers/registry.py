from __future__ import annotations

import os

from simulateinput.core.models import PlatformKind
from simulateinput.core.session import detect_platform
from simulateinput.drivers.base import PlatformDriver
from simulateinput.drivers.browser import BrowserDriver
from simulateinput.drivers.linux_wayland import LinuxWaylandDriver
from simulateinput.drivers.linux_x11 import LinuxX11Driver
from simulateinput.drivers.macos import MacOSDriver
from simulateinput.drivers.windows import WindowsDriver


def create_driver(platform: PlatformKind | None = None) -> PlatformDriver:
    resolved = platform or detect_platform()
    if resolved == PlatformKind.WINDOWS:
        return WindowsDriver()
    if resolved == PlatformKind.MACOS:
        return MacOSDriver()
    if resolved == PlatformKind.LINUX:
        if os.environ.get("WAYLAND_DISPLAY") and os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland":
            return LinuxWaylandDriver()
        return LinuxX11Driver()
    if resolved == PlatformKind.BROWSER:
        return BrowserDriver()
    return LinuxWaylandDriver()
