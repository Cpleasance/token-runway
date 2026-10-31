import json
from unittest.mock import patch

from token_runway.cli import __version__, main
from token_runway.sources.base import ProviderReading, QuotaWindow
from token_runway.viewer.watch import build_hud_text, render_bar

MOCK_READINGS = {
    "claude": ProviderReading(
        provider="claude",
        display_name="Claude Code",
        available=True,
        windows=[QuotaWindow(name="5-Hour", used_pct=20, remaining_pct=80.0)],
    )
}


def test_cli_version(capsys):
    try:
        main(["--version"])
    except SystemExit as e:
        assert e.code == 0
    captured = capsys.readouterr()
    assert f"token-runway {__version__}" in captured.out


def test_cli_doctor(capsys):
    with patch("token_runway.cli.fetch_all_runways", return_value=MOCK_READINGS):
        ret = main(["doctor", "--no-color"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Token Runway: Doctor" in captured.out


def test_cli_check_json(capsys):
    with patch("token_runway.cli.fetch_all_runways", return_value=MOCK_READINGS):
        ret = main(["check", "--json"])
    assert ret == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert isinstance(data, dict)
    assert "claude" in data


def test_cli_check_no_color(capsys):
    with patch("token_runway.cli.fetch_all_runways", return_value=MOCK_READINGS):
        ret = main(["check", "--no-color"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "\033[" not in captured.out
    assert "Token Runway: Live Quota Telemetry" in captured.out


def test_cli_rejects_unknown_provider(capsys):
    # check
    assert main(["check", "-p", "invalid_provider", "--no-color"]) == 1
    err = capsys.readouterr().err
    assert "Unknown provider 'invalid_provider'" in err

    # doctor
    assert main(["doctor", "-p", "invalid_provider", "--no-color"]) == 1
    err = capsys.readouterr().err
    assert "Unknown provider 'invalid_provider'" in err

    # watch
    assert main(["watch", "-p", "invalid_provider"]) == 1
    err = capsys.readouterr().err
    assert "Unknown provider 'invalid_provider'" in err


def test_render_bar_and_hud():
    bar_green = render_bar(50, width=10)
    assert "█" in bar_green
    assert "░" in bar_green

    hud = build_hud_text({})
    assert "Token Runway: Live HUD" in hud


def test_watch_loop_with_provider_filter():
    from token_runway.viewer.watch import run_watch_loop
    with patch("token_runway.viewer.watch.fetch_all_runways", return_value=MOCK_READINGS):
        # Should run 1 iteration deterministically and exit
        run_watch_loop(interval=0.1, max_iterations=1, provider="claude")


def test_cli_dashboard_prohibits_non_loopback(capsys):
    ret = main(["dashboard", "--host", "0.0.0.0"])
    assert ret == 1
    captured = capsys.readouterr()
    assert "Security Error" in captured.err
    assert "loopback-only" in captured.err
