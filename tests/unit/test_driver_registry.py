import os
import unittest
from unittest.mock import patch

from simulateinput.core.models import PlatformKind
from simulateinput.drivers.linux_wayland import LinuxWaylandDriver
from simulateinput.drivers.linux_x11 import LinuxX11Driver
from simulateinput.drivers.macos import MacOSDriver
from simulateinput.drivers.registry import create_driver
from simulateinput.drivers.windows import WindowsDriver


class DriverRegistryTest(unittest.TestCase):
    def test_create_driver_returns_windows_driver(self) -> None:
        driver = create_driver(PlatformKind.WINDOWS)
        self.assertIsInstance(driver, WindowsDriver)

    def test_create_driver_returns_macos_driver(self) -> None:
        driver = create_driver(PlatformKind.MACOS)
        self.assertIsInstance(driver, MacOSDriver)

    def test_create_driver_returns_linux_x11_driver_by_default(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            driver = create_driver(PlatformKind.LINUX)
        self.assertIsInstance(driver, LinuxX11Driver)

    def test_create_driver_returns_wayland_driver_for_wayland_session(self) -> None:
        with patch.dict(
            os.environ,
            {"WAYLAND_DISPLAY": "wayland-0", "XDG_SESSION_TYPE": "wayland"},
            clear=False,
        ):
            driver = create_driver(PlatformKind.LINUX)
        self.assertIsInstance(driver, LinuxWaylandDriver)
