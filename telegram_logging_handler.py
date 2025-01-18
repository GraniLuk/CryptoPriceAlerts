import logging
import requests
import os

class TelegramHandler(logging.Handler):
    def __init__(self, token, chat_id):
        super().__init__()
        self.token = token
        self.chat_id = chat_id

    def emit(self, record):
        log_entry = self.format(record)
        self.send_telegram_message(log_entry)

    def send_telegram_message(self, message):
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            'chat_id': self.chat_id,
            'text': message,
            'parse_mode': 'Markdown'
        }
        requests.post(url, json=payload)

def setup_logger():
    logger = logging.getLogger('AppLogger')
    logger.setLevel(logging.INFO)  # Set the logger's level to the lowest level you want to capture

    # Formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Console Handler (INFO level)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Telegram Handler (ERROR level)
    telegram_token = os.environ.get("TELEGRAM_TOKEN")
    telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if telegram_token and telegram_chat_id:
        telegram_handler = TelegramHandler(telegram_token, telegram_chat_id)
        telegram_handler.setLevel(logging.ERROR)
        telegram_handler.setFormatter(formatter)
        logger.addHandler(telegram_handler)
    else:
        print("Telegram logging not configured due to missing environment variables")

    return logger

# Create the logger instance
app_logger = setup_logger()