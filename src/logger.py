import sys
import logging
import os

class InfoFilter(logging.Filter):
    def filter(self, record):
        return record.levelno == logging.INFO

logger = logging.getLogger(__name__)

logger.setLevel(logging.DEBUG)
stdoutHandler = logging.StreamHandler(stream=sys.stdout)
fileHandler = logging.FileHandler(f"{os.path.dirname(__file__)}/../logs.txt")

fmt = logging.Formatter(
    "%(levelname)s | %(filename)s | line %(lineno)s | %(asctime)s | >>> %(message)s"
)

stdoutHandler.setFormatter(fmt)
fileHandler.setFormatter(fmt)

# Set the level of the stdoutHandler to INFO and add the InfoFilter
stdoutHandler.setLevel(logging.DEBUG)  # Set to DEBUG so it can apply the filter for INFO
stdoutHandler.addFilter(InfoFilter())

# Set the level of the fileHandler to DEBUG
fileHandler.setLevel(logging.DEBUG)

logger.addHandler(stdoutHandler)
logger.addHandler(fileHandler)
