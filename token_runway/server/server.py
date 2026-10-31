"""Stdio-based Model Context Protocol (MCP) server for Token Runway."""

from __future__ import annotations

import json
import sys
import time
from typing import Any, Dict, List, Optional

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


class TokenRunwayServer:
    """Zero-dependency stdio MCP server exposing token quotas and advice."""

    def __init__(self, cache_ttl: float = 30.0):
        self.cache_ttl = cache_ttl
        self._cached_readings: Optional[Dict[str, ProviderReading]] = None
        self._cache_time: float = 0.0

    def get_readings(self, force_refresh: bool = False) -> Dict[str, ProviderReading]:
        now = time.monotonic()
        if force_refresh or self._cached_readings is None or (now - self._cache_time) > self.cache_ttl:
            self._cached_readings = fetch_all_runways()
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
                        "version": "0.1.0",
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
                    "Inspect current token quotas, utilization percentages, remaining capacity, "
                    "and reset countdowns across Claude, Gemini, Antigravity, GitHub Copilot, and Colab."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "refresh": {
                            "type": "boolean",
                            "description": "Bypass cache and force an immediate re-fetch from all provider CLIs/APIs.",
                            "default": False,
                        },
                        "provider": {
                            "type": "string",
                            "description": "Optional specific provider to filter ('claude', 'gemini', 'antigravity', 'copilot', 'colab').",
                        },
                    },
                },
            },
            {
                "name": "assess_action",
                "description": (
                    "Meta-cognitive evaluation of whether a proposed action (e.g. running multiple parallel subagents, "
                    "reading massive files, or continuous test loops) is justified given current remaining quotas and reset timers."
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
                            "description": "Target provider whose limits you want to evaluate against (optional).",
                        },
                    },
                },
            },
        ]

    def _call_tool(self, req_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        name = params.get("name")
        args = params.get("arguments") or {}

        if name == "check_runway":
            force = bool(args.get("refresh", False))
            provider_filter = args.get("provider")
            readings = self.get_readings(force_refresh=force)

            if provider_filter and provider_filter.lower() in readings:
                data = {provider_filter.lower(): readings[provider_filter.lower()].to_dict()}
            else:
                data = {k: v.to_dict() for k, v in readings.items()}

            text = json.dumps(data, indent=2)
            return make_response(req_id, {"content": [{"type": "text", "text": text}]})

        if name == "assess_action":
            action_type = args.get("action_type", "general")
            intensity = args.get("intensity", "medium")
            provider = args.get("provider")
            readings = self.get_readings()
            assessment = evaluate_action_feasibility(readings, action_type, intensity, provider)
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
                "Before initiating resource-heavy operations (e.g. fanning out multiple subagents, dumping whole files >500 lines, "
                "or running unbounded search loops), call `assess_action` or `check_runway`.\n\n"
                "- If utilization is >=95%: Switch to quota-preserving strategies (surgical line edits, targeted ripgrep, sequential steps).\n"
                "- If reset is within 20 minutes and quota is high: Defer heavy work and perform lightweight verification.\n"
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
