import json
import socket
from typing import Optional
from urllib import error, request as urllib_request

SYSTEM_PROMPT = """You are a helpful assistant inside a Stock Portfolio Management web app.

Rules:
- Focus on the user's portfolio, analytics, transactions, and the app's features.
- Do NOT provide financial advice or guaranteed predictions.
- Provide educational explanations only.
- Use the provided CONTEXT as ground truth.
- If the user asks something outside scope, explain what the app can do instead.
- Keep responses clear, short, and user-friendly.
"""

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "gemma3"


def ask_gemini(
    user_message: str,
    context_text: str = "",
    model: str = OLLAMA_MODEL,
    timeout: int = 120,
) -> str:
    """
    Drop-in replacement for the previous Gemini-based function.
    Function name is kept the same to avoid changing existing imports.
    """

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": f"CONTEXT:\n{context_text}\n\nUSER:\n{user_message}",
        },
    ]

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.5,
        },
    }

    try:
        body = json.dumps(payload).encode("utf-8")
        http_request = urllib_request.Request(
            OLLAMA_URL,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib_request.urlopen(http_request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")

        data = json.loads(raw)
        message = data.get("message", {}) if isinstance(data, dict) else {}
        reply: Optional[str] = message.get("content") if isinstance(message, dict) else None

        if reply and reply.strip():
            return reply.strip()

        return "Sorry, I couldn't generate a response."

    except error.HTTPError as e:
        return f"Local AI HTTP error: {e.code} {e.reason}"
    except error.URLError as e:
        reason = getattr(e, "reason", None)
        if isinstance(reason, (TimeoutError, socket.timeout)):
            return "The local AI model took too long to respond. Please try a shorter question."
        return (
            "Local AI assistant is unavailable. Please make sure Ollama is installed, "
            "running, and the selected model is downloaded."
        )
    except (TimeoutError, socket.timeout):
        return "The local AI model took too long to respond. Please try a shorter question."
    except Exception as e:
        return f"Local AI error: {e}"
