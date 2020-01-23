import logging

from utils import get_env_value


def get_logger(name):
    debug = get_env_value("DEBUG", raise_exception=False)
    level = logging.DEBUG if debug else logging.INFO
    formatting = "%(asctime)s [%(name)s, %(levelname)s]: %(message)s"
    logging.basicConfig(format=formatting, level=level)

    logger = logging.getLogger(name)

    return logger
