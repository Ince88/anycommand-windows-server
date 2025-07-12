import json
from shortcuts_handler import handle_shortcut

async def handle_websocket_message(websocket, message):
    try:
        data = json.loads(message)
        if data['type'] == 'shortcut':
            handle_shortcut(
                data['shortcut_id'], 
                data['app_id'],
                data.get('keys')  # Get keys if provided
            )
            await websocket.send(json.dumps({'status': 'success'}))
        # Handle other message types...
        
    except Exception as e:
        await websocket.send(json.dumps({
            'status': 'error',
            'message': str(e)
        })) 