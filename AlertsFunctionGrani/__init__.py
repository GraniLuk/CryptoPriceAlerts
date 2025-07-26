import logging

import azure.functions as func

from shared_code.process_alerts import process_alerts
from shared_code.process_indicator_alerts import process_indicator_alerts


async def main(mytimer: func.TimerRequest) -> None:
    logging.info("Day alerts timer trigger function started")
    
    # Process price alerts
    await process_alerts()
    
    # Process indicator alerts
    await process_indicator_alerts()
