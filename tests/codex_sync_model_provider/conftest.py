from __future__ import annotations

from pathlib import Path

import pytest


from ._helpers import create_environment, required_tools_missing


missing_tools = required_tools_missing()
if missing_tools:
    pytest.skip(
        "required shell-test tools are missing from the controlled PATH: "
        + ", ".join(missing_tools),
        allow_module_level=True,
    )


@pytest.fixture
def environment(tmp_path: Path) -> dict[str, Path]:
    return create_environment(tmp_path)
