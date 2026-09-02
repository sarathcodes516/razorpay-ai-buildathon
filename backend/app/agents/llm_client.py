"""
LLM client for TrustRail — OpenRouter backend.

Provides two interfaces:
  - call_llm_json()    : single-shot JSON response, no tool calling.
  - run_agent_turn()   : full agentic tool-calling loop for Face 2 (B2B gateway).

Uses OpenRouter's OpenAI-compatible API so any model on the router works by
changing MODEL below.

Rate-limit strategy
-------------------
On a 429 we back off with exponential delays (2 s, 4 s, 8 s, 16 s, 32 s) with
20% jitter, then raise so the caller gets a real error instead of silent garbage.
"""
import os
import json
import time
import random
from openai import OpenAI, RateLimitError, APIStatusError
from dotenv import load_dotenv

load_dotenv()

MODEL = "minimax/minimax-m3:free"

# Exponential back-off schedule (seconds) for 429s.
_BACKOFF_SCHEDULE = [2, 4, 8, 16, 32]

# Module-level singleton.
_CLIENT: OpenAI | None = None


def _client() -> OpenAI:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY", ""),
        )
    return _CLIENT


def _is_rate_limit(exc: Exception) -> bool:
    if isinstance(exc, RateLimitError):
        return True
    if isinstance(exc, APIStatusError) and exc.status_code == 429:
        return True
    msg = str(exc).lower()
    return "429" in msg or "rate limit" in msg or "too many requests" in msg


def _chat_with_retry(messages: list, tools: list | None = None, **kwargs):
    """
    Call chat.completions.create with exponential back-off on 429s.
    Raises the last exception if all retries are exhausted.
    """
    client = _client()
    last_exc: Exception | None = None
    call_kwargs = {"model": MODEL, "messages": messages, **kwargs}
    if tools:
        call_kwargs["tools"] = tools
        call_kwargs["tool_choice"] = "auto"

    for attempt, wait in enumerate([0] + _BACKOFF_SCHEDULE):
        if wait > 0:
            jitter = random.uniform(0, wait * 0.2)
            total = wait + jitter
            print(f"Rate limit — retrying in {total:.1f}s (attempt {attempt})…")
            time.sleep(total)
        try:
            return client.chat.completions.create(timeout=25, **call_kwargs)
        except Exception as exc:
            if _is_rate_limit(exc):
                last_exc = exc
                continue
            raise  # non-rate-limit: propagate immediately

    raise last_exc  # type: ignore[misc]


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
    return text.strip()


# ---------------------------------------------------------------------------
# JSON interface — no tool calling
# ---------------------------------------------------------------------------

def call_llm_json(system_prompt: str, user_input: str) -> dict:
    """
    Single-shot call that returns a parsed JSON dict.
    Retries once on a JSON parse error.
    Raises on API errors.
    """
    messages = [
        {"role": "system", "content": system_prompt
            + "\n\nIMPORTANT: Your response MUST be a single raw JSON object only. "
              "No markdown, no code fences, no extra text."},
        {"role": "user", "content": user_input},
    ]

    for attempt in range(2):
        if attempt == 1:
            messages.append({
                "role": "user",
                "content": "Your previous response was not valid JSON. "
                           "Return ONLY a raw JSON object, no markdown, no code fences."
            })
        response = _chat_with_retry(messages, max_tokens=1024)
        raw = _strip_fences(response.choices[0].message.content or "")
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"JSON parse error (attempt {attempt + 1}): {e}\nRaw: {raw[:300]}")

    return {"_raw": raw, "error": "json_parse_failed"}


# ---------------------------------------------------------------------------
# Tool-calling agentic loop
# ---------------------------------------------------------------------------

def run_agent_turn(
    system_prompt: str,
    user_input: str,
    tools: list,
    tool_impls: dict[str, callable],
    max_tool_rounds: int = 6,
) -> tuple[str, list[dict]]:
    """
    Run a multi-turn agentic loop with OpenAI-style tool calling.

    Each round:
      - If the model returns tool_calls, execute them and feed results back.
      - If the model returns a text message, return it immediately.

    If the loop exhausts max_tool_rounds, makes one final call with tools
    disabled and a JSON instruction to force a structured reply.

    Returns:
        (final_text, trace)
        final_text — model's last text output.
        trace      — list of {tool, args, result} dicts for the audit log.
    """
    trace: list[dict] = []

    # Build OpenAI tool schema from Python callables via their docstrings + type hints.
    # We pass the raw Python functions — the OpenAI SDK does NOT auto-generate schemas,
    # so we build minimal schemas ourselves from the function signatures.
    openai_tools = _build_tool_schemas(tools)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_input},
    ]

    for _round in range(max_tool_rounds):
        response = _chat_with_retry(messages, tools=openai_tools, max_tokens=1024)
        msg = response.choices[0].message

        if not msg.tool_calls:
            # Model responded with text — done.
            return msg.content or "", trace

        # Append the assistant's tool-call message to history.
        messages.append({"role": "assistant", "content": msg.content, "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in msg.tool_calls
        ]})

        # Execute each tool call and append results.
        for tc in msg.tool_calls:
            fn = tool_impls.get(tc.function.name)
            try:
                args = json.loads(tc.function.arguments)
                result = fn(**args) if fn else {"error": f"unknown_tool: {tc.function.name}"}
            except Exception as exc:
                result = {"error": str(exc)}

            trace.append({"tool": tc.function.name, "args": args, "result": result})

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result),
            })

    # Exhausted rounds — ask for a plain JSON response with no tools.
    messages.append({
        "role": "user",
        "content": "You have used your tools. Now provide your final response as a raw JSON object only."
    })
    response = _chat_with_retry(messages, max_tokens=1024)
    return response.choices[0].message.content or "", trace


# ---------------------------------------------------------------------------
# Schema builder — converts Python callables to OpenAI tool schemas
# ---------------------------------------------------------------------------

def _build_tool_schemas(fns: list) -> list[dict]:
    """
    Build minimal OpenAI function tool schemas from Python callables.
    Uses type annotations to infer parameter types.
    """
    import inspect

    type_map = {
        str: "string", int: "integer", float: "number",
        bool: "boolean", list: "array", dict: "object",
    }

    schemas = []
    for fn in fns:
        sig = inspect.signature(fn)
        doc = (fn.__doc__ or "").strip().split("\n")[0]  # first line of docstring
        properties = {}
        required = []

        for name, param in sig.parameters.items():
            ann = param.annotation
            json_type = type_map.get(ann, "string")
            properties[name] = {"type": json_type}
            if param.default is inspect.Parameter.empty:
                required.append(name)

        schemas.append({
            "type": "function",
            "function": {
                "name": fn.__name__,
                "description": doc,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        })

    return schemas


# ---------------------------------------------------------------------------
# Back-compat alias — old code that calls call_gemini_json still works
# ---------------------------------------------------------------------------
call_gemini_json = call_llm_json
