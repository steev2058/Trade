from pathlib import Path


def test_runner_auto_path_uses_protected_execution_only():
    src = Path("app/core/runner.py").read_text()
    start = src.index("if self.auto_enabled:")
    end = src.index("if settings.heartbeat_seconds > 0", start)
    block = src[start:end]

    # safety invariant: no direct open_order in automatic execution block
    assert "open_order(" not in block
    # safety invariant: risk intent + protected execution must be present
    assert "build_execution_intent(" in block
    assert "_execute_intent_with_protection(" in block
