import discord


async def isGuildClosed(bot: object, guild: discord.Guild) -> bool:
    db_enty = await bot.models.HolidayClose.query.where(
        bot.models.HolidayClose.guild_id == str(guild.id)
    ).gino.first()
    if db_enty:
        return True
    return False
