"""In-memory LLM adapter for tests: scripted outcomes, recorded calls."""

from __future__ import annotations

from src.llm import AITask, LLMResult


class FakeLLMAdapter:
    name = "fake"
    display_name = "Fake"
    default_models = {task: "fake-model" for task in AITask}

    def __init__(self, outcomes=()):
        """Each outcome is an LLMResult, a str (response text) or an Exception to raise."""
        self._outcomes = list(outcomes)
        self.calls: list[dict] = []

    @classmethod
    def owns_model(cls, model: str) -> bool:
        return True

    @staticmethod
    def supports_json_schema(model: str) -> bool:
        return False

    async def complete(self, *, system, messages, model, max_tokens, cache_system=False, timeout=None,
                       json_schema=None, json_output=False):
        self.calls.append(
            {"system": system, "messages": messages, "model": model, "max_tokens": max_tokens,
             "cache_system": cache_system, "timeout": timeout, "json_schema": json_schema,
             "json_output": json_output}
        )
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        if isinstance(outcome, str):
            return LLMResult(text=outcome)
        return outcome

    async def aclose(self) -> None:
        pass
