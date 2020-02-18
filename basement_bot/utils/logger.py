"""Helper for generating a standard logger.
"""

import logging

from utils.helpers import get_env_value


def get_logger(name):
    """Gathers a logger object based on project standards.

    parameters:
        name (str): the name for the logger.
    """
    try:
        debug = int(get_env_value("DEBUG", raise_exception=False))
    except ValueError:
        debug = 0

    level = logging.DEBUG if debug else logging.INFO
    formatting = "%(asctime)s [%(name)s, %(levelname)s]: %(message)s"
    logging.basicConfig(format=formatting, level=level)

    logger = logging.getLogger(name)

    return logger
