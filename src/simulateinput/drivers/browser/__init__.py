from __future__ import annotations

from simulateinput.core.models import PlatformKind
from simulateinput.drivers.base import DriverProbe


class BrowserDriver:
    platform = PlatformKind.BROWSER

    def probe(self) -> DriverProbe:
        return DriverProbe(
            available=False,
            platform=self.platform,
            message="browser driver scaffold created; Playwright integration pending",
        )
