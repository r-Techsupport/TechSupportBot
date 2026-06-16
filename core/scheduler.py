"""
Biggest issues I still want to look at:
Generalizing the setup for the scheduler.
Removing guild from the execution, putting it in the payload
Creating a way to reset specifc tasks, especially after a config change
"""

from __future__ import annotations

import datetime
import random
import uuid
from typing import TYPE_CHECKING, Self

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

if TYPE_CHECKING:
    import bot


class SchedulerService:
    """This is the scheduler service
    This schedules a given task and runs it at later date

    Args:
        bot (bot.TechSupportBot): The running bot object
    """

    def __init__(self: Self, bot: bot.TechSupportBot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        self.tasks = {}  # task_name -> coroutine

    async def start(self: Self) -> None:
        """
        Start scheduler.
        We should only start the scheduler after tasks have been registered
        """
        self.scheduler.start()

    def register_task(self: Self, name: str, func: callable):
        """This registers a callback location for a scheduled tasks
        Modules wishing to schedule tasks should call this to setup tasks first

        Args:
            name (str): The globally unique name of a task
            func (callable): The function to call when the task executes
        """
        self.tasks[name] = func

    # Schedulers to be called by cogs

    async def schedule_date(
        self: Self,
        task_name: str,
        run_at: datetime.datetime,
        payload: dict,
    ) -> str:
        """
        Schedule a task at an exact datetime.
        Ideally to be used for voting
        """

        job_id = f"{task_name}:{uuid.uuid4()}"

        handler = self.tasks.get(task_name)
        if not handler:
            raise AttributeError(f"Missing task for {task_name}")

        self.scheduler.add_job(
            func=handler,
            trigger=DateTrigger(run_date=run_at),
            args=[payload],
            id=job_id,
            replace_existing=True,
        )

        return job_id

    async def schedule_delay(
        self: Self,
        task_name: str,
        seconds: int,
        payload: dict,
    ) -> str:
        """
        Schedule a task N seconds in the future.
        Ideally to be used for modmail, forum
        """

        run_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=seconds)

        return await self.schedule_date(task_name, run_at, payload)

    async def schedule_cron(
        self: Self,
        task_name: str,
        cron: str,
        payload: dict,
    ) -> str:
        """
        Schedule a task using cron syntax.
        Converts cron → next execution datetime immediately.
        Ideally to be used for news, application, factoid jobs
        """

        trigger = CronTrigger.from_crontab(cron)

        now = datetime.datetime.utcnow()
        run_at = trigger.get_next_fire_time(None, now)

        if run_at is None:
            raise ValueError("Invalid cron expression")

        return await self.schedule_date(task_name, run_at, payload)

    async def schedule_random(
        self: Self,
        task_name: str,
        min_hours: float,
        max_hours: float,
        payload: dict,
    ) -> str:
        """
        Schedule a task at a random time between min/max hours.
        Ideally to be used for duck, kanye
        """

        seconds = random.uniform(min_hours * 3600, max_hours * 3600)
        run_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=seconds)

        return await self.schedule_date(task_name, run_at, payload)

    # Getting tasks and other internal functions

    async def get_upcoming_tasks(self: Self) -> list[dict]:
        """
        Return all scheduled tasks sorted by next execution time.
        """

        return sorted(
            [
                {
                    "job_id": job.id,
                    "payload": job.args[0],
                    "run_at": job.next_run_time,
                }
                for job in self.scheduler.get_jobs()
            ],
            key=lambda x: x["run_at"],
        )
