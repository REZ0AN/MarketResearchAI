"""
Token counting helpers.

Groq returns usage in the final stream chunk's `x_groq` metadata.
We also provide a lightweight character-based estimator as a fallback.
"""

from app.db.models import Chat, TokenUsage
from sqlalchemy.ext.asyncio import AsyncSession


def estimate_tokens(text: str) -> int:
    """
    Rough estimate: ~4 chars per token (GPT/LLaMA average).
    Used only when the model doesn't return exact counts.
    """
    return max(1, len(text) // 4)


async def save_token_usage(
    db:            AsyncSession,
    chat:          Chat,
    input_tokens:  int,
    output_tokens: int,
    model:         str,
) -> TokenUsage:
    total = input_tokens + output_tokens

    usage = TokenUsage(
        chat_id=chat.id,
        user_id=chat.user_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total,
        model=model,
    )
    db.add(usage)

    # Roll up into chat total
    chat.total_tokens_used += total

    await db.commit()
    await db.refresh(usage)
    return usage