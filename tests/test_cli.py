import json

from token_runway.cli import __version__, main
from token_runway.viewer.watch import build_hud_text, render_bar


def test_cli_version(capsys):
    try:
        main(["--version"])
    except SystemExit as e:
        assert e.code == 0
    captured = capsys.readouterr()
    assert f"token-runway {__version__}" in captured.out


def test_cli_doctor(capsys):
    ret = main(["doctor", "--no-color"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Token Runway: Doctor" in captured.out


def test_cli_check_json(capsys):
    ret = main(["check", "--json"])
    assert ret == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert isinstance(data, dict)


def test_cli_check_no_color(capsys):
    ret = main(["check", "--no-color"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "\033[" not in captured.out
    assert "Token Runway: Live Quota Telemetry" in captured.out


def test_render_bar_and_hud():
    bar_green = render_bar(50, width=10)
    assert "█" in bar_green
    assert "░" in bar_green

    hud = build_hud_text({})
    assert "Token Runway: Live HUD" in hud
