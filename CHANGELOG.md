# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.2] - 2026-10-31

### Fixed
- **Uncertainty & Availability Handling**: `assess_action` returns verdict `"unknown"` when all providers are unavailable or reporting no active windows, eliminating false reassurance of 0% utilization.
- **Strict Tool Argument Validation**: `server.py` validates `refresh` (must be boolean), `intensity` (low/medium/high), `action_type`, `max_budget`, and rejects unknown provider names with JSON-RPC `-32602` (`INVALID_PARAMS`).
- **Config Overwrite Protection**: `config_injector.py` detects malformed JSON and non-object roots, fails safely without overwriting, and generates an automatic `.bak` backup before modifying.
- **Centralized Versioning**: Fixed hardcoded versions in `serverInfo` and modules, reading from single source `token_runway.__version__`.
- **Cache Transparency & Freshness**: Added `is_cached` and `cache_age_seconds` to `ProviderReading` when serving fallback readings during API rate limits.
- **Ruff Linting**: Cleaned up all Ruff findings across the codebase and added automated Ruff lint job to CI workflow.
- **Test Suite in CI**: Updated test assertions to accommodate environments without configured provider credentials, and verified entry points in CI.
- **PyPI Release Idempotency**: Added `skip-existing: true` in release workflow.

### Added
- **Action-Type Sensitivity in Advice**: Differentiates `subagent_fanout` (high consumption multiplier) from `targeted_edit` (lightweight), adjusting verdict and strategies accordingly.
- **Provider-Targeted Refreshes**: `fetch_all_runways` and `check_runway` can selectively refresh only the requested provider.
- **CLI Flags**: Added `--json`, `--no-color`, and `--provider` to `check` and `doctor`.

## [0.2.0] - 2026-10-31

### Added
- **OpenRouter Harvester**: Credit limit, cumulative spend balance, and rate limit tracking via `/api/v1/auth/key`.
- **OpenAI API Harvester**: Key authentication validation and model tier accessibility checks via `/v1/models`.
- **Live Terminal HUD (`token-runway watch`)**: Interactive terminal watch mode (`top` for AI quotas) with ANSI progress bars and countdown timers.
- **Zero-Dependency Web HUD (`token-runway dashboard`)**: Built-in local dark-mode dashboard at `http://localhost:7890` with real-time polling and an interactive Assess Action Simulator.
- **Project Rules Generator (`token-runway init-rules`)**: Embeds meta-cognitive self-governance instructions into `CLAUDE.md`, `.cursorrules`, `.windsurfrules`, and `AGENTS.md`.
- **Safety Guardrails & Strict Throttling**: Support for `--max-budget` and `--strict` to prevent agents from running operations when quota utilization crosses user thresholds.

## [0.1.1] - 2026-10-31

### Fixed
- Fixed `pyproject.toml` `project.license` table syntax for Python 3.8 / older `setuptools` build compatibility.

## [0.1.0] - 2026-10-31

### Added
- Initial release of **Token Runway** MCP server and CLI.
- Zero-dependency Model Context Protocol (MCP 2024-11-05) implementation over stdio.
- Harvesters for:
  - **Anthropic Claude**: OAuth usage endpoint, 5-hour current and 7-day weekly windows, local cache fallback.
  - **Google Gemini**: Flash/Pro 5-hour and weekly limits, Argon weekly quota via `agy`.
  - **Antigravity**: Claude + GPT third-party limits via `agy`.
  - **GitHub Copilot**: Chat Monthly, Completions Monthly, Premium requests via `gh api /copilot_internal/user`.
  - **Google Colab**: Compute unit balance, burn rate, and active runtimes via `colab usage`.
- MCP Tools: `check_runway` and `assess_action` (meta-cognitive reasoning engine).
- MCP Resource: `runway://status`.
- MCP Prompt: `runway_governance`.
- Multi-IDE auto-injector (`token-runway inject`) supporting Claude Desktop, Cursor, Claude Code, Antigravity, and Windsurf.
- Interactive CLI tools: `token-runway check` and `token-runway doctor`.
