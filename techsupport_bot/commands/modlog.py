class BanLogger:
    async def high_score_command(self, interaction):
        ...

    async def on_ban(self, guild, ban):
        ...


async def log_ban(banned_member, banning_moderator, guild):
    ...


async def log_unban(unbanned_member, unbanning_moderator, guild):
    ...
