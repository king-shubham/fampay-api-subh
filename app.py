from flask import Flask, request, jsonify
from telethon import TelegramClient, events
from telethon.tl.types import InputPeerUser, InputPeerChannel
from telethon.tl.functions.messages import SendMessageRequest
import asyncio
import re
import json
import os
from datetime import datetime
import threading
import time
from functools import wraps
import logging

from config import Config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Global variables to manage Telegram client
telegram_client = None
client_lock = asyncio.Lock()
is_authenticated = False

# Cache for responses
response_cache = {}
CACHE_TIMEOUT = 300  # 5 minutes

def async_to_sync(async_func):
    """Decorator to run async functions in sync context"""
    @wraps(async_func)
    def wrapper(*args, **kwargs):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(async_func(*args, **kwargs))
            loop.close()
            return result
        except Exception as e:
            logger.error(f"Async error: {e}")
            raise
    return wrapper

def rate_limit(max_per_minute=10):
    """Simple rate limiting decorator"""
    def decorator(func):
        requests = []
        @wraps(func)
        def wrapper(*args, **kwargs):
            now = time.time()
            requests[:] = [req for req in requests if now - req < 60]
            if len(requests) >= max_per_minute:
                return jsonify({'error': 'Rate limit exceeded'}), 429
            requests.append(now)
            return func(*args, **kwargs)
        return wrapper
    return decorator

class TelegramFAMBot:
    def __init__(self):
        self.client = None
        self.group_entity = None
        self.last_message_id = None
        self.response_received = asyncio.Event()
        self.bot_response = None
        
    async def initialize(self):
        """Initialize Telegram client"""
        global telegram_client, is_authenticated
        
        async with client_lock:
            if telegram_client and is_authenticated:
                self.client = telegram_client
                return True
                
            try:
                session_path = f"sessions/{Config.SESSION_NAME}"
                os.makedirs("sessions", exist_ok=True)
                
                self.client = TelegramClient(
                    session_path,
                    Config.API_ID,
                    Config.API_HASH
                )
                
                await self.client.connect()
                
                if not await self.client.is_user_authorized():
                    logger.info("User not authorized. Sending code request...")
                    await self.client.send_code_request(Config.PHONE_NUMBER)
                    
                    # In production, you'd need to handle 2FA properly
                    # For Render, you might need to pre-authorize the session
                    return False
                
                telegram_client = self.client
                is_authenticated = True
                logger.info("Telegram client initialized successfully")
                return True
                
            except Exception as e:
                logger.error(f"Initialization error: {e}")
                return False
    
    async def find_pinned_group(self):
        """Find the first pinned group/chat"""
        try:
            dialogs = await self.client.get_dialogs(limit=100)
            
            for dialog in dialogs:
                if dialog.is_group and dialog.pinned:
                    self.group_entity = dialog.entity
                    logger.info(f"Found pinned group: {dialog.name}")
                    return True
                elif dialog.is_channel and dialog.pinned:
                    self.group_entity = dialog.entity
                    logger.info(f"Found pinned channel: {dialog.name}")
                    return True
            
            # If no pinned group found, use the first group
            for dialog in dialogs:
                if dialog.is_group:
                    self.group_entity = dialog.entity
                    logger.info(f"Using group (not pinned): {dialog.name}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error finding group: {e}")
            return False
    
    async def send_fam_command(self, upi_id):
        """Send /fam command to the group"""
        try:
            if not self.group_entity:
                if not await self.find_pinned_group():
                    return False
            
            message = f"/fam {upi_id}"
            result = await self.client.send_message(self.group_entity, message)
            self.last_message_id = result.id
            logger.info(f"Sent message: {message}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending command: {e}")
            return False
    
    async def wait_for_bot_response(self, timeout=30):
        """Wait for bot response in the group"""
        try:
            self.response_received.clear()
            self.bot_response = None
            
            # Handler for new messages in the group
            @self.client.on(events.NewMessage(chats=self.group_entity))
            async def handler(event):
                if event.message.reply_to_msg_id == self.last_message_id:
                    if event.message.document or event.message.file:
                        # Bot sent a file
                        logger.info("Bot sent a file")
                        self.bot_response = event.message
                        self.response_received.set()
                    elif event.message.text:
                        # Bot sent a text message
                        logger.info(f"Bot response: {event.message.text}")
                        self.bot_response = event.message.text
                        self.response_received.set()
            
            # Wait for response
            try:
                await asyncio.wait_for(self.response_received.wait(), timeout=timeout)
                return True
            except asyncio.TimeoutError:
                logger.warning("Timeout waiting for bot response")
                return False
                
        except Exception as e:
            logger.error(f"Error waiting for response: {e}")
            return False
    
    async def download_and_parse_file(self):
        """Download and parse the bot's file response"""
        try:
            if not self.bot_response:
                return None
            
            if hasattr(self.bot_response, 'document'):
                # It's a document file
                file_path = await self.bot_response.download_media(file="downloads/")
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                os.remove(file_path)  # Clean up
                return self.parse_fam_response(content)
            else:
                # It's text
                return self.parse_fam_response(self.bot_response)
                
        except Exception as e:
            logger.error(f"Error processing file: {e}")
            return None
    
    def parse_fam_response(self, text):
        """Parse the FAM response into JSON"""
        result = {}
        
        try:
            # Common patterns in FAM response
            patterns = {
                'fam_id': r'FAM ID\s*:?\s*(.+)',
                'name': r'NAME\s*:?\s*(.+)',
                'phone': r'PHONE\s*:?\s*(.+)',
                'type': r'TYPE\s*:?\s*(.+)',
                'upi': r'UPI\s*:?\s*(.+)',
                'bank': r'BANK\s*:?\s*(.+)',
                'account': r'ACCOUNT\s*:?\s*(.+)',
                'ifsc': r'IFSC\s*:?\s*(.+)',
                'status': r'STATUS\s*:?\s*(.+)',
                'timestamp': r'TIMESTAMP\s*:?\s*(.+)'
            }
            
            for key, pattern in patterns.items():
                match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
                if match:
                    result[key] = match.group(1).strip()
            
            # If no structured data found, return raw text
            if not result:
                result['raw_response'] = text.strip()
            
            # Add timestamp
            result['query_timestamp'] = datetime.now().isoformat()
            
            return result
            
        except Exception as e:
            logger.error(f"Error parsing response: {e}")
            return {'error': 'Failed to parse response', 'raw_text': text[:500]}
    
    async def process_fam_request(self, upi_id):
        """Main method to process FAM request"""
        try:
            # Initialize client
            if not await self.initialize():
                return {'error': 'Failed to initialize Telegram client'}
            
            # Find group
            if not await self.find_pinned_group():
                return {'error': 'No group found'}
            
            # Send command
            if not await self.send_fam_command(upi_id):
                return {'error': 'Failed to send command'}
            
            # Wait for response
            if not await self.wait_for_bot_response(timeout=25):
                return {'error': 'No response from bot within timeout'}
            
            # Parse response
            result = await self.download_and_parse_file()
            
            if result:
                return {
                    'success': True,
                    'upi_id': upi_id,
                    'data': result,
                    'timestamp': datetime.now().isoformat()
                }
            else:
                return {'error': 'Failed to parse bot response'}
                
        except Exception as e:
            logger.error(f"Process error: {e}")
            return {'error': str(e)}

# Create global instance
fam_bot = TelegramFAMBot()

@app.route('/api', methods=['GET'])
@rate_limit(max_per_minute=15)
def get_fam_info():
    """Main API endpoint"""
    upi_id = request.args.get('fam', '').strip()
    
    if not upi_id:
        return jsonify({
            'error': 'Missing fam parameter',
            'usage': 'GET /api?fam=upi@fam',
            'example': 'GET /api?fam=priyanshis@fam'
        }), 400
    
    # Check cache
    cache_key = upi_id.lower()
    if cache_key in response_cache:
        cache_entry = response_cache[cache_key]
        if time.time() - cache_entry['timestamp'] < CACHE_TIMEOUT:
            return jsonify(cache_entry['data'])
    
    try:
        # Process the request
        result = async_to_sync(fam_bot.process_fam_request)(upi_id)
        
        # Cache successful responses
        if result.get('success'):
            response_cache[cache_key] = {
                'data': result,
                'timestamp': time.time()
            }
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"API error: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Render"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'Telegram FAM API'
    })

@app.route('/', methods=['GET'])
def home():
    """Homepage with instructions"""
    return jsonify({
        'service': 'Telegram FAM Information API',
        'endpoint': '/api?fam=upi@fam',
        'example': 'https://your-domain.onrender.com/api?fam=priyanshis@fam',
        'description': 'Query FAM information via Telegram bot',
        'health_check': '/health',
        'note': 'First request may be slow as it initializes Telegram session'
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
