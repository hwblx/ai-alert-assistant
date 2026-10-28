import json
import re
from typing import Any

from pydantic_ai import Agent
import logging

from app.services.llm import model
from app.schemas import AlertAssessment, SeverityLevel, ConfidenceLevel

logger = logging.getLogger(__name__)
logger.setLevel(level=logging.WARNING)


INSTRUCTIONS = """
• Act as a senior Site Reliability Engineer / incident responder.
• Analyze the incoming alert payload (name, severity, description, metrics, and generator
 details).
• Produce concise, actionable root cause hypotheses and ordered mitigation steps.
• Ensure the sanitized summary omits sensitive infrastructure details (internal IPs,
 credentials, tokens).
""" 

agent = Agent(
    model,
    instructions=INSTRUCTIONS,
    output_type=AlertAssessment,
)

async def analyze_single_pass(raw_payload: dict[str, Any]) -> AlertAssessment:
    sanitized_payload = _sanitize_raw_payload(raw_payload)
    alert_json = json.dumps(sanitized_payload, indent=2)

    result = await agent.run(f"Process this alert: {alert_json}")
    return result.output


async def analyze_sequentially(raw_payload: dict[str, Any]) -> AlertAssessment:
    sanitized_payload = _sanitize_raw_payload(raw_payload)
    alert_json = json.dumps(sanitized_payload, indent=2)
    trimmed_context = _format_trimmed_context(raw_payload)
    
    cause = await prompt_cause(alert_json)
    actions = await prompt_actions(trimmed_context, cause)
    classification = await prompt_classification(trimmed_context, cause)
    summary = await prompt_summary(cause, actions)

    return AlertAssessment(
        assessed_severity=classification["severity"],
        root_cause_hypothesis=cause,
        recommended_actions=actions,
        sanitized_summary=summary,
        confidence=classification["confidence"]
    )


ROOT_CAUSE_INSTRUCTIONS = """
Act as a senior Site Reliability Engineer.
Analyze the alert symptoms, metrics, and event details.
Provide a concise, direct root cause hypothesis (2 to 4 sentences).
Do not cite raw URLs, query parameters, container IDs, hostnames, internal IPs, or credentials;
describe components and issues conceptually.
Do not include conversational filler, greetings, or markdown headers.
"""

root_cause_agent = Agent(
    model,
    instructions=ROOT_CAUSE_INSTRUCTIONS,
    output_type=str,
)

async def prompt_cause(alert_json: str) -> str:
    result = await root_cause_agent.run(
        f"Analyze this alert and identify the root cause:\n{alert_json}"
    )
    logger.warning("prompt cause ...")
    
    return result.output.strip()


ACTIONS_INSTRUCTIONS = """
Act as an incident responder.
Given an alert context and a root cause hypothesis, generate an ordered list of 3 to 5 clear,
concrete mitigation steps for an on-call engineer.
Provide only actionable steps as a bulleted list, one step per line.
Keep each step concise (under 20 words).
Do not include conversational filler, notes, or markdown headers.
"""

actions_agent = Agent(
    model,
    instructions=ACTIONS_INSTRUCTIONS,
    output_type=str,
)

def _parse_action_steps(raw_text: str) -> list[str]:
    steps: list[str] = []
    for line in raw_text.splitlines():
        cleaned = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip()
        if cleaned:
            steps.append(cleaned)
    return steps or [raw_text.strip()]

async def prompt_actions(trimmed_context: str, root_cause: str) -> list[str]:
    logger.warning("prompt actions ...")

    prompt = (
        f"{trimmed_context}\n\n"
        f"Diagnosed Root Cause:\n{root_cause}\n\n"
        "Provide ordered mitigation steps to resolve this incident."
    )
    result = await actions_agent.run(prompt)
    return _parse_action_steps(result.output)


CLASSIFICATION_INSTRUCTIONS = """
Act as an incident triager.
Evaluate the alert context and the diagnosed root cause hypothesis.
Classify:
1. severity: one of critical, warning, info
2. confidence: one of high, medium, low

Output format (exactly two lines, no markdown, no other text):
severity: <critical|warning|info>
confidence: <high|medium|low>
"""

classification_agent = Agent(
    model,
    instructions=CLASSIFICATION_INSTRUCTIONS,
    output_type=str,
)

def _parse_classification(raw_text: str) -> dict[str, Any]:
    severity = SeverityLevel.WARNING
    confidence = ConfidenceLevel.MEDIUM

    sev_match = re.search(r"severity\s*:\s*(\w+)", raw_text, re.IGNORECASE)
    if sev_match:
        val = sev_match.group(1).lower()
        if val in {s.value for s in SeverityLevel}:
            severity = SeverityLevel(val)
    else:
        for s in SeverityLevel:
            if re.search(rf"\b{s.value}\b", raw_text, re.IGNORECASE):
                severity = s
                break

    conf_match = re.search(r"confidence\s*:\s*(\w+)", raw_text, re.IGNORECASE)
    if conf_match:
        val = conf_match.group(1).lower()
        if val in {c.value for c in ConfidenceLevel}:
            confidence = ConfidenceLevel(val)
    else:
        for c in ConfidenceLevel:
            if re.search(rf"\b{c.value}\b", raw_text, re.IGNORECASE):
                confidence = c
                break

    return {
        "severity": severity,
        "confidence": confidence,
    }


async def prompt_classification(trimmed_context: str, root_cause: str) -> dict[str, Any]:
    logger.warning("prompt classification ...")

    prompt = (
        f"{trimmed_context}\n\n"
        f"Root Cause Hypothesis:\n{root_cause}\n\n"
        "Assess the severity and your confidence level."
    )
    result = await classification_agent.run(prompt)
    return _parse_classification(result.output)


SANITIZED_SUMMARY_INSTRUCTIONS = """
Act as a technical communications specialist for incident response.
Given a diagnosed root cause and recommended mitigation actions, produce a concise incident
summary in clean markdown (under 150 words).
Ensure the summary strictly omits or redacts sensitive infrastructure details, including
internal IP addresses, container IDs, hostnames, ports, credentials, and tokens.
Do not wrap your response in code block fences (no ```).
Do not prefix the response with the word 'markdown'.
Output clean, direct markdown headings and bullet points.
"""

sanitized_summary_agent = Agent(
    model,
    instructions=SANITIZED_SUMMARY_INSTRUCTIONS,
    output_type=str,
)

async def prompt_summary(
    root_cause: str,
    recommended_actions: list[str],
) -> str:
    logger.warning("prompt summary ...")

    actions_formatted = "\n".join(f"- {action}" for action in recommended_actions)
    prompt = (
        f"Root Cause Hypothesis:\n{root_cause}\n\n"
        f"Recommended Mitigation Actions:\n{actions_formatted}\n\n"
        "Generate the concise, sanitized markdown incident summary."
    )
    result = await sanitized_summary_agent.run(prompt)
    return _clean_markdown(result.output)


def _sanitize_raw_payload(raw_payload: dict[str, Any]) -> dict[str, Any]:
    excluded_keys = {"generator_url"}
    return {k: v for k, v in raw_payload.items() if k not in excluded_keys}


def _format_trimmed_context(raw_payload: dict[str, Any]) -> str:
    name = raw_payload.get("name", "Unknown Alert")
    severity = raw_payload.get("severity", "Unknown")
    summary = raw_payload.get("summary") or raw_payload.get("description", "No details")
    return f"Alert: {name}\nReported Severity: {severity}\nSummary: {summary}"


def _clean_markdown(raw_text: str) -> str:
    text = raw_text.strip()

    # Strip code block fences or leading language tags (e.g., ```markdown or ``` or bare "markdown\n")
    text = re.sub(r"^```(?:markdown)?\s*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n?```\s*$", "", text)
    text = re.sub(r"^markdown\s*\n", "", text, flags=re.IGNORECASE)

    # Deterministic scrubbing for internal URLs, container/host hashes, and local IPs
    text = re.sub(r"https?://[^\s)\]]+", "[redacted-url]", text)
    text = re.sub(r"\b[a-f0-9]{12,64}(?::\d+)?\b", "[internal-host]", text)
    text = re.sub(r"\b(?:10\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])|192\.168)\.\d{1,3}\.\d{1,3}\b", "[internal-ip]", text)

    return text.strip()


