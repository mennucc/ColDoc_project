import sys
import logging
from logging import Logger, StreamHandler, Formatter

logger = logging.getLogger()
#Logger('ColDoc')
handler = StreamHandler(sys.stderr)
LOG_FORMAT = '[%(name)s - %(funcName)s - %(levelname)s] %(message)s'
handler.setFormatter(Formatter(LOG_FORMAT))
logger.addHandler(handler)
