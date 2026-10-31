# Token Runway 🛫

[![PyPI version](https://badge.fury.io/py/token-runway.svg)](https://pypi.org/project/token-runway/)
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

| Provider | Harvester Source | Metrics Exposed | Setup Command |
|---|---|---|---|
| **Anthropic Claude** | `~/.claude/` credentials or `CLAUDE_CODE_TOKEN` | 5-Hour Current utilization %, Weekly 7-Day %, countdowns | `claude` (or `CLAUDE_CODE_TOKEN=...`) |
| **GitHub Copilot** | GitHub CLI (`gh api /copilot_internal/user`) | Chat Monthly %, Completions %, Plan tier, reset date | `gh auth login` |
| **Google Gemini** | Antigravity CLI (`agy`) | Flash/Pro 5-Hour %, Flash/Pro Weekly %, Argon Weekly % | `agy` in `$PATH` |
| **Antigravity** | Antigravity CLI (`agy`) | Claude & GPT models 5-Hour %, Weekly % | `agy` in `$PATH` |
| **Google Colab** | Colab CLI (`colab usage`) | Compute unit balance, burn rate/hr, active runtimes | `colab` in `$PATH` |
| **OpenRouter** | OpenRouter Key API | Credit limit, spend balance, rate limit interval | `OPENROUTER_API_KEY=...` |
| **OpenAI API** | OpenAI Models API | Model tier access, key validation | `OPENAI_API_KEY=...` |

---

## Authentication & Provider Setup

Token Runway is designed around a **Zero Manual Configuration** philosophy: it automatically piggybacks on the tools and sessions you already use every day. You don't need to generate or paste API keys.

### 1. Anthropic Claude
- **Automatic Discovery**: If you have [Claude Code](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/overview) installed, simply log in once:
  ```bash
  claude
  ```
  Token Runway automatically discovers your OAuth token in `~/.claude/.credentials.json`.
- **Manual / Headless / CI**: If running in an environment without `~/.claude/`, pass your token via the `CLAUDE_CODE_TOKEN` environment variable:
  ```bash
  export CLAUDE_CODE_TOKEN="your-oauth-token"
  ```
  Or in your MCP client config:
  ```json
  {
    "mcpServers": {
      "token-runway": {
        "command": "uvx",
        "args": ["token-runway"],
        "env": {
          "CLAUDE_CODE_TOKEN": "your-oauth-token"
        }
      }
    }
  }
  ```

### 2. GitHub Copilot
- **Automatic Discovery**: Ensure the [GitHub CLI (`gh`)](https://cli.github.com/) is installed and authenticated:
  ```bash
  gh auth login
  ```
  Token Runway queries GitHub's internal Copilot quota endpoint directly through your `gh` session.
- **Environment Variable**: Alternatively, export `GH_TOKEN` or `GITHUB_TOKEN` with Copilot permissions:
  ```bash
  export GH_TOKEN="ghp_..."
  ```

### 3. Google Gemini & Antigravity
- **Automatic Discovery**: Ensure the Antigravity CLI (`agy`) is in your system `$PATH` and logged in. Token Runway polls `agy -p /usage --output-format json` directly.

### 4. Google Colab
- **Automatic Discovery**: Ensure the `colab` command-line tool is installed and authenticated.

### 5. OpenRouter & OpenAI (Optional)
- Export `OPENROUTER_API_KEY` or `OPENAI_API_KEY`:
  ```bash
  export OPENROUTER_API_KEY="sk-or-v1-..."
  export OPENAI_API_KEY="sk-proj-..."
  ```
  Token Runway tracks credit limits, spend, and active model access automatically.

### 6. Check Your Setup: `doctor`
Whenever you set up or add a new provider, run the doctor command to verify all integrations:

```bash
uvx token-runway doctor
```
It tests every local tool and remote endpoint, reporting exact connection status and active quota windows.

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

### 2. Live Terminal HUD (`watch`)

Keep a live-updating quota dashboard in a split pane (`top` for AI quotas):

```bash
uvx token-runway watch
```
Displays colored ANSI progress bars (`[████████░░░░] 68%`) and real-time countdown tickers ticking down to the exact reset minute.

### 3. Zero-Dependency Web HUD (`dashboard`)

Launch a local dark-mode browser dashboard on `http://localhost:7890`:

```bash
uvx token-runway dashboard
```
Visual progress meters, live polling, and an interactive **Assess Action Simulator** to test LLM decisions in real time.

### 4. Embed Rules into Projects (`init-rules`)

Embed self-governance instructions into your project repository (`CLAUDE.md`, `.cursorrules`, `.windsurfrules`, `AGENTS.md`):

```bash
uvx token-runway init-rules
```
Instructs coding agents to automatically check `assess_action` before running expensive multi-agent sweeps or loading large files.

### 5. Auto-Inject into your AI IDEs

Token Runway detects your installed AI editors (**Claude Desktop**, **Cursor**, **Claude Code**, **Antigravity**, **Windsurf**) and injects the server configuration in one command:

```bash
uvx token-runway inject
```

---

## Safety Guardrails & Strict Throttling

Enforce spending ceilings or maximum quota thresholds:

```bash
# Warn and advise downgrade when utilization exceeds 80%
uvx token-runway run --max-budget 80

# Return an advisory "reject" verdict once over 80%
uvx token-runway run --max-budget 80 --strict
```

> **Important**: MCP servers provide meta-cognitive telemetry and advisory recommendations. Setting `--strict` causes `assess_action` to return a `"reject"` verdict and actionable mitigation strategies, but the server cannot forcibly terminate client process execution outside the agent's client policies and system prompts.

---

## Telemetry Semantics: Quotas vs. Session Token Counters

Token Runway reports **provider rate-limit windows, monthly quota ceilings, and spend limits**, *not* cumulative prompt token counts:
- **Measured Quotas**: Rolling time windows (e.g. Claude 5-hour, Gemini weekly) and monthly plan caps (e.g. GitHub Copilot chat/completions) where percent used and reset countdowns are measured directly.
- **Credit Limits & Spend**: OpenRouter balance tracking where spend vs set credit limit is monitored.
- **Access & Status Checks**: Endpoints like OpenAI API Key validation report model access and connectivity (`is_quota=False`). When only status telemetry is available, `assess_action` returns an explicit `"unknown"` verdict to avoid false headroom reassurance.

---

## Provider Integration Notes & Known Limitations

Token Runway interfaces with developer tools and APIs using standard, lightweight harvesters:
- **GitHub Copilot**: Uses `gh api /copilot_internal/user` (an internal endpoint utilized by official Copilot IDE extensions). If GitHub alters this endpoint's schema, Token Runway gracefully reports the provider as unavailable without crashing.
- **Anthropic Claude**: Reads session tokens from `~/.claude/` or `CLAUDE_CODE_TOKEN`. If your session expires, run `claude` to re-authenticate.
- **Google Gemini / Antigravity**: Parses JSON telemetry from `agy usage --json`. Requires the Antigravity CLI in `$PATH`.
- **Google Colab**: Parses stdout of `colab usage`. Requires `colab` CLI in `$PATH`.
- **OpenRouter**: Uses public endpoint `/api/v1/auth/key`. Unlimited keys report total spend without synthetic quota ceilings.
- **OpenAI**: Uses `/v1/models` to confirm key validity and tier. Does not report live token consumption.

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
