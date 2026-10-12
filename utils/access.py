"""Access helpers for private records."""

from __future__ import annotations

import discord


def can_manage_records(interaction: discord.Interaction) -> bool:
    """Only allowlisted user IDs may use /records and records config."""
    cfg = getattr(interaction.client, "config", None)
    if cfg is None:
        return False
    allowed: frozenset[int] = getattr(cfg, "records_admin_ids", frozenset())
    if not allowed:
        return False
    return interaction.user.id in allowed
