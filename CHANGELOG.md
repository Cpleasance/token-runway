# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
