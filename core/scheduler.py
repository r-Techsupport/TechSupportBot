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

    def __init__(self: Self, bot: bot.TechSupportBot) -> None:
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        self.tasks = {}  # task_name -> coroutine

    async def start(self: Self) -> None:
        """
        Start scheduler.
        We should only start the scheduler after tasks have been registered
        """
        self.scheduler.start()

    def register_task(self: Self, name: str, func: callable) -> None:
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
        """This schedules a task at a particular date in the future

        Args:
            task_name (str): The name of the task to register
            run_at (datetime.datetime): The time to run this task
            payload (dict): The data needed to run this task.
                May include channels, guilds, strings, members, etc

        Raises:
            AttributeError: Raised if the job being scheduled hasn't been registered

        Returns:
            str: The job ID number created for this job
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
        """This schedules a task in the future a given amount of seconds

        Args:
            task_name (str): The name of the task to register
            seconds (int): The amount of seconds to schedule the task into the future
            payload (dict): The data needed to run this task.
                May include channels, guilds, strings, members, etc

        Returns:
            str: The job ID number created for this job
        """

        run_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=seconds)

        return await self.schedule_date(task_name, run_at, payload)

    async def schedule_cron(
        self: Self,
        task_name: str,
        cron: str,
        payload: dict,
    ) -> str:
        """This schedules a task based on the next execution of a given cron

        Args:
            task_name (str): The name of the task to register
            cron (str): The crontab syntax for the job
            payload (dict): The data needed to run this task.
                May include channels, guilds, strings, members, etc

        Raises:
            ValueError: Raised if the passed crontab is invalid

        Returns:
            str: The job ID number created for this job
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
        """This schedules a task based on a randomly picked time

        Args:
            task_name (str): The name of the task to register
            min_hours (float): The minimum number of hours to wait
            max_hours (float): The maximum number of hours to wait
            payload (dict): The data needed to run this task.
                May include channels, guilds, strings, members, etc

        Returns:
            str: The job ID number created for this job
        """

        seconds = random.uniform(min_hours * 3600, max_hours * 3600)
        run_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=seconds)

        return await self.schedule_date(task_name, run_at, payload)

    # Getting tasks and other internal functions

    async def get_upcoming_tasks(self: Self) -> list[dict]:
        """This gets a list of all upcoming tasks in the scheduler, to allow for parsing
        This includes the ID, the payload, and the run_at time

        Returns:
            list[dict]: The list of upcoming tasks
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
