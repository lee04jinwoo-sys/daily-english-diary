"""Fake Gemini client for the review pipeline: answers each call by the role marker in its prompt."""
import json

from tests.test_essays import FAKE_REVIEW

MAIN = {k: v for k, v in FAKE_REVIEW.items() if k not in ("suggestions", "corrected_text")}


def role_of(prompt: str) -> str:
    if "[오류 탐지]" in prompt:
        return "detect"
    if "[교정 검증]" in prompt:
        return "verify"
    if "[다시 쓴 글]" in prompt:
        return "pairs"
    if "[밴드 채점]" in prompt:
        return "score"
    return "main"


def accept_all(n: int, patterns=None) -> dict:
    """Verifier answer accepting candidates c1..cn."""
    return {"verdicts": [{"id": f"c{i}", "valid": True} for i in range(1, n + 1)], "patterns": patterns or []}


class Router:
    """main/detect/verify/pairs/score -> response. A list value is consumed one item per call."""

    def __init__(self, main=MAIN, detect=None, verify=None, pairs=None, score=None):
        self.responses = {"main": main, "detect": detect or {"suggestions": []}, "verify": verify or {},
                          "pairs": pairs or {"pairs": []}, "score": score or {"rubric": FAKE_REVIEW["rubric"]}}
        self.prompts = {}
        self.calls = []
        router = self

        class Models:
            async def generate_content(self, *a, **k):
                role = role_of(k["contents"])
                router.prompts[role] = k["contents"]
                router.calls.append((role, k))
                resp = router.responses[role]
                if isinstance(resp, list):
                    resp = resp.pop(0)

                class Usage:
                    prompt_token_count = 100
                    candidates_token_count = 50
                    thoughts_token_count = 10

                class R:
                    text = json.dumps(resp)
                    usage_metadata = Usage()
                return R()

        class Aio:
            models = Models()
        self.aio = Aio()

    def count(self, role: str) -> int:
        return sum(1 for r, _ in self.calls if r == role)
