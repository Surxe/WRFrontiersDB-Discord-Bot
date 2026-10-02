"""Entry point: `python -m wrfdb_bot`."""

import sys

from dotenv import load_dotenv
from loguru import logger

from .bot import WrfBot
from .options import load_options


def main() -> None:
    load_dotenv()
    options = load_options()
    logger.remove()
    logger.add(sys.stderr, level=options.log_level)
    WrfBot(options).run(options.discord_bot_token)


if __name__ == '__main__':
    main()
