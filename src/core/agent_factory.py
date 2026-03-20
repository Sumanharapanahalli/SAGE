"""
agent_factory.py — JD-to-agent-config extractor using LLM metaprompt.

Reads a job description (or plain-language role description) and returns
a structured RoleConfig dict ready for the /agents/hire HITL proposal.
"""
import json
import logging

logger = logging.getLogger(__name__)

try:
    from src.core.llm_gateway import llm_gateway
except Exception:
    llm_gateway = None  # type: ignore[assignment]

METAPROMPT = """You are an AI agent architect for the SAGE Framework.
Your job is to read a job description or role description and convert it into
a precise SAGE agent configuration.

A SAGE agent configuration has:
1. role_key        — snake_case unique identifier (e.g. "security_reviewer")
2. name            — Display name (e.g. "Security Reviewer")
3. description     — One-sentence description of what this agent does
4. system_prompt   — The LLM persona + instructions (3-6 sentences):
   - Open: "You are a [seniority] [role] with expertise in [domain]."
   - List 3-5 specific responsibilities from the JD
   - Output format: "Always return strict JSON with keys: ..."
   - End: "Do not output markdown, prose, or any text outside the JSON object."
5. task_types      — List of objects with keys "name" (SCREAMING_SNAKE_CASE) and "description" (one line)
   - Max 5 task types
   - Each maps to one specific input type (log, diff, report, metric)
6. output_schema   — Dict of field_name to "type or description" the agent always returns
   - Always include: severity (RED|AMBER|GREEN), summary, recommended_action
   - Add domain-specific fields from the JD
7. eval_case       — Object with keys "input" (a realistic test input string) and "expected_keywords" (list of words)

Solution context (if provided): {solution_context}

Rules:
- Only return a single JSON object. No markdown, no explanation, no extra text.
- role_key must be snake_case, all lowercase, no spaces.
- task_type names must be SCREAMING_SNAKE_CASE.
- The output_schema field must be present in the returned JSON.

Job description or role description:
{jd_text}

Return ONLY the JSON object:"""


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        raw = "\n".join(lines[1:end])
    return raw.strip()


def jd_to_role_config(jd_text: str, solution_context: str = "") -> dict:
    """
    Extract a structured role config dict from a job description using the LLM.

    Returns a dict with keys: role_key, name, description, system_prompt,
    task_types (list), output_schema (dict), eval_case (dict).

    Raises:
        RuntimeError: if llm_gateway is unavailable
        ValueError: if LLM response cannot be parsed as valid JSON
    """
    if llm_gateway is None:
        raise RuntimeError("LLM gateway is not configured.")

    prompt = METAPROMPT.format(
        jd_text=jd_text.strip(),
        solution_context=solution_context.strip() or "general purpose",
    )
    try:
        raw = llm_gateway.generate(prompt)
        cleaned = _strip_fences(raw)
        config = json.loads(cleaned)
        if not isinstance(config, dict):
            raise ValueError(f"Expected JSON object, got {type(config).__name__}")
        # Ensure required keys are present
        required = {"role_key", "name", "description", "system_prompt", "task_types"}
        missing = required - config.keys()
        if missing:
            raise ValueError(f"LLM response missing required keys: {missing}")
        return config
    except json.JSONDecodeError as exc:
        raise ValueError(f"Could not parse LLM response as JSON: {exc}") from exc
