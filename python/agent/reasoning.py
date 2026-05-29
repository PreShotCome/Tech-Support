"""Theo-soul: a model-agnostic reasoning loop.

One-shot answers waste a model's headroom. This wraps any `LlmClient` in a
deliberate loop — plan -> draft -> self-critique against IDENTITY -> revise
— with a working scratchpad that records every stage. The point is leverage:
a disciplined loop lets a smaller local model (Qwen 32B on the box) reason
well above its weight, narrowing the gap to Claude-Theo. It runs unchanged
on whatever backend `LlmClient` points at.

Self-contained and opt-in: it does NOT replace the default agent loop. Wire
it in deliberately once it's proven. It depends only on the LLM abstraction
(`agent.llm.base`) and the stdlib. Run the self-test (no real model needed):

    python -m agent.reasoning
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional

from .llm.base import ChatMessage, LlmClient


# A stage tag is prepended to each stage's system prompt. Real models treat
# it as harmless context; it makes the trace self-documenting and lets a
# stub LLM route deterministically in tests.
STAGE_TAG = "STAGE="

# Compact rubric distilled from IDENTITY.md's idioms, so the critic holds
# Theo's standards even when no full identity text is passed in.
_DEFAULT_RUBRIC = """\
- Lead with the actual answer; no throat-clearing ("Great question", "Sure!").
- Make the call when asked to recommend; no "your call" / "either is fine".
- Truth over flattery; don't soften a real problem into a non-problem.
- Speak as yourself, first person; no "as an AI" qualifiers.
- Match the input's energy and register; don't pad a short ask with structure.
- Be concrete before abstract: name the file, number, or example first."""


@dataclass
class Critique:
    verdict: str            # "pass" | "revise"
    issues: list[str] = field(default_factory=list)


@dataclass
class ReasoningTrace:
    question: str
    plan: str
    drafts: list[str]
    critiques: list[Critique]
    final: str
    revisions: int

    def to_markdown(self) -> str:
        out = [f"### Reasoning trace\n", f"**Question:** {self.question}\n",
               f"**Plan:**\n{self.plan}\n"]
        for i, d in enumerate(self.drafts):
            label = "Draft" if i == 0 else f"Revision {i}"
            out.append(f"**{label}:**\n{d}\n")
            if i < len(self.critiques):
                c = self.critiques[i]
                issues = "; ".join(c.issues) if c.issues else "—"
                out.append(f"**Critique {i + 1}:** {c.verdict} ({issues})\n")
        out.append(f"**Final ({self.revisions} revision(s)):**\n{self.final}")
        return "\n".join(out)


class ReasoningLoop:
    def __init__(
        self,
        llm: LlmClient,
        identity: str = "",
        max_revisions: int = 2,
        temperature: float = 0.2,
    ) -> None:
        self.llm = llm
        self.identity = identity.strip()
        self.max_revisions = max(0, int(max_revisions))
        self.temperature = temperature

    # ------------------------------------------------------------ primitives

    def _ask(self, stage: str, system: str, user: str) -> str:
        msgs = [
            ChatMessage(role="system", content=f"{STAGE_TAG}{stage}\n{system}"),
            ChatMessage(role="user", content=user),
        ]
        reply = self.llm.chat(msgs, temperature=self.temperature)
        return (reply.content or "").strip()

    def _rubric(self) -> str:
        if self.identity:
            return f"{_DEFAULT_RUBRIC}\n\nIDENTITY:\n{self.identity}"
        return _DEFAULT_RUBRIC

    # ---------------------------------------------------------------- stages

    def plan(self, question: str) -> str:
        return self._ask(
            "PLAN",
            "Plan how to answer the user's request. Output a brief numbered "
            "list of the steps or checks needed. No prose answer yet.",
            question,
        )

    def draft(self, question: str, plan: str) -> str:
        return self._ask(
            "DRAFT",
            "Write the best answer you can, following this plan:\n" + plan,
            question,
        )

    def critique(self, question: str, draft: str) -> Critique:
        raw = self._ask(
            "CRITIC",
            "You are a strict critic. Judge the draft answer against the "
            "question and the standards below. Reply with ONLY a JSON object: "
            '{"verdict": "pass" | "revise", "issues": [short strings]}. '
            "Use 'revise' only for real problems.\n\nStandards:\n" + self._rubric(),
            f"QUESTION:\n{question}\n\nDRAFT:\n{draft}",
        )
        return self._parse_critique(raw)

    def revise(self, question: str, draft: str, critique: Critique, plan: str) -> str:
        issues = "\n".join(f"- {i}" for i in critique.issues) or "- tighten it"
        return self._ask(
            "REVISE",
            "Revise the draft to fix these issues, keeping what worked. "
            "Output only the improved answer.\n\nIssues:\n" + issues,
            f"QUESTION:\n{question}\n\nPLAN:\n{plan}\n\nDRAFT:\n{draft}",
        )

    # -------------------------------------------------------------- parsing

    @staticmethod
    def _parse_critique(raw: str) -> Critique:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(0))
                verdict = str(data.get("verdict", "")).lower()
                issues = [str(x) for x in data.get("issues", []) if str(x).strip()]
                if verdict in ("pass", "revise"):
                    return Critique(verdict=verdict, issues=issues)
            except (json.JSONDecodeError, AttributeError, TypeError):
                pass
        # Tolerant fallback: a verdict word anywhere, else pass (don't loop
        # forever on a non-conforming model).
        low = raw.lower()
        if "revise" in low and "pass" not in low:
            return Critique(verdict="revise", issues=["critic output unparsed"])
        return Critique(verdict="pass", issues=[])

    # ------------------------------------------------------------------ run

    def think(self, question: str) -> ReasoningTrace:
        plan = self.plan(question)
        current = self.draft(question, plan)
        drafts = [current]
        critiques: list[Critique] = []
        revisions = 0

        for attempt in range(self.max_revisions + 1):
            crit = self.critique(question, current)
            critiques.append(crit)
            if crit.verdict == "pass" or not crit.issues:
                break
            if attempt == self.max_revisions:
                break  # out of revision budget; keep the best so far
            current = self.revise(question, current, crit, plan)
            drafts.append(current)
            revisions += 1

        return ReasoningTrace(
            question=question, plan=plan, drafts=drafts,
            critiques=critiques, final=current, revisions=revisions,
        )

    def answer(self, question: str) -> str:
        """Convenience: run the loop, return just the final answer."""
        return self.think(question).final


# ----------------------------------------------------------------- self-test

def _stage_of(messages: list[ChatMessage]) -> str:
    if messages and messages[0].role == "system":
        m = re.match(rf"{STAGE_TAG}(\w+)", messages[0].content)
        if m:
            return m.group(1)
    return "?"


def _selftest() -> int:
    """Deterministic checks driven by a scripted stub LLM — no real model,
    no network. Returns 0 on pass, 1 on failure."""

    failures: list[str] = []

    def check(name: str, cond: bool) -> None:
        print(f"[{'ok' if cond else 'FAIL'}] {name}")
        if not cond:
            failures.append(name)

    class ScriptedLlm(LlmClient):
        """Routes by stage tag. `verdicts` is the sequence of critic
        verdicts to emit on successive CRITIC calls."""
        def __init__(self, verdicts: list[str]) -> None:
            self.verdicts = list(verdicts)
            self.calls: list[str] = []

        def chat(self, messages, tools=None, temperature=0.2) -> ChatMessage:
            stage = _stage_of(messages)
            self.calls.append(stage)
            if stage == "PLAN":
                return ChatMessage("assistant", "1. understand\n2. answer")
            if stage == "DRAFT":
                return ChatMessage("assistant", "DRAFT_ANSWER")
            if stage == "REVISE":
                return ChatMessage("assistant", "REVISED_ANSWER")
            if stage == "CRITIC":
                v = self.verdicts.pop(0) if self.verdicts else "pass"
                if v == "revise":
                    return ChatMessage("assistant", '{"verdict":"revise","issues":["too long"]}')
                return ChatMessage("assistant", '{"verdict":"pass","issues":[]}')
            return ChatMessage("assistant", "?")

    # 1. Critic passes immediately -> no revision, final == draft.
    llm = ScriptedLlm(verdicts=["pass"])
    loop = ReasoningLoop(llm, max_revisions=2)
    tr = loop.think("q")
    check("pass-first: final is the draft", tr.final == "DRAFT_ANSWER")
    check("pass-first: zero revisions", tr.revisions == 0)
    check("pass-first: stage order", llm.calls == ["PLAN", "DRAFT", "CRITIC"])

    # 2. Revise once, then pass -> one revision, final == revised.
    llm = ScriptedLlm(verdicts=["revise", "pass"])
    tr = ReasoningLoop(llm, max_revisions=2).think("q")
    check("revise-once: final is revised", tr.final == "REVISED_ANSWER")
    check("revise-once: one revision", tr.revisions == 1)
    check("revise-once: two critiques", len(tr.critiques) == 2)
    check("revise-once: stage order",
          llm.calls == ["PLAN", "DRAFT", "CRITIC", "REVISE", "CRITIC"])

    # 3. Critic always revises but budget caps it.
    llm = ScriptedLlm(verdicts=["revise", "revise", "revise"])
    tr = ReasoningLoop(llm, max_revisions=1).think("q")
    check("budget-cap: revisions capped at 1", tr.revisions == 1)
    check("budget-cap: stops at budget",
          llm.calls == ["PLAN", "DRAFT", "CRITIC", "REVISE", "CRITIC"])

    # 4. max_revisions=0 still critiques once (self-critique is core).
    llm = ScriptedLlm(verdicts=["revise"])
    tr = ReasoningLoop(llm, max_revisions=0).think("q")
    check("no-budget: still one critique", len(tr.critiques) == 1)
    check("no-budget: no revision", tr.revisions == 0)

    # 5. Tolerant critique parsing.
    p = ReasoningLoop._parse_critique
    check("parse: clean revise", p('{"verdict":"revise","issues":["x"]}').verdict == "revise")
    check("parse: prose-wrapped json",
          p('Here:\n{"verdict":"pass","issues":[]}\ndone').verdict == "pass")
    check("parse: garbage -> pass (no infinite loop)", p("???").verdict == "pass")

    # 6. Trace renders and identity flows into the rubric.
    check("trace markdown has plan", "Plan:" in tr.to_markdown())
    loop_id = ReasoningLoop(ScriptedLlm(["pass"]), identity="BE TERSE")
    check("identity in rubric", "BE TERSE" in loop_id._rubric())

    print()
    if failures:
        print(f"FAILED: {len(failures)} check(s): {', '.join(failures)}")
        return 1
    print("All reasoning-loop self-tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
