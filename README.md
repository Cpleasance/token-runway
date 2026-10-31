# Token Runway 🛫

[![PyPI version](https://img.shields.io/pypi/v/token-runway.svg)](https://pypi.org/project/token-runway/)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP](https://img.shields.io/badge/MCP-2024--11--05-green.svg)](https://modelcontextprotocol.io/)

> **Real-time token runway & rate-limit awareness for AI agents.**  
> Give LLMs the self-awareness to weigh whether their actions are justified before exhausting your quotas.

---

## The Problem: Quota-Blind Agents

Modern coding agents (Claude Code, Cursor, Antigravity, Windsurf) operate blind to their own resource limits. An agent will happily fan out five parallel subagents, dump 100,000 tokens of file contents into context, or run recursive test loops when you have **2% of your 5-hour quota remaining and 15 minutes until reset**.

The result? Unplanned `HTTP 429` rate-limit lockouts, stalled workflows, and burnt monthly budgets.

## The Solution: Token Runway

**Token Runway** is a pure-Python, zero-dependency [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server and CLI tool. It aggregates live consumption metrics from your local developer tools and exposes them directly to LLMs through MCP tools, resources, and self-governance prompts.

```
┌────────────────────────────────────────────────────────┐
│                   AI Coding Agent                      │
│      "Should I launch 5 subagents for this task?"      │
└──────────────────────────┬─────────────────────────────┘
                           │ calls assess_action()
                           ▼
┌────────────────────────────────────────────────────────┐
│                  Token Runway MCP                      │
│   • Claude 5-hour: 96% used (Resets in 18 min)         │
│   • Verdict: PAUSE_OR_DOWNGRADE                        │
│   • Strategy: "Use targeted ripgrep instead of loading │
│               full files. Window resets in 18m."       │
└────────────────────────────────────────────────────────┘
```

---

## Supported Providers

| Provider | Harvester Source | Metrics Exposed |
|---|---|---|
| **Anthropic Claude** | `~/.claude/` credentials & OAuth API | 5-Hour Current utilization %, Weekly 7-Day %, countdowns |
| **Google Gemini** | Antigravity CLI (`agy`) | Flash/Pro 5-Hour %, Flash/Pro Weekly %, Argon Weekly % |
| **Antigravity** | Antigravity CLI (`agy`) | Claude & GPT models 5-Hour %, Weekly % |
| **GitHub Copilot** | GitHub CLI (`gh api /copilot_internal/user`) | Chat Monthly %, Completions %, Plan tier, reset date |
| **Google Colab** | Colab CLI (`colab usage`) | Compute unit balance, burn rate/hr, active runtimes |

---

## Quick Start

### 1. Run without installing (`uvx`)

Inspect your runway right now in your terminal:

```bash
uvx token-runway check
```

Output:
```text
=== Token Runway: Live Quota Telemetry ===

Anthropic Claude
  • Current (5-Hour)           ● CRITICAL    Used: 100%  (Remaining:   0.0%)  (Resets in 1h 18m)
  • Weekly (7-Day)             ✔ OK          Used:  76%  (Remaining:  24.0%)  (Resets in 3h 58m)

GitHub Copilot (Plan: free_limited_copilot)
  • Chat Monthly               ✔ OK          Used:   2%  (Remaining:  97.6%)  [195/200]  (Resets in 20h 1m)
  • Completions Monthly        ✔ OK          Used:   0%  (Remaining: 100.0%)  [2000/2000]  (Resets in 20h 1m)
  • Premium Monthly            - NOT ON PLAN

Google Gemini
  • Flash/Pro Weekly           ✔ OK          Used:   7%  (Remaining:  93.1%)  (Resets in 3d 13h)
  • Flash/Pro 5-Hour           ✔ OK          Used:   3%  (Remaining:  96.7%)  (Resets in 4h 37m)
  • Argon Weekly               ● CRITICAL    Used: 100%  (Remaining:   0.0%)  (Resets in 3d 11h)

Antigravity (Claude + GPT)
  • Weekly                     ✔ OK          Used:  50%  (Remaining:  50.2%)  (Resets in 6d 16h)
  • Current (5-Hour)           ✔ OK          Used:   0%  (Remaining: 100.0%)  (Resets in 5h 0m)

Google Colab
  • Compute Units Balance      ✔ OK           [499.46]
  • Burn Rate (/hr)            ✔ OK           [0.0]
  • Active Runtimes            ✔ OK           [0.0]
```

### 2. Auto-Inject into your AI IDEs

Token Runway detects your installed AI editors (**Claude Desktop**, **Cursor**, **Claude Code**, **Antigravity**, **Windsurf**) and injects the server configuration in one command:

```bash
uvx token-runway inject
```

---

## Manual IDE Configuration

If you prefer configuring your editor manually, add the following to your `mcpServers` block:

### Claude Desktop (`claude_desktop_config.json`) / Cursor (`mcp.json`)

```json
{
  "mcpServers": {
    "token-runway": {
      "command": "uvx",
      "args": ["token-runway"]
    }
  }
}
```

Or using standard `python`:

```json
{
  "mcpServers": {
    "token-runway": {
      "command": "python",
      "args": ["-m", "token_runway"]
    }
  }
}
```

---

## What the Agent Sees

Token Runway registers tools, resources, and prompts with the host IDE:

### 1. `assess_action` (Tool)
Agents call this before embarking on expensive actions:
```json
{
  "name": "assess_action",
  "arguments": {
    "action_type": "subagent_fanout",
    "intensity": "high"
  }
}
```
**Sample Response**:
```json
{
  "verdict": "pause_or_downgrade",
  "max_utilization_pct": 100,
  "bottleneck": {
    "provider": "Anthropic Claude",
    "window": "Current (5-Hour)",
    "resets_in_minutes": 78
  },
  "analysis": "Quota is critically constrained (100% used on Anthropic Claude Current (5-Hour)).",
  "preservation_strategies": [
    "Prohibit parallel subagent fan-outs; execute one step at a time.",
    "Read narrow line ranges (under 100 lines) instead of loading full files into context.",
    "Route subagent prompts to lightweight models (Flash/Haiku) if model selection is supported."
  ]
}
```

### 2. `check_runway` (Tool)
Returns a structured JSON snapshot of all active provider limits, reset times, and plan types.

### 3. `runway://status` (Resource)
Real-time JSON context stream that clients can pin to the context window.

### 4. `runway_governance` (Prompt)
System prompt guidelines teaching the agent how to budget tokens and adapt when limits are tight.

---

## Diagnostic Doctor

Run `doctor` to verify which local CLIs and authentication tokens are ready:

```bash
uvx token-runway doctor
```

```text
=== Token Runway: Doctor ===

  ✔ Claude Code: Credentials found
  ✔ Antigravity CLI (`agy`): Found in PATH
  ✔ GitHub CLI (`gh`): Found in PATH
  ✔ Google Colab CLI (`colab`): Found in PATH

Checking live endpoints...
  ✔ Anthropic Claude: Connected (2 quota windows active)
  ✔ GitHub Copilot: Connected (3 quota windows active)
  ✔ Google Gemini: Connected (3 quota windows active)
  ✔ Antigravity (Claude + GPT): Connected (2 quota windows active)
  ✔ Google Colab: Connected (3 quota windows active)

Doctor check completed.
```

---

## Design Philosophy

- **Zero Runtime Dependencies**: Written entirely in pure Python standard library (`json`, `urllib`, `subprocess`, `dataclasses`). Fast startup, no wheel compilation, no broken dependency trees.
- **Fail-Safe & Non-Blocking**: If a CLI is missing or a service times out, Token Runway reports `available: false` with a clear explanation without crashing the MCP connection.
- **Privacy First**: Runs entirely on your local machine over standard input/output (`stdio`). No usage data or tokens are sent to any third-party telemetry servers.

---

## Contributing & Development

```bash
git clone https://github.com/Cpleasance/token-runway.git
cd token-runway
pip install -e ".[dev]"

# Run tests
pytest -v

# Run linter
ruff check .
```

---

## License

MIT License — Copyright (c) 2026 Cory Pleasance.
