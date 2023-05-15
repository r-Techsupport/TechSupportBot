import base
import discord
import expiringdict
import util
from discord.ext import commands


async def setup(bot):
    await bot.add_cog(ChatGPT(bot=bot))


class ChatGPT(base.BaseCog):
    API_URL = "https://api.openai.com/v1/chat/completions"

    async def preconfig(self):
        self.history = expiringdict.ExpiringDict(
            max_len=1000,
            max_age_seconds=3600,
        )

    def get_system_prompt(self):
        return [
            {
                "role": "system",
                "content": "The following questions are being asked via a Discord bot. Please try to keep messages informative but concise. For example, in code responses please try to not have a lot of newlines if unnecessary. The max message size should always be under 2000 characters or it will get clipped.",
            }
        ]

    async def call_api(self, ctx, api_key, prompt):
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "model": "gpt-3.5-turbo",
            "messages": self.get_system_prompt()
            + self.history.get(ctx.author.id, [])
            + [{"role": "user", "content": prompt}],
        }
        response = await self.bot.http_call(
            "post", self.API_URL, headers=headers, json=data
        )
        return response

    # @util.with_typing
    @commands.cooldown(3, 60, commands.BucketType.channel)
    @commands.command(
        brief="Prompts ChatGPT",
        description="Issues a prompt to the ChatGPT API",
        usage="[prompt]",
    )
    async def gpt(self, ctx, *, prompt: str):
        api_key = self.bot.file_config.main.api_keys.openai
        if not api_key:
            await ctx.send_deny_embed("I couldn't find the OpenAI API key")
            return

        response = await self.call_api(ctx, api_key, prompt)
        choices = response.get("choices", [])
        if not choices:
            await ctx.send_deny_embed("I couldn't figure out what to say!")
            return

        content = choices[0].get("message", {}).get("content")
        if not content:
            await ctx.send_deny_embed("I couldn't figure out what to say!")

        if not self.history.get(ctx.author.id):
            self.history[ctx.author.id] = [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": content},
            ]
        else:
            self.history[ctx.author.id].append({"role": "user", "content": prompt})
            self.history[ctx.author.id].append(
                {"role": "assistant", "content": content}
            )

        await ctx.send(content=content[:2000])

    @commands.group(
        brief="Executes a ChatGPT util command",
        description="Executes a ChatGPT util command",
    )
    async def gptutil(self, ctx):
        pass

    @util.with_typing
    @gptutil.command(
        name="clear",
        brief="Clears history",
        description="Clears your ChatGPT conversation history",
    )
    async def clear_history(self, ctx):
        history = self.history.pop(ctx.author.id, None)
        if history is None:
            await ctx.send_deny_embed("No history found")
            return

        confirm = await ctx.confirm(f"Clear {len(history)} messages?")
        if not confirm:
            return

        await ctx.send_confirm_embed("Chat history cleared!")

    @util.with_typing
    @gptutil.command(
        name="history",
        brief="Gets history",
        description="Gets your ChatGPT conversation history",
    )
    async def get_history(self, ctx):
        history = self.history.get(ctx.author.id)
        if history is None:
            await ctx.send_deny_embed("No history found")
            return

        embeds = []
        for i in range(0, len(history), 2):
            prompt = history[i].get("content", "Unknown").strip()
            resp = history[i + 1].get("content", "Unknown").strip()
            embed = discord.Embed(title="ChatGPT History")
            embed.add_field(name="Prompt", value=prompt[:255])
            embed.add_field(name="Response", value=resp[:255])
            embeds.append(embed)

        ctx.task_paginate(pages=embeds)
