import logging

import azure.functions as func

from shared_code.process_alerts import process_alerts


async def main(mytimer: func.TimerRequest) -> None:
    logging.info("Night alerts timer trigger function started")
    await process_alerts()
