"""Stdio-based Model Context Protocol (MCP) server for Token Runway."""

from __future__ import annotations

import json
import sys
import time
from typing import Any, Dict, List, Optional

from token_runway import __version__
from token_runway.server.advice import evaluate_action_feasibility
from token_runway.server.protocol import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    MCP_PROTOCOL_VERSION,
    METHOD_NOT_FOUND,
    make_error,
    make_response,
    write_message,
)
from token_runway.sources import fetch_all_runways
from token_runway.sources.base import ProviderReading

SUPPORTED_PROVIDERS = {"claude", "gemini", "antigravity", "copilot", "colab", "openrouter", "openai"}


class TokenRunwayServer:
    """Zero-dependency stdio MCP server exposing token quotas and advice."""

    def __init__(
        self,
        cache_ttl: float = 30.0,
        max_budget: Optional[float] = None,
        strict: bool = False,
    ):
        self.cache_ttl = cache_ttl
        self.max_budget = max_budget
        self.strict = strict
        self._cached_readings: Optional[Dict[str, ProviderReading]] = None
        self._cache_time: float = 0.0

    def get_readings(
        self,
        force_refresh: bool = False,
        provider: Optional[str] = None,
    ) -> Dict[str, ProviderReading]:
        now = time.monotonic()
        if self._cached_readings is None:
            self._cached_readings = fetch_all_runways(provider=None)
            self._cache_time = now
            return self._cached_readings

        if force_refresh:
            if provider:
                fresh = fetch_all_runways(provider=provider)
                self._cached_readings.update(fresh)
            else:
                self._cached_readings = fetch_all_runways(provider=None)
                self._cache_time = now
        elif (now - self._cache_time) > self.cache_ttl:
            self._cached_readings = fetch_all_runways(provider=None)
            self._cache_time = now

        return self._cached_readings

    def handle_request(self, req: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(req, dict) or req.get("jsonrpc") != "2.0":
            return make_error(req.get("id") if isinstance(req, dict) else None, INVALID_REQUEST, "Invalid JSON-RPC request")

        method = req.get("method")
        req_id = req.get("id")
        params = req.get("params") or {}

        # Notifications (no id)
        if req_id is None:
            if method == "notifications/initialized":
                return None
            return None

        # RPC Methods
        if method == "initialize":
            return make_response(
                req_id,
                {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {
                        "tools": {},
                        "resources": {},
                        "prompts": {},
                    },
                    "serverInfo": {
                        "name": "token-runway",
                        "version": __version__,
                    },
                },
            )

        if method == "ping":
            return make_response(req_id, {})

        if method == "tools/list":
            return make_response(req_id, {"tools": self._list_tools()})

        if method == "tools/call":
            return self._call_tool(req_id, params)

        if method == "resources/list":
            return make_response(req_id, {"resources": self._list_resources()})

        if method == "resources/read":
            return self._read_resource(req_id, params)

        if method == "prompts/list":
            return make_response(req_id, {"prompts": self._list_prompts()})

        if method == "prompts/get":
            return self._get_prompt(req_id, params)

        return make_error(req_id, METHOD_NOT_FOUND, f"Method not found: {method}")

    def _list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "check_runway",
                "description": (
                    "Inspect current AI provider rate-limit windows, quota utilization percentages, "
                    "remaining capacity, and reset countdowns across Claude, Gemini, Antigravity, "
                    "GitHub Copilot, Colab, OpenRouter, and OpenAI. "
                    "Note: This reflects provider quota windows and rate limits, not session token counts."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "refresh": {
                            "type": "boolean",
                            "description": "Bypass cache and force an immediate re-fetch from provider CLIs/APIs.",
                            "default": False,
                        },
                        "provider": {
                            "type": "string",
                            "description": "Optional provider filter ('claude', 'gemini', 'antigravity', 'copilot', 'colab', 'openrouter', 'openai').",
                        },
                    },
                },
            },
            {
                "name": "assess_action",
                "description": (
                    "Meta-cognitive evaluation of whether a proposed action (e.g. running multiple parallel subagents, "
                    "reading massive files, or continuous test loops) is justified given current remaining provider quotas and reset timers."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "action_type": {
                            "type": "string",
                            "description": "Type of action planned ('subagent_fanout', 'large_file_dump', 'deep_research', 'targeted_edit', 'continuous_loop').",
                            "default": "general",
                        },
                        "intensity": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                            "description": "Estimated token burn intensity of the action.",
                            "default": "medium",
                        },
                        "provider": {
                            "type": "string",
                            "description": "Target provider whose limits you want to evaluate against ('claude', 'gemini', etc.).",
                        },
                        "max_budget": {
                            "type": "number",
                            "description": "Maximum allowed utilization percentage before pausing (0-100).",
                        },
                        "strict": {
                            "type": "boolean",
                            "description": (
                                "If true, returns an advisory 'reject' verdict when exceeding budget thresholds "
                                "(advisory recommendation; cannot forcibly prevent execution outside agent client policy)."
                            ),
                            "default": False,
                        },
                    },
                },
            },
        ]

    def _call_tool(self, req_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        name = params.get("name")
        args = params.get("arguments") or {}

        if name == "check_runway":
            if "refresh" in args:
                if not isinstance(args["refresh"], bool):
                    return make_error(req_id, INVALID_PARAMS, "Argument 'refresh' must be a boolean (true/false).")
                force = args["refresh"]
            else:
                force = False

            provider_filter = args.get("provider")
            if provider_filter is not None:
                if not isinstance(provider_filter, str) or not provider_filter.strip():
                    return make_error(req_id, INVALID_PARAMS, "Argument 'provider' must be a non-empty string.")
                prov_clean = provider_filter.lower().strip()
                if prov_clean not in SUPPORTED_PROVIDERS:
                    return make_error(
                        req_id,
                        INVALID_PARAMS,
                        f"Unknown provider '{provider_filter}'. Supported providers: {', '.join(sorted(SUPPORTED_PROVIDERS))}.",
                    )
            else:
                prov_clean = None

            readings = self.get_readings(force_refresh=force, provider=prov_clean)
            if prov_clean:
                data = {prov_clean: readings[prov_clean].to_dict()} if prov_clean in readings else {}
            else:
                data = {k: v.to_dict() for k, v in readings.items()}

            text = json.dumps(data, indent=2)
            return make_response(req_id, {"content": [{"type": "text", "text": text}]})

        if name == "assess_action":
            action_type = args.get("action_type", "general")
            if not isinstance(action_type, str) or not action_type.strip():
                return make_error(req_id, INVALID_PARAMS, "Argument 'action_type' must be a non-empty string.")

            intensity = args.get("intensity", "medium")
            if not isinstance(intensity, str) or intensity.lower() not in ("low", "medium", "high"):
                return make_error(
                    req_id,
                    INVALID_PARAMS,
                    f"Invalid intensity '{intensity}'. Must be one of: 'low', 'medium', 'high'.",
                )

            provider = args.get("provider")
            if provider is not None:
                if not isinstance(provider, str) or not provider.strip():
                    return make_error(req_id, INVALID_PARAMS, "Argument 'provider' must be a non-empty string.")
                prov_clean = provider.lower().strip()
                if prov_clean not in SUPPORTED_PROVIDERS:
                    return make_error(
                        req_id,
                        INVALID_PARAMS,
                        f"Unknown provider '{provider}'. Supported providers: {', '.join(sorted(SUPPORTED_PROVIDERS))}.",
                    )
            else:
                prov_clean = None

            budget_limit = args.get("max_budget", self.max_budget)
            if budget_limit is not None and (
                not isinstance(budget_limit, (int, float)) or not (0 <= budget_limit <= 100)
            ):
                return make_error(req_id, INVALID_PARAMS, "Argument 'max_budget' must be a number between 0 and 100.")

            if "strict" in args:
                if not isinstance(args["strict"], bool):
                    return make_error(req_id, INVALID_PARAMS, "Argument 'strict' must be a boolean (true/false).")
                strict_mode = args["strict"]
            else:
                strict_mode = self.strict
            readings = self.get_readings()
            assessment = evaluate_action_feasibility(
                readings,
                action_type=action_type,
                intensity=intensity,
                target_provider=prov_clean,
                max_budget=budget_limit,
                strict=strict_mode,
            )
            text = json.dumps(assessment, indent=2)
            return make_response(req_id, {"content": [{"type": "text", "text": text}]})

        return make_error(req_id, INVALID_PARAMS, f"Unknown tool name: {name}")

    def _list_resources(self) -> List[Dict[str, Any]]:
        return [
            {
                "uri": "runway://status",
                "name": "Live Token Runway Telemetry",
                "description": "Real-time snapshot of remaining limits and countdowns across all providers.",
                "mimeType": "application/json",
            }
        ]

    def _read_resource(self, req_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        uri = params.get("uri")
        if uri == "runway://status":
            readings = self.get_readings()
            data = {k: v.to_dict() for k, v in readings.items()}
            return make_response(
                req_id,
                {
                    "contents": [
                        {
                            "uri": uri,
                            "mimeType": "application/json",
                            "text": json.dumps(data, indent=2),
                        }
                    ]
                },
            )
        return make_error(req_id, INVALID_PARAMS, f"Unknown resource URI: {uri}")

    def _list_prompts(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "runway_governance",
                "description": "Self-governance guidelines for operating under token rate-limits and quotas.",
            }
        ]

    def _get_prompt(self, req_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        prompt_name = params.get("name")
        if prompt_name == "runway_governance":
            prompt_text = (
                "You are an AI agent equipped with real-time awareness of your token quotas via Token Runway.\n\n"
                "Before initiating resource-heavy operations (e.g. fanning out multiple subagents, "
                "dumping whole files >500 lines, or running unbounded search loops), call `assess_action` "
                "or `check_runway`.\n\n"
                "- If utilization is >=95%: Switch to quota-preserving strategies (surgical line edits, "
                "targeted ripgrep, sequential steps).\n"
                "- If reset is within 20 minutes and quota is high: Defer heavy work and perform local verification.\n"
                "- If utilization is <80%: You have full operational headroom."
            )
            return make_response(
                req_id,
                {
                    "description": "Runway governance instructions",
                    "messages": [
                        {
                            "role": "user",
                            "content": {"type": "text", "text": prompt_text},
                        }
                    ],
                },
            )
        return make_error(req_id, INVALID_PARAMS, f"Unknown prompt: {prompt_name}")

    def run_stdio(self) -> None:
        """Run the MCP server event loop over standard input and standard output."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except Exception as e:
                write_message(make_error(None, -32700, f"Parse error: {e}"))
                continue

            try:
                resp = self.handle_request(msg)
                if resp is not None:
                    write_message(resp)
            except Exception as e:
                req_id = msg.get("id") if isinstance(msg, dict) else None
                write_message(make_error(req_id, INTERNAL_ERROR, f"Internal server error: {e}"))
