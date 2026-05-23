from typing import Optional

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

SYSTEM_PROMPT_MODE2 = (
    "You are a text editor. The user dictated the following text.\n"
    "Clean it up: fix grammar, remove filler words, improve flow.\n"
    "Keep the original language. Keep the meaning and tone.\n"
    "Return only the cleaned text, no explanations."
)

SYSTEM_PROMPT_MODE3 = (
    "You are a text editor and translator. The user dictated the following text.\n"
    "First clean it up: fix grammar, remove filler words, improve flow.\n"
    "Then translate the cleaned text into natural English.\n"
    "Return only the final English text, no explanations."
)


class ProcessorError(Exception):
    pass


class TextProcessor:
    MODEL = "claude-sonnet-4-6"
    MAX_TOKENS = 2048

    def __init__(self, api_key: str):
        self._api_key = api_key
        self._client: Optional["anthropic.Anthropic"] = None

    def _get_client(self) -> "anthropic.Anthropic":
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def process(self, text: str, mode: int) -> str:
        if not ANTHROPIC_AVAILABLE:
            raise ProcessorError(
                "anthropic package is not installed. Run: pip install anthropic"
            )
        if mode == 2:
            system_prompt = SYSTEM_PROMPT_MODE2
        elif mode == 3:
            system_prompt = SYSTEM_PROMPT_MODE3
        else:
            raise ProcessorError(f"Invalid mode: {mode}. Use 2 or 3.")

        return self._call_api(system_prompt, text)

    def _call_api(self, system: str, user_text: str) -> str:
        try:
            client = self._get_client()
            response = client.messages.create(
                model=self.MODEL,
                max_tokens=self.MAX_TOKENS,
                system=system,
                messages=[{"role": "user", "content": user_text}],
            )
            return response.content[0].text.strip()
        except Exception as e:
            if ANTHROPIC_AVAILABLE:
                if isinstance(e, anthropic.AuthenticationError):
                    raise ProcessorError(
                        "Invalid API key. Please check your Claude API key in Settings."
                    ) from e
                if isinstance(e, anthropic.APIError):
                    raise ProcessorError(str(e)) from e
            raise ProcessorError(f"Unexpected error: {e}") from e


_processor: Optional[TextProcessor] = None
_processor_api_key: str = ""


def get_processor(api_key: str) -> TextProcessor:
    global _processor, _processor_api_key
    if _processor is None or api_key != _processor_api_key:
        _processor = TextProcessor(api_key=api_key)
        _processor_api_key = api_key
    return _processor
