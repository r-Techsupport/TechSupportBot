"""Helper for generating a standard logger.
"""

import logging
import os


def get_logger(name):
    """Gathers a logger object based on project standards.

    parameters:
        name (str): the name for the logger.
    """
    try:
        debug = int(os.environ.get("DEBUG", 0))
    except Exception:
        debug = 0

    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=level)

    logger = logging.getLogger(name)

    return logger
