import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

BIN = Path(__file__).resolve().parent.parent / "bin" / "claude-idle-compact"


@pytest.fixture(scope="session")
def ic():
    loader = SourceFileLoader("claude_idle_compact", str(BIN))
    spec = importlib.util.spec_from_loader("claude_idle_compact", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module
