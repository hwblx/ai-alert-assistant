import json
import re
from typing import Any
import logging
from abc import ABC, abstractmethod

from pydantic_ai import Agent

from app.services.llm import get_model
from app.schemas import AlertAssessment, SeverityLevel, ConfidenceLevel
from app.settings import settings

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    @abstractmethod
    async def execute(self, *args, **kwargs) -> Any:
        ...


class DiagnosticAgent(BaseAgent):
    instructions: str
    output_type: type

    def __init__(self, model):
        self.agent = Agent(
            model,
            instructions=type(self).instructions,
            output_type=type(self).output_type,
        )


def get_agent() -> BaseAgent:
    model = get_model()

    if settings.MULTIPASS_AGENT:
        return MultiPassAgent(model)
    else:
        return SinglePassAgent(model)


def _sanitize_raw_payload(raw_payload: dict[str, Any]) -> dict[str, Any]:
    excluded_keys = {"generator_url"}
    return {k: v for k, v in raw_payload.items() if k not in excluded_keys}


class SinglePassAgent(DiagnosticAgent):
    instructions = """
    Act as a senior Site Reliability Engineer / incident responder.
    Analyze the incoming alert payload (name, severity, description, metrics, and generator
     details).
    Produce concise, actionable root cause hypotheses and ordered mitigation steps.
    Ensure the sanitized summary omits sensitive infrastructure details (internal IPs,
     credentials, tokens).
    """
    output_type = AlertAssessment

    async def execute(self, raw_payload: dict[str, Any]) -> AlertAssessment:
        logger.debug("Executing single-pass diagnostic analysis")

        sanitized_payload = _sanitize_raw_payload(raw_payload)
        alert_json = json.dumps(sanitized_payload, indent=2)

        result = await self.agent.run(f"Process this alert: {alert_json}")
        return result.output


class MultiPassAgent(BaseAgent):
    def __init__(self, model):
        self.root_cause_agent = RootCauseAgent(model)
        self.actions_agent = ActionsAgent(model)
        self.classification_agent = ClassificationAgent(model)
        self.summary_agent = SummaryAgent(model)

    async def execute(self, raw_payload: dict[str, Any]) -> AlertAssessment:
        logger.debug("Executing multi-pass diagnostic analysis")

        sanitized_payload = _sanitize_raw_payload(raw_payload)
        alert_json = json.dumps(sanitized_payload, indent=2)
        trimmed_context = self._format_trimmed_context(raw_payload)

        cause = await self.root_cause_agent.execute(alert_json)
        actions = await self.actions_agent.execute(trimmed_context, cause)
        classification = await self.classification_agent.execute(trimmed_context, cause)
        summary = await self.summary_agent.execute(cause, actions)

        return AlertAssessment(
            assessed_severity=classification["severity"],
            root_cause_hypothesis=cause,
            recommended_actions=actions,
            sanitized_summary=summary,
            confidence=classification["confidence"]
        )

    @staticmethod
    def _format_trimmed_context(raw_payload: dict[str, Any]) -> str:
        name = raw_payload.get("name", "Unknown Alert")
        severity = raw_payload.get("severity", "Unknown")
        summary = raw_payload.get("summary") or raw_payload.get("description", "No details")
        return f"Alert: {name}\nReported Severity: {severity}\nSummary: {summary}"


class RootCauseAgent(DiagnosticAgent):
    instructions = """
    Act as a senior Site Reliability Engineer.
    Analyze the alert symptoms, metrics, and event details.
    Provide a concise, direct root cause hypothesis (2 to 4 sentences).
    Do not cite raw URLs, query parameters, container IDs, hostnames, internal IPs, or credentials;
    describe components and issues conceptually.
    Do not include conversational filler, greetings, or markdown headers.
    """
    output_type = str

    async def execute(self, alert_json: str) -> str:
        logger.debug("Generating root cause hypothesis")

        result = await self.agent.run(
            f"Analyze this alert and identify the root cause:\n{alert_json}"
        )

        return result.output.strip()


class ActionsAgent(DiagnosticAgent):
    instructions = """
    Act as an incident responder.
    Given an alert context and a root cause hypothesis, generate an ordered list of 3 to 5 clear,
    concrete mitigation steps for an on-call engineer.
    Provide only actionable steps as a bulleted list, one step per line.
    Keep each step concise (under 20 words).
    Do not include conversational filler, notes, or markdown headers.
    """
    output_type = str

    async def execute(self, trimmed_context: str, root_cause: str) -> list[str]:
        logger.debug("Generating recommended mitigation actions")

        prompt = (
            f"{trimmed_context}\n\n"
            f"Diagnosed Root Cause:\n{root_cause}\n\n"
            "Provide ordered mitigation steps to resolve this incident."
        )
        result = await self.agent.run(prompt)
        return self._parse_action_steps(result.output)

    @staticmethod
    def _parse_action_steps(raw_text: str) -> list[str]:
        steps: list[str] = []
        for line in raw_text.splitlines():
            cleaned = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip()
            if cleaned:
                steps.append(cleaned)
        return steps or [raw_text.strip()]


class ClassificationAgent(DiagnosticAgent):
    instructions = """
    Act as an incident triager.
    Evaluate the alert context and the diagnosed root cause hypothesis.
    Classify:
    1. severity: one of critical, warning, info
    2. confidence: one of high, medium, low

    Output format (exactly two lines, no markdown, no other text):
    severity: <critical|warning|info>
    confidence: <high|medium|low>
    """
    output_type = str

    async def execute(self, trimmed_context: str, root_cause: str) -> dict[str, Any]:
        logger.debug("Classifying incident severity and assessment confidence")

        prompt = (
            f"{trimmed_context}\n\n"
            f"Root Cause Hypothesis:\n{root_cause}\n\n"
            "Assess the severity and your confidence level."
        )
        result = await self.agent.run(prompt)
        return self._parse_classification(result.output)

    @staticmethod
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


class SummaryAgent(DiagnosticAgent):
    instructions = """
    Act as a technical communications specialist for incident response.
    Given a diagnosed root cause and recommended mitigation actions, produce a concise incident
    summary in clean markdown (under 150 words).
    Ensure the summary strictly omits or redacts sensitive infrastructure details, including
    internal IP addresses, container IDs, hostnames, ports, credentials, and tokens.
    Do not wrap your response in code block fences (no ```).
    Do not prefix the response with the word 'markdown'.
    Output clean, direct markdown headings and bullet points.
    """
    output_type = str

    async def execute(
        self,
        root_cause: str,
        recommended_actions: list[str],
    ) -> str:
        logger.debug("Generating sanitized incident summary")

        actions_formatted = "\n".join(f"- {action}" for action in recommended_actions)
        prompt = (
            f"Root Cause Hypothesis:\n{root_cause}\n\n"
            f"Recommended Mitigation Actions:\n{actions_formatted}\n\n"
            "Generate the concise, sanitized markdown incident summary."
        )
        result = await self.agent.run(prompt)
        return self._clean_markdown(result.output)

    @staticmethod
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


