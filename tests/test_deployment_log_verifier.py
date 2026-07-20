import importlib.util
from pathlib import Path

SCRIPT_PATH = Path(__file__).parents[1] / "ops" / "podman" / "verify_logs.py"
SPEC = importlib.util.spec_from_file_location("verify_logs", SCRIPT_PATH)
verify_logs = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(verify_logs)


def ready_logs(events: int = 3) -> str:
    return "\n".join(
        ["[INFO] bot: Distro has connected to Discord!"]
        + [f"[INFO] bot: Reconstructed event: event {index}" for index in range(events)]
    )


def test_fast_verification_accepts_connection_and_three_events():
    assert verify_logs.verify(ready_logs(), "fast") == (True, "log verification passed")


def test_fast_verification_rejects_insufficient_reconstruction():
    assert verify_logs.verify(ready_logs(2), "fast") == (
        False,
        "fewer than three reconstructed events found",
    )


def test_verification_rejects_new_error_signal():
    logs = ready_logs() + "\n[ERROR] bot: connection lost"
    assert verify_logs.verify(logs, "fast") == (
        False,
        "new error-level startup signal found",
    )


def test_verification_rejects_unbracketed_critical_signal():
    logs = ready_logs() + "\nCRITICAL: startup failure"
    assert verify_logs.verify(logs, "fast") == (
        False,
        "new error-level startup signal found",
    )


def test_fast_verification_does_not_accept_stale_input_not_in_the_fresh_log_slice():
    stale_logs = ready_logs()
    fresh_logs = "[INFO] bot: service started"
    assert verify_logs.verify(fresh_logs, "fast") == (
        False,
        "Discord connection marker not found",
    )
    assert verify_logs.verify(stale_logs, "fast") == (True, "log verification passed")


def test_full_verification_requires_final_marker():
    logs = ready_logs() + "\n[INFO] bot: Bot fully initialized and memory reconstructed"
    assert verify_logs.verify(logs, "full") == (True, "log verification passed")


def test_full_verification_rejects_missing_final_marker():
    assert verify_logs.verify(ready_logs(), "full") == (
        False,
        "full initialization marker not found",
    )
