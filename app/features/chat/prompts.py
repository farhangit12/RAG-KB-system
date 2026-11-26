"""Prompt text. Kept short: every token here is paid for in the free-plan token budget."""

from __future__ import annotations

from app.features.chat.models import Source
from app.features.retrieval.service import BusinessProfile

SYSTEM = """You are Disha's startup advisor. Speak warmly and directly, in simple English \
(reply in Hinglish if the founder writes in Hinglish).

Rules:
1. Use ONLY the numbered sources and the business profile below. Do not use outside knowledge.
2. Cite every point with its source label, like [S1] or [S2][S3].
3. Never invent numbers, quotes, client names or outcomes. Copy numbers exactly from the sources.
4. If the sources do not answer the question, say so plainly and suggest booking a Direction \
Call with Disha. Do not guess.
5. Make the advice specific to the business profile when the sources allow it.
6. Keep it short: a direct answer first, then up to 5 bullet points."""

NOT_FOUND = (
    "I couldn't find this in Disha's knowledge base, so I won't guess. "
    "A Direction Call with Disha's founders is the best next step for this question."
)


def profile_block(profile: BusinessProfile | None) -> str:
    """The business profile as short labelled lines (only fields that are set)."""
    if profile is None:
        return "Business profile: not provided."
    fields = [
        ("Sector", profile.sector),
        ("Stage", profile.founder_stage),
        ("Location", profile.location),
        ("Business model", profile.business_model),
        ("Target audience", profile.target_audience),
        ("Summary", profile.summary),
    ]
    lines = [f"- {k}: {v}" for k, v in fields if v]
    return "Business profile:\n" + ("\n".join(lines) if lines else "- (no details yet)")


def build_prompt(question: str, sources: list[Source], profile: BusinessProfile | None) -> str:
    """Sources, profile and question in one user message."""
    blocks = [f"[{s.label}] {s.citation}\n{s.text}" for s in sources]
    return (
        "Sources:\n\n" + "\n\n".join(blocks) + "\n\n" + profile_block(profile)
        + f"\n\nFounder's question: {question}"
    )
