"""Optional OpenAI proposer used by the bounded refinement loop."""

from typing import Any


class OpenAIProposer:
    """Turn refinement prompts into strategy source without hiding API failures."""

    def __init__(self, client: Any, model: str = "gpt-4.1-mini", lenient_fences: bool = False) -> None:
        self.client = client
        self.model = model
        # Opt-in (docs/dart-oracle-design.md Section 18): also accept a fenced
        # code block followed by prose, which gpt-4.1 returns routinely. Off by
        # default so every earlier arm's parsing stays exactly reproducible.
        self.lenient_fences = lenient_fences

    def __call__(self, prompt: str) -> str:
        response = self.client.responses.create(
            model=self.model,
            input=prompt,
            temperature=0.2,
            max_output_tokens=2500,
        )
        text = getattr(response, "output_text", None)
        if not text:
            raise RuntimeError("LLM response did not contain output_text")
        if self.lenient_fences:
            return _extract_first_fenced_block(text)
        return _strip_code_fence(text)


def _strip_code_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        lines = cleaned.splitlines()
        return "\n".join(lines[1:-1]).strip()
    return cleaned


def _extract_first_fenced_block(text: str) -> str:
    """Like `_strip_code_fence`, but when the response opens with a fence and
    has prose after the closing one, return just the first fenced block."""
    cleaned = text.strip()
    if not cleaned.startswith("```"):
        return cleaned
    lines = cleaned.splitlines()
    for index in range(1, len(lines)):
        if lines[index].strip() == "```":
            return "\n".join(lines[1:index]).strip()
    return _strip_code_fence(text)
