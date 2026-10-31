# AI Alert Assistant

A lightweight backend service designed to receive alert webhooks (such as from Prometheus or Alertmanager routed through Hookdeck), deduplicate incoming incidents, generate structured AI diagnostic summaries, and dispatch enriched incident reports.

This repository is a work sample and demonstration project built to explore asynchronous webhook ingestion, structured LLM prompting with validation, and clean service orchestration in Python.

---
![Flowchart](backend/.doc/flowchart.png)

---

## Architecture & Workflow

AI Alert Assistant decouples webhook ingestion from LLM diagnosis and notification delivery through an event-driven architecture. Hookdeck serves as a bidirectional webhook gateway—buffering inbound alerts from Prometheus Alertmanager and fanning out outbound incident reports to downstream endpoints (such as GitHub Issues and Resend for email delivery).

<p align="center">
  <a href="backend/.doc/c4-context.png">
    <img src="backend/.doc/c4-context.png" height="500" alt="C4 Context Diagram" />
  </a>
  <br />
  <small><em>Click image to zoom</em></small>
</p>

### End-to-End Processing Flow

1. **Ingestion & Verification:** Webhook Router validates inbound requests using HMAC SHA-256 signatures.
2. **Deduplication:** Ingestion Service computes a deterministic fingerprint from core identity fields. If a matching alert was received within the lookback window (default 15 minutes), the duplicate is recorded without triggering redundant analysis.
3. **Immediate Acknowledgement:** The endpoint returns an immediate HTTP receipt to satisfy upstream timeouts, offloading inference to asynchronous background processing.
4. **Diagnostic Orchestration:** Alert Processing Orchestrator coordinates the Diagnostic Agent (single-pass or multi-pass pipeline) to analyze symptoms, derive root cause hypotheses, categorize severity, and suggest ordered mitigations.
5. **Sanitization & Outbound Dispatch:** Sensitive infrastructure details (internal IPs, credentials, container IDs) are scrubbed before Notification Dispatcher posts the structured event to Hookdeck for fan-out delivery.

<p align="center">
  <a href="backend/.doc/c4-component.png">
    <img src="backend/.doc/c4-component.png" height="500" alt="C4 Component Diagram" />
  </a>
  <br />
  <small><em>Click image to zoom</em></small>
</p>

### Alert Lifecycle

- **Pending:** Alert received, signature verified, deduplication evaluated, and record stored in SQLite.
- **Analyzing:** The diagnostic agent prompts the LLM to assess symptoms and draft mitigation steps.
- **Notifying:** Diagnostic assessment completed; the outbound notification is being dispatched.
- **Completed:** Notification successfully delivered to the outbound webhook endpoint.
- **Failed:** An error occurred during diagnosis or delivery; the error details are recorded on the alert record.

---

## AI Diagnostic Modes

The service supports two agent implementations configured via `MULTIPASS_AGENT`:

1. **Single-Pass Agent (`MULTIPASS_AGENT=False`):**
   Sends the alert payload in a single prompt to produce an `AlertAssessment` model containing the root cause, suggested actions, sanitized summary, assessed severity, and confidence level. This provides lower latency and lower token consumption.

2. **Multi-Pass Agent (`MULTIPASS_AGENT=True`):**
   Breaks the diagnosis into sequential, specialized prompts:
   - **Root Cause Agent:** Focuses strictly on technical hypothesis generation.
   - **Actions Agent:** Generates concise, ordered mitigation steps.
   - **Classification Agent:** Categorizes incident severity and model confidence.
   - **Summary Agent:** Generates a sanitized markdown summary with deterministic scrubbing rules for sensitive URLs, hashes, and internal IP ranges.

Both local models (via Ollama) and cloud providers (such as OpenRouter) are supported through configuration.

---

## Tech Stack

- **Framework:** [FastAPI](https://fastapi.tiangolo.com/) (asynchronous routing and lifespan management)
- **Database & ORM:** [SQLModel](https://sqlmodel.tiangolo.com/) & [SQLAlchemy](https://www.sqlalchemy.org/) (Async SQLite)
- **AI Agent:** [Pydantic AI](https://ai.pydantic.dev/) (type-safe structured inference)
- **HTTP Client:** [HTTPX](https://www.python-httpx.org/) (asynchronous outbound webhooks with exponential backoff)
- **Validation:** [Pydantic](https://docs.pydantic.dev/) v2
- **Environment & Packaging:** [uv](https://github.com/astral-sh/uv)

---

## Project Structure

```
backend/
├── app/
│   ├── api/
│   │   └── webhooks.py         # Inbound webhook verification and ingestion endpoint
│   ├── database/
│   │   ├── crud.py             # Database access and query functions
│   │   ├── models.py           # SQLModel database tables
│   │   └── session.py          # Async engine, sessionmaker, and lifespan setup
│   ├── services/
│   │   ├── agent.py            # Single-pass and multi-pass Pydantic AI agents
│   │   ├── ingestion.py        # Fingerprint computation and deduplication logic
│   │   ├── llm.py              # Model and provider factory (Ollama, OpenRouter)
│   │   ├── notification.py     # Outbound webhook client with retry logic
│   │   └── orchestrator.py     # Alert lifecycle and workflow orchestration
│   ├── errors.py               # Application-level HTTP and domain exceptions
│   ├── main.py                 # FastAPI application factory and logging setup
│   ├── schemas.py              # Pydantic request/response schemas and enums
│   └── settings.py             # Pydantic Settings configuration
├── tests/
│   ├── conftest.py             # Pytest fixtures and mock setup
│   └── unit/
│       ├── test_ingestion.py   # Deduplication and fingerprinting unit tests
│       └── test_security.py    # HMAC signature verification tests
├── pyproject.toml
└── uv.lock
```

---

## Getting Started

### Prerequisites

- Python 3.12+
- [`uv`](https://github.com/astral-sh/uv) package manager
- (Optional) [Ollama](https://ollama.com/) running locally, or an API key for [OpenRouter](https://openrouter.ai/)

### Installation

1. Clone the repository and navigate to the `backend` directory:
   ```bash
   cd backend
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   uv sync
   ```

### Configuration

Copy the example environment file and configure your settings:

```bash
cp app/.env.example app/.env
```

Key environment variables:
- `DATABASE_URL`: SQLite connection string (defaults to `sqlite+aiosqlite:///./alerts.db`).
- `HOOKDECK_SIGNING_SECRET`: Secret key used to verify incoming webhook signatures.
- `HOOKDECK_API_KEY` & `HOOKDECK_API_URL`: Credentials used by the notification dispatcher to send outbound events.
- `INFERENCE_PROVIDER`: Set to `1` or `2` to pick between configured providers.
- `MULTIPASS_AGENT`: Set to `True` for multi-step diagnosis or `False` for single-pass analysis.
- `PROVIDER_NAME_1`: Name of the provider (`ollama` or `openrouter`).
- `PROVIDER_MODEL_1`: Model name (e.g., `llama3.2` for Ollama or `meta-llama/llama-3.2-3b-instruct` for OpenRouter).
- `PROVIDER_URL_1`: Ollama base URL (e.g., `http://localhost:11434/v1`).
- `PROVIDER_KEY_1`: API key (required when using OpenRouter).

### Running the Application

Start the local development server:

```bash
uv run uvicorn app.main:app --reload --port 8000
```

The service will start at `http://localhost:8000`. You can inspect the interactive OpenAPI documentation at `http://localhost:8000/docs`.

### Local Webhook Forwarding (Hookdeck CLI)

Because webhooks originate from external services, exposing your local instance on `localhost` requires a webhook tunnel. Use Hookdeck-CLI to forward events directly to your running FastAPI server:

[Hookdeck-CLI](https://hookdeck.com/docs/guides/how-to-test-webhooks-locally)

The CLI outputs a unique webhook signing secret for your session. Make sure to update `HOOKDECK_SIGNING_SECRET` in your `app/.env` file with this secret so that HMAC signature verification passes during local testing.


### Running Tests

Execute the unit test suite:

```bash
uv run pytest
```

---

## Future Ideas & Improvements

- **RAG:** Pull relevant internal runbooks, past incident post-mortems, and service docs into the prompt so the LLM suggests team-specific playbooks instead of generic advice.
- **Tool Calling & MCP:** Turn the agent from a passive summarizer into an active investigator using Model Context Protocol (MCP) or tool calling to query live Prometheus metrics, and check recent GitHub deployments before hypothesizing root causes.
- **Task queue:** Swap FastAPI's built-in `BackgroundTasks` for Redis + ARQ so long LLM jobs survive server restarts and failed jobs can retry automatically.
- **Integrations:** Add webhook parsers for more services (Convoy, Svix etc.)
