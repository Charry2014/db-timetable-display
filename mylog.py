from loguru import logger
from sys import stdout

logger.remove(0)
logger.add(stdout, colorize=True, format="{time} | {level} | {message}", level="DEBUG")

