import time
from typing import Dict, Any, List
from src.telemetry.logger import logger


# Price table: USD per 1,000 tokens, split by input (prompt) and output (completion).
# Real published rates so the "Cost Analysis" metric in EVALUATION.md is meaningful.
# Matched by substring on the model name (lower-cased), longest match wins.
PRICING_PER_1K = {
    # OpenAI
    "gpt-4o-mini":   {"input": 0.00015, "output": 0.00060},
    "gpt-4o":        {"input": 0.00250, "output": 0.01000},
    # Google Gemini
    "gemini-2.5-pro":   {"input": 0.00125, "output": 0.01000},
    "gemini-2.5-flash": {"input": 0.00030, "output": 0.00250},
    "gemini-2.0-flash": {"input": 0.00010, "output": 0.00040},
    # Local model: runs on your own CPU -> no API cost.
    "phi-3": {"input": 0.0, "output": 0.0},
}

# Used when a model name isn't in the table (e.g. router/mimo gateways).
DEFAULT_PRICING = {"input": 0.0005, "output": 0.0015}


class PerformanceTracker:
    """
    Tracking industry-standard metrics for LLMs.
    """
    def __init__(self):
        self.session_metrics = []

    def track_request(self, provider: str, model: str, usage: Dict[str, int], latency_ms: int):
        """
        Logs a single request metric to our telemetry.
        """
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", 0) or (prompt_tokens + completion_tokens)

        metric = {
            "provider": provider,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            # Completion/prompt ratio: high "chatter" before tool calls inflates cost.
            "completion_ratio": round(completion_tokens / total_tokens, 3) if total_tokens else 0.0,
            "latency_ms": latency_ms,
            "cost_estimate": self._calculate_cost(model, usage),
        }
        self.session_metrics.append(metric)
        logger.log_event("LLM_METRIC", metric)

    def _lookup_pricing(self, model: str) -> Dict[str, float]:
        """Find the price entry whose key best matches the model name."""
        name = (model or "").lower()
        best_key = None
        for key in PRICING_PER_1K:
            if key in name and (best_key is None or len(key) > len(best_key)):
                best_key = key
        return PRICING_PER_1K[best_key] if best_key else DEFAULT_PRICING

    def _calculate_cost(self, model: str, usage: Dict[str, int]) -> float:
        """
        Estimate USD cost from real per-model pricing, charging input and
        output tokens separately (output tokens are usually 3-4x pricier).
        """
        pricing = self._lookup_pricing(model)
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        cost = (prompt_tokens / 1000) * pricing["input"] + (completion_tokens / 1000) * pricing["output"]
        return round(cost, 6)

    def session_summary(self) -> Dict[str, Any]:
        """Aggregate totals for the current session (for end-of-run reporting)."""
        return {
            "requests": len(self.session_metrics),
            "total_tokens": sum(m["total_tokens"] for m in self.session_metrics),
            "total_cost_usd": round(sum(m["cost_estimate"] for m in self.session_metrics), 6),
            "avg_latency_ms": round(
                sum(m["latency_ms"] for m in self.session_metrics) / len(self.session_metrics)
            ) if self.session_metrics else 0,
        }


# Global tracker instance
tracker = PerformanceTracker()
