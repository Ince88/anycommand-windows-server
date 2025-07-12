import sys
import logging
import keyboard
import pyautogui
import win32api
import win32con
from remote_server import RemoteServer

logging.basicConfig(level=logging.INFO)

if __name__ == '__main__':
    try:
        server = RemoteServer()
        print('Press Ctrl+C to exit')
        server.start()
    except KeyboardInterrupt:
        print('\nServer shutting down...')
    except Exception as e:
        print(f'Error: {e}')
        input('Press Enter to exit...')
