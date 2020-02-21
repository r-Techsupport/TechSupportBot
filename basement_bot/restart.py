"""Dev-only tool for hot-reloading on file-changes.

Eventually, this will be moved to its own Python module.
"""

from functools import partial

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


class RestartManager:
    """Watchdog event thread with interfacing to the bot.

    parameters:
        watch_dir (str): the directory to watch
        recursive (bool): True if recursive directories should be
    """

    def __init__(self, watch_dir, recursive=True):
        self.watch_dir = watch_dir
        self.recursive = recursive
        self.bot = None

        self.observer = Observer()
        self.event_handler = FileSystemEventHandler()
        self.event_handler.on_any_event = lambda _: None

    def set_bot(self, bot):
        """Registers a bot object into the on_any_event function.

        parameters:
            bot (BasementBot): the bot object to register
        """
        self.event_handler.on_any_event = partial(self.on_any_event, bot)

    def start(self):
        """Starts the observer thread.
        """
        self.observer.schedule(self.event_handler, self.watch_dir, self.recursive)
        self.observer.start()

    def stop(self):
        """Stops the observer thread.
        """
        self.observer.stop()
        self.observer.join()

    @staticmethod
    def on_any_event(bot, _):
        """Asks the bot to shutdown on any Watchdog event.

        parameters:
            bot (BasementBot): the bot object to register
        """
        if bot.stable:
            bot.loop.create_task(bot.shutdown())
