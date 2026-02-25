"""
src/llm_summary.py
───────────────────
LLM Insight Generator — Groq API (free Llama 3).

The module sends a structured JSON prompt and expects JSON back:
{
  "executive_summary": "...",
  "key_risks": ["...", "..."],
  "recommendations": ["...", "..."],
  "outlook": "..."
}

Robustness features
────────────────────
• Retry with exponential back-off (configurable)
• JSON extraction from partial / markdown-wrapped responses
• Fallback summary when JSON is unparseable
• Token usage tracking + cost estimation logging
"""

import json
import re
import time
from dataclasses import dataclass

from groq import Groq

from src.config import cfg
from src.logger import get_logger

logger = get_logger(__name__)

# Groq free tier — $0 / token but we track for operational awareness
_COST_PER_1K_INPUT = 0.0
_COST_PER_1K_OUTPUT = 0.0


@dataclass
class LLMResult:
    executive_summary: str
    key_risks: list[str]
    recommendations: list[str]
    outlook: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_seconds: float
    estimated_cost_usd: float
    raw_response: str = ""

    def to_dict(self) -> dict:
        return {
            "executive_summary": self.executive_summary,
            "key_risks": self.key_risks,
            "recommendations": self.recommendations,
            "outlook": self.outlook,
        }


class LLMSummary:
    """
    Calls Groq API to generate structured business insights.

    Usage
    ──────
        llm = LLMSummary()
        result = llm.generate(kpi_payload, anomaly_lines)
    """

    def __init__(self) -> None:
        api_key = cfg.get("groq_api_key", "")
        if not api_key:
            raise EnvironmentError(
                "GROQ_API_KEY is not set. Add it to your .env file.\n"
                "Get a free key at https://console.groq.com/"
            )
        self._client = Groq(api_key=api_key)
        self._model: str = cfg.get("groq_model", "llama3-8b-8192")
        self._max_retries: int = int(cfg.get("max_retries", 3))
        logger.info(f"LLMSummary ready — model={self._model}")

    # ── Public ────────────────────────────────────────────────────

    def generate(
        self,
        kpi_payload: dict[str, str],
        anomaly_lines: list[str] | None = None,
    ) -> LLMResult:
        """
        Generate structured business insights from KPI data.

        Parameters
        ──────────
        kpi_payload   : dict from KPIResult.to_prompt_payload()
        anomaly_lines : list of anomaly description strings (may be empty)
        """
        prompt = self._build_prompt(kpi_payload, anomaly_lines or [])
        last_exc: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                return self._call_api(prompt, attempt)
            except Exception as exc:
                last_exc = exc
                if attempt < self._max_retries:
                    wait = 2 ** attempt
                    logger.warning(f"LLM attempt {attempt} failed: {exc}. Retrying in {wait}s…")
                    time.sleep(wait)

        logger.error(f"LLM failed after {self._max_retries} attempts. Using fallback.")
        return self._fallback(kpi_payload, str(last_exc))

    # ── Private ───────────────────────────────────────────────────

    def _call_api(self, prompt: str, attempt: int) -> LLMResult:
        t0 = time.perf_counter()
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.3,
            max_tokens=700,
            top_p=0.9,
        )
        elapsed = round(time.perf_counter() - t0, 2)
        raw = response.choices[0].message.content.strip()
        usage = response.usage

        cost = round(
            usage.prompt_tokens / 1000 * _COST_PER_1K_INPUT
            + usage.completion_tokens / 1000 * _COST_PER_1K_OUTPUT,
            6,
        )

        if cfg.get("enable_token_tracking"):
            logger.info(
                f"LLM tokens — input={usage.prompt_tokens} "
                f"output={usage.completion_tokens} "
                f"total={usage.total_tokens} "
                f"latency={elapsed}s cost=${cost:.6f}"
            )

        parsed = self._parse_json(raw)
        return LLMResult(
            executive_summary=parsed.get("executive_summary", ""),
            key_risks=parsed.get("key_risks", []),
            recommendations=parsed.get("recommendations", []),
            outlook=parsed.get("outlook", ""),
            model=self._model,
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            latency_seconds=elapsed,
            estimated_cost_usd=cost,
            raw_response=raw,
        )

    @staticmethod
    def _parse_json(raw: str) -> dict:
        """Extract JSON from the response, handling markdown code fences."""
        # Strip ```json ... ``` wrappers if present
        match = re.search(r"```(?:json)?\s*([\s\S]+?)```", raw)
        json_str = match.group(1).strip() if match else raw

        # Try direct parse
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

        # Try extracting the first {...} block
        brace_match = re.search(r"\{[\s\S]+\}", json_str)
        if brace_match:
            try:
                return json.loads(brace_match.group())
            except json.JSONDecodeError:
                pass

        logger.warning("Could not parse LLM JSON response; using raw text as summary.")
        return {"executive_summary": raw, "key_risks": [], "recommendations": [], "outlook": ""}

    @staticmethod
    def _build_prompt(kpi: dict[str, str], anomalies: list[str]) -> str:
        anomaly_block = (
            "\n\nAnomalies detected this period:\n" + "\n".join(f"- {a}" for a in anomalies)
            if anomalies
            else "\n\nNo statistical anomalies detected."
        )
        return (
            f"Weekly business KPI data:\n{json.dumps(kpi, indent=2)}"
            f"{anomaly_block}\n\n"
            "Generate the analysis as instructed."
        )

    @staticmethod
    def _fallback(kpi: dict[str, str], error: str) -> LLMResult:
        return LLMResult(
            executive_summary=(
                f"Revenue stood at {kpi.get('revenue', 'N/A')} with "
                f"{kpi.get('revenue_growth', 'N/A')} growth. "
                f"User base reached {kpi.get('users', 'N/A')} "
                f"({kpi.get('user_growth', 'N/A')} growth). "
                f"Churn rate: {kpi.get('churn_rate', 'N/A')}."
            ),
            key_risks=["LLM service unavailable — manual review recommended."],
            recommendations=["Retry report generation once API is accessible."],
            outlook="Data-driven outlook unavailable; review KPIs manually.",
            model="fallback",
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            latency_seconds=0.0,
            estimated_cost_usd=0.0,
        )


# ── System prompt ─────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a senior business analyst AI at an early-stage startup.
Your task is to analyse weekly KPI data and produce a structured JSON report.

You MUST respond with ONLY valid JSON — no markdown, no prose outside the JSON.

Required JSON structure:
{
  "executive_summary": "2–3 sentence paragraph summarising performance",
  "key_risks": ["risk 1", "risk 2", "risk 3"],
  "recommendations": ["action 1", "action 2", "action 3"],
  "outlook": "1 sentence forward-looking observation"
}

Guidelines:
- Tone: executive, data-driven, no marketing fluff
- Interpret trends, do not just repeat numbers
- key_risks and recommendations must each have 2–4 items
- If anomalies are listed, reference the most critical one in key_risks
"""
