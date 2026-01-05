import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Telegram API credentials (from https://my.telegram.org)
    API_ID = int(os.getenv('API_ID', 35415101))
    API_HASH = os.getenv('API_HASH', 'ab68651b9cb3c6757baf547cabef27d6')
    
    # Your Telegram account credentials
    PHONE_NUMBER = os.getenv('PHONE_NUMBER', '+918859679570')
    
    # Session settings
    SESSION_NAME = 'fam_bot_session'
    
    # Rate limiting
    REQUEST_TIMEOUT = 30
    MAX_RETRIES = 3
