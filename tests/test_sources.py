from token_runway.sources.base import calculate_minutes_until
from token_runway.sources.claude import find_claude_token, parse_claude_usage
from token_runway.sources.colab import parse_colab_text
from token_runway.sources.copilot import parse_copilot_data
from token_runway.sources.gemini import parse_agy_json
from token_runway.sources.openai_source import find_openai_key
from token_runway.sources.openrouter import find_openrouter_key, parse_openrouter_data


def test_find_openrouter_and_openai_keys(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert find_openrouter_key() is None
    assert find_openai_key() is None

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-test")
    assert find_openrouter_key() == "sk-or-v1-test"
    assert find_openai_key() == "sk-proj-test"


def test_parse_openrouter_data():
    mock_data = {
        "data": {
            "label": "Work Key",
            "usage": 8.50,
            "limit": 10.00,
            "is_free_tier": False,
            "rate_limit": {
                "requests": 200,
                "interval": "10s",
            },
        }
    }
    reading = parse_openrouter_data(mock_data)
    assert reading.provider == "openrouter"
    assert reading.account == "Work Key"
    assert reading.available is True
    assert len(reading.windows) == 2

    limit_window = reading.windows[0]
    assert limit_window.name == "Credit Limit"
    assert limit_window.used_pct == 85
    assert limit_window.status == "warning"
    assert limit_window.remaining_count == 1.50
    assert limit_window.total_entitlement == 10.00

    rate_window = reading.windows[1]
    assert "Rate Limit" in rate_window.name
    assert rate_window.remaining_count == 200.0


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


def test_parse_openrouter_limited_and_unlimited():
    from token_runway.sources.openrouter import parse_openrouter_data

    # 1. Limited key with credit limit -> is_quota=True
    limited_raw = {
        "data": {
            "label": "My Key",
            "usage": 25.0,
            "limit": 100.0,
            "is_free_tier": False,
        }
    }
    reading = parse_openrouter_data(limited_raw)
    assert reading.provider == "openrouter"
    assert len(reading.windows) == 1
    w = reading.windows[0]
    assert w.name == "Credit Limit"
    assert w.used_pct == 25
    assert w.is_quota is True

    # 2. Unlimited key -> is_quota=False, used_pct=None
    unlimited_raw = {
        "data": {
            "label": "Unlimited Key",
            "usage": 42.50,
            "limit": None,
            "is_free_tier": False,
            "rate_limit": {"requests": 200, "interval": "10s"},
        }
    }
    reading_unlim = parse_openrouter_data(unlimited_raw)
    assert len(reading_unlim.windows) == 2
    spend = reading_unlim.windows[0]
    assert spend.name == "Cumulative Spend"
    assert spend.used_pct is None
    assert spend.is_quota is False

    rl = reading_unlim.windows[1]
    assert "Rate Limit" in rl.name
    assert rl.used_pct is None
    assert rl.is_quota is False
