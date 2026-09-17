"""Test setup shared by every suite: Qt runs offscreen and never reaches the network."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
