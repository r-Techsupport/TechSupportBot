import datetime
import random
import uuid
from typing import List, Self

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger


class SchedulerService:
    def __init__(self: Self, bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        self.tasks = {}  # task_name -> coroutine

    async def start(self: Self) -> None:
        """
        Start scheduler.
        """
        self.scheduler.start()

    def register_task(self, name: str, func):
        """
        Register execution handler for a task.
        """
        self.tasks[name] = func

    async def _execute(
        self: Self,
        task_name: str,
        guild_id: int,
        payload: dict,
    ) -> None:
        """
        Execute a scheduled task.
        Does checks to ensure the task is capable of being executed
        """

        handler = self.tasks.get(task_name)
        if not handler:
            return

        guild = self.bot.get_guild(guild_id)
        if not guild:
            return

        await handler(
            guild,
            payload or {},
        )

    # Schedulers to be called by cogs

    async def schedule_date(
        self: Self,
        task_name: str,
        guild: discord.Guild,
        run_at: datetime.datetime,
        payload: dict | None = None,
    ) -> str:
        """
        Schedule a task at an exact datetime.
        """

        job_id = f"{task_name}:{uuid.uuid4()}"

        self.scheduler.add_job(
            self._execute,
            trigger=DateTrigger(run_date=run_at),
            args=[task_name, guild.id, payload or {}],
            id=job_id,
            replace_existing=True,
        )

        return job_id

    async def schedule_delay(
        self: Self,
        task_name: str,
        guild: discord.Guild,
        seconds: int,
        payload: dict | None = None,
    ) -> str:
        """
        Schedule a task N seconds in the future.
        """

        run_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=seconds)

        return await self.schedule_date(task_name, guild, run_at, payload)

    async def schedule_cron(
        self: Self,
        task_name: str,
        guild: discord.Guild,
        cron: str,
        payload: dict | None = None,
    ) -> str:
        """
        Schedule a task using cron syntax.
        Converts cron → next execution datetime immediately.
        """

        trigger = CronTrigger.from_crontab(cron)

        now = datetime.datetime.utcnow()
        run_at = trigger.get_next_fire_time(None, now)

        if run_at is None:
            raise ValueError("Invalid cron expression")

        return await self.schedule_date(task_name, guild, run_at, payload)

    async def schedule_random(
        self: Self,
        task_name: str,
        guild: discord.Guild,
        min_hours: float,
        max_hours: float,
        payload: dict | None = None,
    ) -> str:
        """
        Schedule a task at a random time between min/max hours.
        """

        seconds = random.uniform(min_hours * 3600, max_hours * 3600)
        run_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=seconds)

        return await self.schedule_date(task_name, guild, run_at, payload)

    # Getting tasks and other internal functions

    async def get_upcoming_tasks(self: Self) -> List[dict]:
        """
        Return all scheduled tasks sorted by next execution time.
        """

        return sorted(
            [
                {
                    "job_id": job.id,
                    "task_name": (job.args[0] if job.args else "unknown"),
                    "run_at": job.next_run_time,
                }
                for job in self.scheduler.get_jobs()
            ],
            key=lambda x: x["run_at"],
        )
