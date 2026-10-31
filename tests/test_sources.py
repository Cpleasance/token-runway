from token_runway.sources.base import calculate_minutes_until
from token_runway.sources.claude import find_claude_token, parse_claude_usage
from token_runway.sources.colab import parse_colab_text
from token_runway.sources.copilot import parse_copilot_data
from token_runway.sources.gemini import parse_agy_json


def test_find_claude_token(monkeypatch):
    monkeypatch.delenv("CLAUDE_CODE_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_TOKEN", raising=False)

    monkeypatch.setenv("ANTHROPIC_ACCESS_TOKEN", "test-token-123")
    assert find_claude_token() == "test-token-123"

    monkeypatch.setenv("CLAUDE_CODE_TOKEN", "priority-token-456")
    assert find_claude_token() == "priority-token-456"


def test_calculate_minutes_until():
    assert calculate_minutes_until(None) is None
    assert calculate_minutes_until("invalid") is None
    # Future timestamp should return positive int
    assert calculate_minutes_until("2099-01-01T00:00:00Z") > 0


def test_parse_copilot_data():
    mock_data = {
        "login": "octocat",
        "access_type_sku": "individual",
        "quota_reset_date": "2099-01-01",
        "quota_snapshots": {
            "chat": {
                "entitlement": 200,
                "remaining": 150,
                "percent_remaining": 75.0,
                "unlimited": False,
            },
            "completions": {
                "entitlement": 2000,
                "remaining": 2000,
                "percent_remaining": 100.0,
                "unlimited": False,
            },
            "premium_interactions": {
                "entitlement": 0,
                "remaining": 0,
                "has_quota": False,
            },
        },
    }
    reading = parse_copilot_data(mock_data)
    assert reading.provider == "copilot"
    assert reading.account == "octocat"
    assert reading.plan == "individual"
    assert len(reading.windows) == 3

    chat = reading.windows[0]
    assert chat.name == "Chat Monthly"
    assert chat.used_pct == 25
    assert chat.remaining_pct == 75.0
    assert chat.remaining_count == 150

    completions = reading.windows[1]
    assert completions.name == "Completions Monthly"
    assert completions.used_pct == 0
    assert completions.remaining_pct == 100.0

    premium = reading.windows[2]
    assert premium.name == "Premium Monthly"
    assert premium.status == "not_on_plan"


def test_parse_agy_json():
    mock_data = {
        "command": {
            "name": "usage",
            "data": {
                "groups": [
                    {
                        "name": "Gemini Models",
                        "buckets": [
                            {"id": "gemini-5h", "window": "5h", "remaining_fraction": 0.85, "reset_time": "2099-01-01T00:00:00Z"},
                            {"id": "gemini-weekly", "window": "weekly", "remaining_fraction": 0.90, "reset_time": "2099-01-01T00:00:00Z"},
                        ],
                    },
                    {
                        "name": "Claude and GPT models",
                        "buckets": [
                            {"id": "3p-5h", "window": "5h", "remaining_fraction": 1.0, "reset_time": "2099-01-01T00:00:00Z"},
                            {"id": "3p-weekly", "window": "weekly", "remaining_fraction": 0.50, "reset_time": "2099-01-01T00:00:00Z"},
                        ],
                    },
                    {
                        "name": "Gemini 4 Argon",
                        "buckets": [
                            {"id": "gemini-argon-wtu-weekly", "window": "weekly", "remaining_fraction": 0.0, "reset_time": "2099-01-01T00:00:00Z"},
                        ],
                    },
                ]
            },
        }
    }
    gemini, agy = parse_agy_json(mock_data)
    assert gemini.provider == "gemini"
    assert len(gemini.windows) == 3
    # Argon should be critical
    argon = [w for w in gemini.windows if "Argon" in w.name][0]
    assert argon.used_pct == 100
    assert argon.status == "critical"

    assert agy.provider == "antigravity"
    assert len(agy.windows) == 2


def test_parse_claude_usage():
    mock_data = {
        "five_hour": {
            "utilization": 42.0,
            "resets_at": "2099-01-01T00:00:00Z",
        },
        "seven_day": {
            "utilization": 20.0,
            "resets_at": "2099-01-02T00:00:00Z",
        },
    }
    reading = parse_claude_usage(mock_data)
    assert reading.provider == "claude"
    assert len(reading.windows) == 2
    assert reading.windows[0].name == "Current (5-Hour)"
    assert reading.windows[0].used_pct == 42
    assert reading.windows[1].name == "Weekly (7-Day)"
    assert reading.windows[1].used_pct == 20


def test_parse_colab_text():
    raw = """
Current balance: 450.25 compute units
Usage rate: 1.50/hr
Active assignments: 1
    """
    reading = parse_colab_text(raw)
    assert reading.provider == "colab"
    assert len(reading.windows) == 3
    assert reading.windows[0].remaining_count == 450.25
    assert reading.windows[1].remaining_count == 1.50
    assert reading.windows[2].remaining_count == 1.0
