"""Make one real, minimal NVIDIA NIM request to verify backend configuration."""
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from openai import OpenAI, APIStatusError, APIConnectionError, APITimeoutError
from app.core.config import NVIDIA_API_KEY, NVIDIA_BASE_URL, NVIDIA_MODEL


def main() -> int:
    if not NVIDIA_API_KEY or NVIDIA_API_KEY.strip() in ("", "your_nvidia_api_key_here"):
        print("BLOCKED: NVIDIA_API_KEY is missing. Set it in backend/.env.")
        return 2
    client = OpenAI(api_key=NVIDIA_API_KEY, base_url=NVIDIA_BASE_URL, timeout=30.0, max_retries=0)
    try:
        response = client.chat.completions.create(
            model=NVIDIA_MODEL,
            messages=[{"role": "user", "content": "Return JSON with status set to ok."}],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=64,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
        content = response.choices[0].message.content if response.choices else None
        if not content:
            print("FAIL: NVIDIA returned an empty response.")
            return 1
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            print("FAIL: NVIDIA returned a response that was not valid JSON.")
            return 1
        if not isinstance(parsed, dict) or parsed.get("status") != "ok":
            print("FAIL: NVIDIA returned JSON with an unexpected shape.")
            return 1
        print(f"PASS: NVIDIA returned valid JSON from model {response.model or NVIDIA_MODEL}.")
        return 0
    except (APIStatusError, APIConnectionError, APITimeoutError):
        print("FAIL: NVIDIA request failed. Check credentials, service availability, and network access.")
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
