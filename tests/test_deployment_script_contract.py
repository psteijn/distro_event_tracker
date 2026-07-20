from pathlib import Path

REPO_ROOT = Path(__file__).parents[1]


def test_fast_gate_is_bounded_and_only_reads_logs_after_the_restart():
    common = (REPO_ROOT / "ops" / "podman" / "common.sh").read_text(encoding="utf-8")
    assert "fast) deadline=$((SECONDS + 120))" in common
    assert 'podman logs --since "$started_at" "$container"' in common


def test_deploy_rolls_both_services_back_and_rebuilds_a_missing_prior_image():
    deploy = (REPO_ROOT / "ops" / "podman" / "deploy.sh").read_text(encoding="utf-8")
    assert "rollback_both_bots()" in deploy
    assert 'podman image exists "$previous_image" || podman build --pull=never' in deploy
    assert 'start_and_verify_bots "$PREVIOUS_SHA"' in deploy
    assert 'ln -sfn "$PREVIOUS_RELEASE" /srv/src/distro_event_tracker' in deploy


def test_powershell_exposes_fast_and_full_verification_modes():
    deploy = (REPO_ROOT / "deploy.ps1").read_text(encoding="utf-8")
    assert "[switch]$VerifyFullInitialization" in deploy
    assert "--rollback-full" in deploy
    assert "wait_for_bot \"$instance\" \"$started_at\" ''{1}''" in deploy
