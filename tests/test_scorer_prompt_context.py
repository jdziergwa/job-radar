import sys
import types


if "anthropic" not in sys.modules:
    anthropic = types.ModuleType("anthropic")

    class AsyncAnthropic:  # pragma: no cover - stub for import only
        pass

    anthropic.AsyncAnthropic = AsyncAnthropic
    anthropic.Anthropic = AsyncAnthropic
    anthropic.RateLimitError = Exception
    anthropic.APIError = Exception
    sys.modules["anthropic"] = anthropic

from src.scorer import _build_system_prompt


def test_build_system_prompt_includes_scoring_context_block():
    prompt = _build_system_prompt(
        "Scoring instructions",
        "Profile doc",
        {
            "keywords": {"title_patterns": {"high_confidence": [r"\bbackend\s+engineer\b"]}},
            "scoring_context": {
                "role_targets": {"core": ["Senior Backend Engineer"]},
                "work_setup": {"preferred_setup": "remote"},
            },
        },
    )

    text = prompt[0]["text"]

    assert "CANDIDATE PREFERENCES (from search_config.yaml):" in text
    assert "scoring_context:" in text
    assert "role_targets:" in text
    assert "preferred_setup: remote" in text
