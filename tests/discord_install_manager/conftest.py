from __future__ import annotations

from pathlib import Path
import sys

import pytest

PACKAGE_DIR = Path(__file__).resolve().parent
if str(PACKAGE_DIR) not in sys.path:
    sys.path.append(str(PACKAGE_DIR))

from _helpers import _create_manager_environment


@pytest.fixture
def env(tmp_path: Path):
    return _create_manager_environment(tmp_path)
