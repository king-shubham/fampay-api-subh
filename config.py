import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Telegram API credentials (from https://my.telegram.org)
    API_ID = int(os.getenv('API_ID', 12345678))
    API_HASH = os.getenv('API_HASH', 'your_api_hash_here')
    
    # Your Telegram account credentials
    PHONE_NUMBER = os.getenv('PHONE_NUMBER', '+1234567890')
    
    # Session settings
    SESSION_NAME = 'fam_bot_session'
    
    # Rate limiting
    REQUEST_TIMEOUT = 30
    MAX_RETRIES = 3
