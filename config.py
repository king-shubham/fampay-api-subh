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
    SESSION_NAME = 'BQAAB_gAUiHWlCQHDCqygz2y4c7gurQ_AqFel4ittK061vuD2LAjBhcCIDC3HcNWGn1uJpuxaPVRwuqEVgbdCQ5GABPiS9451Gd7XfkvCwTjau4y75Ff7XG96kD9qK8bFH-mz0Bxmov-4fpYUS287MmDSaMLiPU3zZHXjL0cLDeax3CastbijaMcEF5CBKlf26kkYe1QIhhVJNeDEDHx0FFe3t3m_Of85x_7MOLqVtQ1ibwdre52FtwK7pNiB9UC4FL64crs_gKp8GC7FFQv1oh5D2pr2T7iiWYkiqqv-lMEXg4ybi6fTN-oNA6tC0ClJdYyRgP_hlODKN6Y_8oA7S3EPE_mwAAAAAH8sNKlAA'
    
    # Rate limiting
    REQUEST_TIMEOUT = 30
    MAX_RETRIES = 3
