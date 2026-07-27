import logging
from logging.handlers import TimedRotatingFileHandler
import os

LOG_DIR = "./logs"
os.makedirs(LOG_DIR, exist_ok=True)

def get_logger(name="nl2sql_mcp"):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    handler = TimedRotatingFileHandler(
        filename=os.path.join(LOG_DIR, "service.log"),
        when="D",
        interval=1,
        backupCount=30,
        encoding="utf-8"
    )

    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    handler.setFormatter(fmt)

    console = logging.StreamHandler()
    console.setFormatter(fmt)

    logger.addHandler(handler)
    logger.addHandler(console)
    return logger

logger = get_logger()
