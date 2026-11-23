# TraceOps AI Workspace Rules
- Python 3.11+, strict type hints, Pydantic v2, FastAPI, LangGraph, google-genai SDK.
- Never put an LLM API call on the synchronous hot path.
- Every code edit must pass `pytest -v` before marking a task complete.
- Never hardcode API keys; read GEMINI_API_KEY and DATABASE_URL from .env.
