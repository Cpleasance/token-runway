"""Meta-cognitive reasoning engine for assessing action feasibility against active quotas."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from token_runway.sources.base import ProviderReading


def evaluate_action_feasibility(
    readings: Dict[str, ProviderReading],
    action_type: str = "general",
    intensity: str = "medium",  # "low", "medium", "high"
    target_provider: Optional[str] = None,
) -> Dict[str, Any]:
    """Evaluate whether an agent should proceed with a resource-intensive action."""
    action_type = action_type.lower()
    intensity = intensity.lower()

    # Identify primary active provider constraints
    providers_to_check = [target_provider] if target_provider and target_provider in readings else list(readings.keys())

    highest_used_pct = 0
    most_constrained_provider = None
    most_constrained_window = None
    mins_to_reset = None

    for p_name in providers_to_check:
        reading = readings.get(p_name)
        if not reading or not reading.available:
            continue
        for w in reading.windows:
            if w.used_pct is not None and w.used_pct > highest_used_pct:
                highest_used_pct = w.used_pct
                most_constrained_provider = reading.display_name
                most_constrained_window = w.name
                mins_to_reset = w.resets_in_minutes

    recommendation = "proceed"
    strategies: List[str] = []
    reasoning: str = ""

    if highest_used_pct >= 95:
        recommendation = "pause_or_downgrade"
        reasoning = (
            f"Quota is critically constrained ({highest_used_pct}% used on {most_constrained_provider} {most_constrained_window})."
        )
        if mins_to_reset is not None and mins_to_reset <= 30:
            strategies.append(
                f"Window resets in ~{mins_to_reset} minutes. Defer heavy work and perform lightweight local tasks."
            )
        strategies.append("Prohibit parallel subagent fan-outs; execute one step at a time.")
        strategies.append("Read narrow line ranges (under 100 lines) instead of loading full files into context.")
        strategies.append("Route subagent prompts to lightweight models (Flash/Haiku) if model selection is supported.")
    elif highest_used_pct >= 80:
        if intensity == "high":
            recommendation = "downgrade_strategy"
            reasoning = (
                f"Quota headroom is tight ({highest_used_pct}% used on {most_constrained_provider}). High-intensity operations risk lockouts."
            )
            strategies.append("Downgrade multi-agent broad searches to targeted ripgrep / grep commands.")
            strategies.append("Summarize long context before launching further turns.")
        else:
            recommendation = "proceed_with_caution"
            reasoning = f"Headroom is moderate ({highest_used_pct}% used). Standard actions permitted."
            strategies.append("Monitor token usage after this turn.")
    else:
        recommendation = "proceed"
        reasoning = f"Healthy headroom ({highest_used_pct}% maximum utilization across active providers)."
        strategies.append("Full operational capacity available for multi-agent workflows and deep research.")

    return {
        "verdict": recommendation,
        "max_utilization_pct": highest_used_pct,
        "bottleneck": {
            "provider": most_constrained_provider,
            "window": most_constrained_window,
            "resets_in_minutes": mins_to_reset,
        }
        if most_constrained_provider
        else None,
        "analysis": reasoning,
        "preservation_strategies": strategies,
    }
