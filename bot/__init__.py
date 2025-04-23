"""Miss Pauling module"""

import os
import asyncio
import logging
from pauling.db import init as db

logger = logging.getLogger("pauling")
logger.setLevel(logging.INFO)

log_format = logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s")

file_handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")
file_handler.setFormatter(log_format)

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_format)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

# if not os.path.exists('pauling.db'):
#     print('DB does not exist, creating now...')
#     logger.debug('DB does not exist, creating now...')
#     loop = asyncio.new_event_loop()
#     asyncio.set_event_loop(loop)
#     loop.run_until_complete(db.init())
#     print('db created')
