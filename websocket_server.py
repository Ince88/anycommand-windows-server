import asyncio
import websockets
import logging
import pyautogui
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class KeyboardWebSocketServer:
    def __init__(self, host='0.0.0.0', port=8001):
        self.host = host
        self.port = port
        pyautogui.FAILSAFE = False

    async def handle_message(self, websocket):
        logger.info("New client connected")
        try:
            async for message in websocket:
                try:
                    logger.info(f"Received raw message: {message}")
                    data = json.loads(message)
                    msg_type = data.get('type')
                    
                    if msg_type == 'text':
                        text = data.get('text', '')
                        logger.info(f"Typing text: {text}")
                        pyautogui.write(text)
                        logger.info(f"Text typed: {text}")
                            
                    elif msg_type == 'key':
                        key = data.get('key')
                        logger.info(f"Pressing key: {key}")
                        pyautogui.press(key)
                        logger.info(f"Key pressed: {key}")
                        
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info("Client disconnected")

    async def start(self):
        server = await websockets.serve(self.handle_message, self.host, self.port)
        logger.info(f"WebSocket keyboard server running on ws://{self.host}:{self.port}")
        await server.wait_closed()

if __name__ == "__main__":
    server = KeyboardWebSocketServer()
    asyncio.run(server.start()) 