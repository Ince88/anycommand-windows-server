import socket
import pyautogui
import keyboard
from threading import Thread
import sys
import logging
import os
import math
import time
import win32api
import win32con
import ctypes
from ctypes import wintypes
import win32gui
import sys
import subprocess
import hashlib
import json
import secrets
import configparser
from threading import Timer
import customtkinter as ctk
import win32event
import win32security
import winerror
from screen_share_service import ScreenShareService
from file_transfer_service import FileTransferService
from window_thumbnails_service import WindowThumbnailsService
import threading
from clipboard_service import ClipboardService
import asyncio
import websockets

REQUIRED_PACKAGES = ["keyboard", "pyautogui", "pywin32", "customtkinter", "pyperclip", "websockets"]

# Use the same mutex name
MUTEX_NAME = "Global\\AnyCommandServer_SingleInstance"

# Gamepad button mapping for keyboard/mouse emulation
GAMEPAD_BUTTON_MAP = {
    # Face buttons
    'a': 'enter',
    'b': 'escape', 
    'x': 'space',
    'y': 'tab',
    
    # D-pad
    'dpad_up': 'up',
    'dpad_down': 'down', 
    'dpad_left': 'left',
    'dpad_right': 'right',
    
    # Shoulder buttons
    'l1': 'q',
    'l2': 'shift',
    'r1': 'e',
    'r2': 'ctrl',
    
    # Center buttons
    'start': 'enter',
    'select': 'escape',
    'home': 'windows',
}

# Function to install missing packages
def install_packages():
    for package in REQUIRED_PACKAGES:
        try:
            __import__(package)
        except ImportError:
            print(f"Installing missing package: {package}")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# Ensure all required packages are installed before proceeding
install_packages()

def send_input_mouse_wheel(delta):
    # Mouse wheel input structure
    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))
        ]

    class INPUT(ctypes.Structure):
        _fields_ = [
            ("type", wintypes.DWORD),
            ("mi", MOUSEINPUT)
        ]

    MOUSEEVENTF_WHEEL = 0x0800

    extra = ctypes.pointer(wintypes.ULONG(0))
    input_struct = INPUT(
        type=0,  # INPUT_MOUSE
        mi=MOUSEINPUT(0, 0, delta, MOUSEEVENTF_WHEEL, 0, extra)
    )

    ctypes.windll.user32.SendInput(1, ctypes.byref(input_struct), ctypes.sizeof(INPUT))

def find_scroll_window():
    """Find the window under the cursor"""
    cursor_pos = win32gui.GetCursorPos()
    return win32gui.WindowFromPoint(cursor_pos)

def send_scroll_message(direction):
    """Send WM_MOUSEWHEEL message directly to the window"""
    WM_MOUSEWHEEL = 0x020A
    window = find_scroll_window()
    wheel_delta = 120 if direction == 'up' else -120  # Standard wheel delta
    cursor_pos = win32gui.GetCursorPos()

    # Create message parameters
    wparam = wheel_delta << 16  # Shift delta to high word
    lparam = cursor_pos[1] << 16 | cursor_pos[0]  # Pack coordinates

    win32gui.SendMessage(window, WM_MOUSEWHEEL, wparam, lparam)

class GamepadState:
    """Track gamepad state for advanced features"""
    def __init__(self):
        self.left_stick = {'x': 0.0, 'y': 0.0}
        self.right_stick = {'x': 0.0, 'y': 0.0}
        self.pressed_buttons = set()
        self.motion_tilt = {'x': 0.0, 'y': 0.0}
        self.gyro_rotation = {'x': 0.0, 'y': 0.0}
        self.gamepad_mode = False
        
        # Mouse simulation state
        self.mouse_sensitivity = 800  # pixels per second at max stick
        self.last_mouse_update = time.time()

class RemoteServer:
    def __init__(self, host='0.0.0.0', port=8000, pin_mode=True, custom_pin=''):
        # Suppress all console output
        logging.getLogger().handlers = []

        # Add null handler to suppress console output
        null_handler = logging.NullHandler()
        logging.getLogger().addHandler(null_handler)

        # Add file handler for logging to file
        file_handler = logging.FileHandler('remote_server.log')
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            '%Y-%m-%d %H:%M:%S'
        ))
        logging.getLogger().addHandler(file_handler)
        logging.getLogger().setLevel(logging.ERROR)

        self.host = host
        self.port = port
        self.server = None
        self.config = self._load_or_create_config(pin_mode, custom_pin)
        self.authenticated_clients = set()
        self.disconnect_timer = None
        self.warning_timer = None
        self.disconnect_minutes = 120  # Default 2 hours
        self.clients = set()  # Track connected clients

        # Initialize gamepad state
        self.gamepad_state = GamepadState()

        # Initialize screen sharing service
        self.screen_share_service = ScreenShareService()
        self.screen_sharing_active = False

        # Initialize file transfer service
        self.file_transfer_service = FileTransferService()

        # Initialize window thumbnails service
        self.window_thumbnails_service = WindowThumbnailsService()

        # Initialize clipboard service
        self.clipboard_service = ClipboardService(port=8084)

        # Initialize WebSocket server for keyboard/text input
        self.websocket_server = None
        self.websocket_thread = None

        try:
            # Create socket with explicit error handling
            self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            self.server.bind((self.host, self.port))
            self.server.listen(5)

            # Initialize pyautogui settings
            pyautogui.FAILSAFE = False  # Disable failsafe
            pyautogui.MINIMUM_DURATION = 0
            pyautogui.MINIMUM_SLEEP = 0
            pyautogui.PAUSE = 0

            # Try to set mouse speed, but don't fail if we can't
            try:
                import win32api
                import win32con
                win32api.SystemParametersInfo(win32con.SPI_SETMOUSESPEED, 0, 20)
            except:
                logging.warning("Could not set mouse speed - continuing anyway")

        except Exception as e:
            logging.error(f"Failed to initialize server: {e}")
            if self.server:
                self.server.close()
            sys.exit(1)

        # Start services
        self.screen_share_service.start()
        self.file_transfer_service.start()
        self.window_thumbnails_service.start()
        self.clipboard_service.start()

    def _load_or_create_config(self, pin_mode, custom_pin):
        config = configparser.ConfigParser()
        config_path = os.path.join(os.path.expanduser('~'), '.anycommand', 'config.ini')

        if not os.path.exists(os.path.dirname(config_path)):
            os.makedirs(os.path.dirname(config_path))

        # Check if config exists and load it
        if os.path.exists(config_path):
            config.read(config_path)

        # Generate or use PIN based on startup configuration
        if pin_mode or not custom_pin or len(custom_pin) != 6:
            # Use random PIN if random mode is enabled or custom PIN is invalid
            pin = self._generate_pin()
        else:
            # Use custom PIN
            pin = custom_pin

        salt = secrets.token_hex(16)

        # Update security section
        if 'Security' not in config:
            config['Security'] = {}
        config['Security']['current_pin'] = pin
        config['Security']['pin_hash'] = self._hash_pin(pin, salt)
        config['Security']['salt'] = salt

        # Update PIN configuration section
        if 'PinConfig' not in config:
            config['PinConfig'] = {}
        config['PinConfig']['use_random_pin'] = str(pin_mode).lower()
        config['PinConfig']['custom_pin'] = custom_pin if not pin_mode else ''

        # Write updated config
        with open(config_path, 'w') as f:
            config.write(f)

        return config

    def _generate_pin(self, length=6):
        return ''.join(secrets.choice('0123456789') for _ in range(length))

    def _hash_pin(self, pin, salt=None):
        if salt is None:
            salt = secrets.token_hex(16)
        return hashlib.pbkdf2_hmac(
            'sha256',
            pin.encode(),
            salt.encode(),
            100000
        ).hex()

    def start(self):
        logging.info("Server starting...")
        try:
            # Start WebSocket server for keyboard/text input
            self.start_websocket_server()

            # Start screen sharing
            self.toggle_screen_sharing(True)

            # Start file transfer service
            self.file_transfer_service.start()

            # Start window thumbnails service
            self.window_thumbnails_service.start()

            # Start clipboard service
            self.clipboard_service.start()

            while True:
                logging.info("Waiting for connection...")
                client, address = self.server.accept()
                logging.info(f"Connected to {address}")
                client_thread = Thread(target=self.handle_client, args=(client, address))
                client_thread.daemon = True
                client_thread.start()
        except KeyboardInterrupt:
            logging.info("Server shutting down...")
        except Exception as e:
            logging.error(f"Server error: {e}")  # Only log to file
        finally:
            self.server.close()

    def handle_key_combination(self, key_combo):
        """Handle complex key combinations with proper timing"""
        try:
            keys = key_combo.split('+')
            # Press all keys in sequence
            for k in keys:
                key = k.lower().strip()
                keyboard.press(key)
                time.sleep(0.05)  # Small delay between key presses

            # Small hold time for the combination
            time.sleep(0.1)

            # Release in reverse order
            for k in reversed(keys):
                key = k.lower().strip()
                keyboard.release(key)
                time.sleep(0.05)  # Small delay between key releases

        except Exception as e:
            logging.error(f"Error in key combination {key_combo}: {e}")
            print("Error processing keyboard input")

    def send_char(self, char):
        """Send a character using Windows API directly"""
        if char == '?':
            # VK_SHIFT = 0x10, VK_OEM_2 (/?key) = 0xBF
            win32api.keybd_event(0x10, 0, 0, 0)  # Press Shift
            win32api.keybd_event(0xBF, 0, 0, 0)  # Press /?
            win32api.keybd_event(0xBF, 0, win32con.KEYEVENTF_KEYUP, 0)  # Release /?
            win32api.keybd_event(0x10, 0, win32con.KEYEVENTF_KEYUP, 0)  # Release Shift
            return True
        return False

    def handle_mouse_move(self, dx, dy):
        """Handle mouse movement with maximum performance and reliability."""
        try:
            # Convert to integers and validate
            dx_int = int(dx)
            dy_int = int(dy)
            
            # Skip processing zero movements to reduce CPU overhead
            if dx_int == 0 and dy_int == 0:
                return
            
            # Use direct Win32 API for maximum performance and reliability
            try:
                current_pos = win32api.GetCursorPos()
                new_x = current_pos[0] + dx_int
                new_y = current_pos[1] + dy_int
                
                # Get screen dimensions to ensure cursor stays within bounds
                screen_width = win32api.GetSystemMetrics(0)
                screen_height = win32api.GetSystemMetrics(1)
                
                # Clamp coordinates to screen bounds
                new_x = max(0, min(new_x, screen_width - 1))
                new_y = max(0, min(new_y, screen_height - 1))
                
                # Set cursor position directly
                win32api.SetCursorPos((new_x, new_y))
                
            except Exception as win32_error:
                # Fallback to pyautogui if Win32 API fails
                logging.warning(f"Win32 mouse move failed, using pyautogui fallback: {win32_error}")
                current_x, current_y = pyautogui.position()
                pyautogui.moveTo(current_x + dx_int, current_y + dy_int, duration=0)
                
        except Exception as e:
            logging.error(f"Error moving mouse: {e}")

    def handle_mouse_click(self, button):
        """Handle mouse click with proper button mapping"""
        try:
            if button == 'left':
                pyautogui.click(button='left')
            elif button == 'right':
                pyautogui.click(button='right')
            elif button == 'middle':
                pyautogui.click(button='middle')
            else:
                logging.warning(f"Unknown mouse button: {button}")
        except Exception as e:
            logging.error(f"Error handling mouse click: {e}")

    def handle_client(self, client, address):
        if address in self.authenticated_clients:
            self.authenticated_clients.remove(address)
            # Cancel any existing timers for this client
            if self.disconnect_timer:
                self.disconnect_timer.cancel()
                self.disconnect_timer = None
            if self.warning_timer:
                self.warning_timer.cancel()
                self.warning_timer = None

        if address not in self.authenticated_clients:
            # Send authentication challenge
            client.send(b'AUTH_REQUIRED')

            try:
                data = client.recv(1024).decode()
                logging.info(f"Raw data received: {data}")
                received_pin = json.loads(data)['pin']

                if received_pin == self.config['Security']['current_pin']:
                    self.authenticated_clients.add(address)
                    client.send(b'AUTH_SUCCESS')
                    logging.info("Authentication successful")
                else:
                    logging.info("Authentication failed")
                    client.send(b'AUTH_FAILED')
                    client.close()
                    return
            except Exception as e:
                logging.error(f"Authentication error: {e}")
                client.close()
                return

        try:
            logging.info(f"Starting to handle client {address}")
            # Initialize timer state after successful authentication
            if self.disconnect_minutes > 0:
                # Send warning 30 seconds before disconnect
                self.warning_timer = Timer(
                    (self.disconnect_minutes * 60) - 30,
                    lambda: self._send_warning(client)
                )
                self.warning_timer.start()
                logging.info(f"Warning timer set for {self.disconnect_minutes} minutes - 30 seconds")

                self.disconnect_timer = Timer(
                    self.disconnect_minutes * 60,
                    lambda: self.auto_disconnect(client)
                )
                self.disconnect_timer.start()
                logging.info(f"Auto-disconnect timer started: {self.disconnect_minutes} minutes")
            else:
                logging.info("Auto-disconnect disabled")

            # Add client to set when connected
            self.clients.add(client)

            while True:
                data = client.recv(1024).decode('utf-8').strip()
                if not data:
                    logging.info(f"Client {address} sent empty data, breaking connection")
                    break

                logging.info(f"Received raw data: {data}")

                if ':' in data:
                    cmd_type, *params = data.split(':')
                else:
                    cmd_type = data

                if cmd_type == 'SET_DISCONNECT_TIMER':
                    try:
                        minutes = int(params[0])
                        self.disconnect_minutes = minutes
                        # Reset the timer with new duration
                        if self.disconnect_timer:
                            self.disconnect_timer.cancel()
                        self.disconnect_timer = Timer(minutes * 60, lambda: self.auto_disconnect(client))
                        self.disconnect_timer.start()  # Start the new timer
                        client.send(b'OK\n')
                        logging.info(f"Auto-disconnect timer set to {minutes} minutes")
                    except (ValueError, IndexError) as e:
                        logging.error(f"Invalid timer value: {e}")
                        client.send(b'ERROR\n')

                elif cmd_type == 'SHUTDOWN':
                    logging.info("Received shutdown command from client")
                    print("\n⚠️ Auto-disconnect timer expired. Server shutting down...")
                    # Force immediate shutdown
                    client.send(b'SHUTDOWN_INITIATED')
                    client.close()
                    os._exit(0)  # Force immediate termination
                    return

                elif cmd_type == 'MOUSE_MOVE':
                    try:
                        x = int(params[0])
                        y = int(params[1])
                        # Skip tiny movements to reduce overhead
                        if abs(x) > 0 or abs(y) > 0:
                            self.handle_mouse_move(x, y)
                        client.send(b'OK\n')
                    except:
                        client.send(b'OK\n')

                elif cmd_type == 'MOUSE_CLICK':
                    try:
                        button = params[0]
                        self.handle_mouse_click(button)
                        client.send(b'OK\n')
                    except Exception as e:
                        logging.error(f"Mouse click error: {e}")
                        client.send(b'OK\n')

                elif cmd_type == 'MOUSE_CLICK_POS':
                    try:
                        # Format: "MOUSE_CLICK_POS:50.5:30.2" (percentage coordinates)
                        percent_x = float(params[0])
                        percent_y = float(params[1])
                        
                        # Convert percentage to absolute coordinates
                        screen_width = win32api.GetSystemMetrics(0)
                        screen_height = win32api.GetSystemMetrics(1)
                        
                        abs_x = int((percent_x / 100.0) * screen_width)
                        abs_y = int((percent_y / 100.0) * screen_height)
                        
                        # Move mouse to position and click
                        win32api.SetCursorPos((abs_x, abs_y))
                        time.sleep(0.05)  # Small delay for stability
                        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                        time.sleep(0.05)
                        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                        
                        client.send(b'OK\n')
                    except Exception as e:
                        logging.error(f"Mouse click position error: {e}")
                    client.send(b'OK\n')

                elif cmd_type == 'KEY':
                    try:
                        key = params[0]
                        if '+' in key:
                            self.handle_key_combination(key)
                        else:
                            keyboard.press_and_release(key.lower())
                        
                        client.send(b'OK\n')

                    except Exception as e:
                        logging.error(f"Key press error: {e}")
                        print("Error processing keyboard input")
                        client.send(b'OK\n')

                elif cmd_type == 'TYPE':
                    try:
                        text = params[0]
                        logging.info(f"Attempting to type character: {repr(text)}")

                        if text == '?':
                            # Use pyautogui for question mark
                            pyautogui.keyDown('shift')
                            pyautogui.press('/')
                            pyautogui.keyUp('shift')
                        elif text == ' ':
                            # Handle space directly
                            keyboard.press_and_release('space')
                        else:
                            # Special character mapping for other characters
                            char_map = {
                                '!': ['shift', '1'],
                                '@': ['shift', '2'],
                                '#': ['shift', '3'],
                                '$': ['shift', '4'],
                                '%': ['shift', '5'],
                                '^': ['shift', '6'],
                                '&': ['shift', '7'],
                                '*': ['shift', '8'],
                                '(': ['shift', '9'],
                                ')': ['shift', '0'],
                                '_': ['shift', '-'],
                                '+': ['shift', '='],
                                '{': ['shift', '['],
                                '}': ['shift', ']'],
                                '|': ['shift', '\\'],
                                ':': ['shift', ';'],
                                '"': ['shift', "'"],
                                '<': ['shift', ','],
                                '>': ['shift', '.'],
                                '~': ['shift', '`'],
                            }

                            if text in char_map:
                                keys = char_map[text]
                                keyboard.press(keys[0])
                                keyboard.press(keys[1])
                                time.sleep(0.1)
                                keyboard.release(keys[1])
                                keyboard.release(keys[0])
                            else:
                                keyboard.write(text)

                        client.send(b'OK\n')

                    except Exception as e:
                        logging.error(f"Error typing text: {e}")
                        client.send(b'OK\n')

                elif cmd_type == 'SCROLL':
                    try:
                        direction = params[0]
                        intensity = int(params[1]) if len(params) > 1 else 1

                        # Reduced multiplier for smoother scrolling
                        wheel_delta = 60 * intensity  # Reduced from 120 to 60

                        # Send scroll message with intensity
                        window = find_scroll_window()
                        wparam = wheel_delta << 16 if direction == 'up' else (-wheel_delta) << 16
                        cursor_pos = win32gui.GetCursorPos()
                        lparam = cursor_pos[1] << 16 | cursor_pos[0]

                        win32gui.SendMessage(window, 0x020A, wparam, lparam)
                        client.send(b'OK\n')
                    except Exception as e:
                        logging.error(f"Scroll error: {e}")
                        client.send(b'OK\n')

                elif cmd_type == 'MOUSE_DOWN':
                    try:
                        button = params[0]
                        # Use win32api for more reliable mouse button control
                        if button == 'left':
                            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                        elif button == 'right':
                            win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
                        elif button == 'middle':
                            win32api.mouse_event(win32con.MOUSEEVENTF_MIDDLEDOWN, 0, 0, 0, 0)
                        client.send(b'OK\n')
                        logging.info(f"Mouse button {button} pressed down")
                    except Exception as e:
                        logging.error(f"Mouse down error: {e}")
                        client.send(b'OK\n')

                elif cmd_type == 'MOUSE_UP':
                    try:
                        button = params[0]
                        # Use win32api for more reliable mouse button control
                        if button == 'left':
                            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                        elif button == 'right':
                            win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
                        elif button == 'middle':
                            win32api.mouse_event(win32con.MOUSEEVENTF_MIDDLEUP, 0, 0, 0, 0)
                        client.send(b'OK\n')
                        logging.info(f"Mouse button {button} released")
                    except Exception as e:
                        logging.error(f"Mouse up error: {e}")
                        client.send(b'OK\n')

                elif cmd_type == 'DISABLE_DISCONNECT_TIMER':
                    # Client requested to disable the timer
                    if self.disconnect_timer:
                        self.disconnect_timer.cancel()
                    self.disconnect_timer = None
                    client.send(b'OK\n')  # Add missing acknowledgment

                elif cmd_type.startswith('SET_DISCONNECT_TIMER:'):
                    minutes = int(cmd_type.split(':')[1])
                    self.disconnect_minutes = minutes
                    # Reset existing timer if any
                    if hasattr(self, 'disconnect_timer'):
                        self.disconnect_timer.cancel()
                    # Set new timer
                    if minutes > 0:
                        self.disconnect_timer = Timer(minutes * 60, lambda: self.auto_disconnect(client))
                        self.disconnect_timer.start()
                    client.send(b'OK\n')

                # Add handling for screen sharing commands
                elif cmd_type == 'screen_share':
                    command = data.get('command')
                    if command == 'start':
                        self.toggle_screen_sharing(True)
                    elif command == 'stop':
                        self.toggle_screen_sharing(False)
                    client.send(b'OK\n')

                # Handle PIN configuration updates
                elif cmd_type.startswith('PIN_CONFIG'):
                    try:
                        # Handle JSON PIN config data
                        if '{' in data:
                            config_data = json.loads(data)
                            if config_data.get('command') == 'PIN_CONFIG':
                                pin_config = config_data.get('config', {})
                                self._update_pin_configuration(pin_config)
                                client.send(b'PIN_CONFIG_OK\n')
                    except Exception as e:
                        logging.error(f"Error processing PIN config: {e}")
                        client.send(b'PIN_CONFIG_ERROR\n')

                # Handle screen share view status messages
                elif cmd_type == "screen_view":
                    view_status = params[0] == "start"
                    self.screen_share_service.set_viewing_status(view_status)
                    client.send(b'OK\n')  # Send response instead of returning

                # Handle gamepad commands
                elif cmd_type == 'GAMEPAD_BUTTON':
                    try:
                        button = params[0]
                        action = params[1]
                        self.handle_gamepad_button(button, action)
                        client.send(b'OK\n')
                    except Exception as e:
                        logging.error(f"Gamepad button error: {e}")
                        client.send(b'OK\n')

                elif cmd_type == 'GAMEPAD_STICK':
                    try:
                        stick = params[0]
                        x = float(params[1])
                        y = float(params[2])
                        self.handle_gamepad_stick(stick, x, y)
                        client.send(b'OK\n')
                    except Exception as e:
                        logging.error(f"Gamepad stick error: {e}")
                        client.send(b'OK\n')

                elif cmd_type == 'GAMEPAD_MOTION':
                    try:
                        tilt_x = float(params[0])
                        tilt_y = float(params[1])
                        self.handle_gamepad_motion(tilt_x, tilt_y)
                        client.send(b'OK\n')
                    except Exception as e:
                        logging.error(f"Gamepad motion error: {e}")
                        client.send(b'OK\n')

                elif cmd_type == 'GAMEPAD_GYRO':
                    try:
                        rot_x = float(params[0])
                        rot_y = float(params[1])
                        logging.info(f"Received gyro data: x={rot_x:.3f}, y={rot_y:.3f}")
                        self.handle_gamepad_gyro(rot_x, rot_y)
                        client.send(b'OK\n')
                    except Exception as e:
                        logging.error(f"Gamepad gyro error: {e}")
                        client.send(b'OK\n')

                # Handle gamepad mode toggle
                elif cmd_type == 'gamepad_mode':
                    mode = params[0] if params else 'start'
                    self.gamepad_state.gamepad_mode = (mode == 'start')
                    logging.info(f"Gamepad mode {'enabled' if self.gamepad_state.gamepad_mode else 'disabled'}")
                    client.send(b'OK\n')

                # Handle PING for connection health monitoring
                elif cmd_type == 'PING':
                    client.send(b'PONG\n')

                # Handle HEARTBEAT for background stability
                elif cmd_type == 'HEARTBEAT':
                    client.send(b'HEARTBEAT_ACK\n')

        except Exception as e:
            logging.error(f"Error handling client {address}: {e}")
        finally:
            # Clean up when client disconnects
            if client in self.clients:
                self.clients.remove(client)
            try:
                client.close()
            except:
                pass

    def auto_disconnect(self, client):
        """Handle auto-disconnect with proper notification"""
        try:
            if client in self.clients:
                client.send(b'SERVER_SHUTDOWN')
                client.close()
                self.clients.remove(client)
        except:
            pass

    def get_current_pin(self):
        """Get the current PIN"""
        return self.config['Security']['current_pin']

    def _send_warning(self, client):
        """Send warning message 30 seconds before disconnect"""
        try:
            logging.info("Sending disconnect warning to client")
            client.send(b'DISCONNECT_WARNING:30')
        except Exception as e:
            logging.error(f"Error sending warning: {e}")

    def notify_clients_shutdown(self):
        """Notify all clients before shutting down"""
        for client in self.clients.copy():  # Use copy to avoid modification during iteration
            try:
                client.send(b'SERVER_SHUTDOWN')
                client.close()
            except:
                pass
        self.clients.clear()

    def quit(self):
        """Clean shutdown of server"""
        try:
            self.notify_clients_shutdown()
            if self.server:
                self.server.close()
        except:
            pass

    def toggle_screen_sharing(self, active=True):
        if active and not self.screen_sharing_active:
            self.screen_share_service.start()
            self.screen_sharing_active = True
        elif not active and self.screen_sharing_active:
            self.screen_share_service.stop()
            self.screen_sharing_active = False

    def stop(self):
        # Stop file transfer service
        self.file_transfer_service.stop()

        # Stop window thumbnails service
        self.window_thumbnails_service.stop()

        # Stop clipboard service
        self.clipboard_service.stop()
        
        # Stop WebSocket server
        self.stop_websocket_server()
        
        # Stop screen sharing
        self.toggle_screen_sharing(False)

    def _update_pin_configuration(self, pin_config):
        """Update PIN configuration from client"""
        try:
            use_random = pin_config.get('use_random_pin', True)
            custom_pin = pin_config.get('custom_pin', '')
            
            # Update config file
            config_path = os.path.join(os.path.expanduser('~'), '.anycommand', 'config.ini')
            
            # Read current config
            config = configparser.ConfigParser()
            if os.path.exists(config_path):
                config.read(config_path)
            
            # Update PIN configuration section
            if 'PinConfig' not in config:
                config['PinConfig'] = {}
            
            config['PinConfig']['use_random_pin'] = str(use_random).lower()
            config['PinConfig']['custom_pin'] = custom_pin if not use_random else ''
            
            # Write updated config
            with open(config_path, 'w') as f:
                config.write(f)
            
            logging.info(f"Updated PIN configuration: use_random={use_random}, custom_pin={'set' if custom_pin else 'not set'}")
            
        except Exception as e:
            logging.error(f"Error updating PIN configuration: {e}")
            raise

    def handle_gamepad_button(self, button, action):
        """Handle gamepad button press/release with mapping to keyboard/mouse"""
        try:
            if action == 'press':
                self.gamepad_state.pressed_buttons.add(button)
                
                # Map gamepad button to keyboard key
                if button in GAMEPAD_BUTTON_MAP:
                    key = GAMEPAD_BUTTON_MAP[button]
                    keyboard.press(key)
                    logging.info(f"Gamepad button {button} pressed -> {key}")
                    
            elif action == 'release':
                self.gamepad_state.pressed_buttons.discard(button)
                
                # Release mapped key
                if button in GAMEPAD_BUTTON_MAP:
                    key = GAMEPAD_BUTTON_MAP[button]
                    keyboard.release(key)
                    logging.info(f"Gamepad button {button} released -> {key}")
                    
        except Exception as e:
            logging.error(f"Error handling gamepad button {button}: {e}")

    def handle_gamepad_stick(self, stick, x, y):
        """Handle analog stick input with mouse simulation"""
        try:
            # Update stick state
            if stick == 'left':
                self.gamepad_state.left_stick = {'x': x, 'y': y}
                
                # Left stick controls WASD movement
                self._handle_movement_stick(x, y)
                
            elif stick == 'right':
                self.gamepad_state.right_stick = {'x': x, 'y': y}
                
                # Right stick controls mouse/camera
                self._handle_camera_stick(x, y)
                
        except Exception as e:
            logging.error(f"Error handling gamepad stick {stick}: {e}")

    def _handle_movement_stick(self, x, y):
        """Convert left stick to WASD movement"""
        try:
            # Dead zone
            if abs(x) < 0.1 and abs(y) < 0.1:
                # Release all movement keys
                for key in ['w', 'a', 's', 'd']:
                    keyboard.release(key)
                return
            
            # Press/release keys based on stick direction
            threshold = 0.3
            
            # Forward/backward (Y axis)
            if y < -threshold:  # Up on stick = forward
                keyboard.press('w')
                keyboard.release('s')
            elif y > threshold:  # Down on stick = backward
                keyboard.press('s')
                keyboard.release('w')
            else:
                keyboard.release('w')
                keyboard.release('s')
            
            # Left/right (X axis)
            if x < -threshold:  # Left on stick = strafe left
                keyboard.press('a')
                keyboard.release('d')
            elif x > threshold:  # Right on stick = strafe right
                keyboard.press('d')
                keyboard.release('a')
            else:
                keyboard.release('a')
                keyboard.release('d')
                
        except Exception as e:
            logging.error(f"Error in movement stick handling: {e}")

    def _handle_camera_stick(self, x, y):
        """Convert right stick to mouse movement for camera control"""
        try:
            current_time = time.time()
            dt = current_time - self.gamepad_state.last_mouse_update
            self.gamepad_state.last_mouse_update = current_time
            
            # Dead zone
            if abs(x) < 0.1 and abs(y) < 0.1:
                return
            
            # Calculate mouse movement with sensitivity and time delta
            mouse_dx = int(x * self.gamepad_state.mouse_sensitivity * dt)
            mouse_dy = int(y * self.gamepad_state.mouse_sensitivity * dt)
            
            if mouse_dx != 0 or mouse_dy != 0:
                # Use relative mouse movement
                current_pos = win32api.GetCursorPos()
                new_x = current_pos[0] + mouse_dx
                new_y = current_pos[1] + mouse_dy
                
                # Keep within screen bounds
                screen_width = win32api.GetSystemMetrics(0)
                screen_height = win32api.GetSystemMetrics(1)
                new_x = max(0, min(new_x, screen_width - 1))
                new_y = max(0, min(new_y, screen_height - 1))
                
                win32api.SetCursorPos((new_x, new_y))
                
        except Exception as e:
            logging.error(f"Error in camera stick handling: {e}")

    def handle_gamepad_motion(self, tilt_x, tilt_y):
        """Handle motion control data (accelerometer)"""
        try:
            self.gamepad_state.motion_tilt = {'x': tilt_x, 'y': tilt_y}
            
            # Use motion for fine camera adjustment or steering
            # Scale down for subtle movement
            motion_sensitivity = 100
            
            if abs(tilt_x) > 0.1 or abs(tilt_y) > 0.1:
                current_pos = win32api.GetCursorPos()
                new_x = current_pos[0] + int(tilt_x * motion_sensitivity)
                new_y = current_pos[1] + int(tilt_y * motion_sensitivity)
                
                # Keep within screen bounds
                screen_width = win32api.GetSystemMetrics(0)
                screen_height = win32api.GetSystemMetrics(1)
                new_x = max(0, min(new_x, screen_width - 1))
                new_y = max(0, min(new_y, screen_height - 1))
                
                win32api.SetCursorPos((new_x, new_y))
                
        except Exception as e:
            logging.error(f"Error handling gamepad motion: {e}")

    def handle_gamepad_gyro(self, rot_x, rot_y):
        """Handle gyroscope data for camera rotation"""
        try:
            self.gamepad_state.gyro_rotation = {'x': rot_x, 'y': rot_y}
            
            # Use gyro for precise camera control
            gyro_sensitivity = 300  # Reduced sensitivity to reduce lag
            
            # Slightly higher dead zone to reduce jitter
            if abs(rot_x) > 0.03 or abs(rot_y) > 0.03:
                current_pos = win32api.GetCursorPos()
                new_x = current_pos[0] + int(rot_y * gyro_sensitivity)  # Pitch -> X movement
                new_y = current_pos[1] + int(rot_x * gyro_sensitivity)  # Yaw -> Y movement
                
                # Keep within screen bounds
                screen_width = win32api.GetSystemMetrics(0)
                screen_height = win32api.GetSystemMetrics(1)
                new_x = max(0, min(new_x, screen_width - 1))
                new_y = max(0, min(new_y, screen_height - 1))
                
                logging.info(f"Gyro movement: ({rot_x:.3f}, {rot_y:.3f}) -> cursor ({current_pos[0]}->{new_x}, {current_pos[1]}->{new_y})")
                win32api.SetCursorPos((new_x, new_y))
            else:
                logging.debug(f"Gyro values below dead zone: x={rot_x:.3f}, y={rot_y:.3f}")
                
        except Exception as e:
            logging.error(f"Error handling gamepad gyro: {e}")

    async def handle_websocket_message(self, websocket, path):
        """Handle WebSocket messages for keyboard and text input"""
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    msg_type = data.get('type')
                    
                    if msg_type == 'text':
                        text = data.get('text', '')
                        logging.info(f"Typing text: {text}")
                        pyautogui.write(text)
                        logging.info(f"Text typed: {text}")
                            
                    elif msg_type == 'key':
                        key = data.get('key')
                        logging.info(f"Pressing key: {key}")
                        pyautogui.press(key)
                        logging.info(f"Key pressed: {key}")
                        
                except Exception as e:
                    logging.error(f"Error processing WebSocket message: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            logging.info("WebSocket client disconnected")

    def start_websocket_server(self):
        """Start WebSocket server in a separate thread"""
        if self.websocket_thread and self.websocket_thread.is_alive():
            return
            
        def run_websocket_server():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                start_server = websockets.serve(
                    self.handle_websocket_message, 
                    '0.0.0.0', 
                    8001
                )
                
                self.websocket_server = loop.run_until_complete(start_server)
                logging.info("WebSocket keyboard server running on ws://0.0.0.0:8001")
                
                loop.run_forever()
            except Exception as e:
                logging.error(f"WebSocket server error: {e}")
            finally:
                if loop.is_running():
                    loop.close()
        
        self.websocket_thread = Thread(target=run_websocket_server, daemon=True)
        self.websocket_thread.start()

    def stop_websocket_server(self):
        """Stop WebSocket server"""
        if self.websocket_server:
            try:
                self.websocket_server.close()
                self.websocket_server = None
            except:
                pass

def get_ip_addresses():
    """Get all IP addresses of the machine"""
    ip_list = []
    try:
        # Get hostname
        hostname = socket.gethostname()

        # Get IP addresses from hostname
        ips = socket.gethostbyname_ex(hostname)[2]

        # Add non-localhost IPs
        for ip in ips:
            if not ip.startswith('127.'):
                ip_list.append(ip)

        # Try to get the IP used for internet connection
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            if ip not in ip_list and not ip.startswith('127.'):
                ip_list.append(ip)
            s.close()
        except:
            pass

    except Exception as e:
        logging.error(f"Error getting IPs: {e}")
        ip_list.append('127.0.0.1')

    return ip_list

def check_already_running():
    try:
        mutex = win32event.CreateMutex(None, 0, MUTEX_NAME)
        last_error = win32api.GetLastError()
        if last_error == winerror.ERROR_ALREADY_EXISTS:
            if mutex:
                win32api.CloseHandle(mutex)
            return True
        return False
    except:
        return False

def get_pin_configuration():
    """Interactive PIN configuration during server startup"""
    print("║" + " "*2 + "🔐 PIN Configuration" + " "*29 + "║")
    print("║" + " "*48 + "║")
    print("║" + " "*2 + "Choose PIN mode:" + " "*31 + "║")
    print("║" + " "*4 + "1. Random PIN (Recommended - More Secure)" + " "*6 + "║")
    print("║" + " "*4 + "2. Custom PIN (Convenient - Less Secure)" + " "*7 + "║")
    print("║" + " "*48 + "║")
    
    while True:
        try:
            choice = input("║   Enter your choice (1 or 2): ").strip()
            
            if choice == '1':
                print("║" + " "*4 + "✅ Random PIN mode selected" + " "*19 + "║")
                return True, ''  # use_random_pin=True, custom_pin=''
            elif choice == '2':
                print("║" + " "*4 + "📝 Custom PIN mode selected" + " "*19 + "║")
                while True:
                    custom_pin = input("║   Enter 6-digit PIN: ").strip()
                    if len(custom_pin) == 6 and custom_pin.isdigit():
                        print(f"║" + " "*4 + f"✅ Custom PIN set: {custom_pin}" + " "*(25-len(custom_pin)) + "║")
                        return False, custom_pin  # use_random_pin=False, custom_pin=value
                    else:
                        print("║" + " "*4 + "❌ Invalid! PIN must be exactly 6 digits" + " "*5 + "║")
            else:
                print("║" + " "*4 + "❌ Invalid choice! Please enter 1 or 2" + " "*9 + "║")
        except KeyboardInterrupt:
            print("\n║" + " "*4 + "Server startup cancelled by user" + " "*13 + "║")
            print("╚" + "═"*48 + "╝")
            sys.exit(0)
        except Exception as e:
            print(f"║" + " "*4 + f"Error: {str(e)[:35]}" + " "*(39-len(str(e)[:35])) + "║")

if __name__ == '__main__':
    # Clear console
    os.system('cls' if os.name == 'nt' else 'clear')

    print("\n" + "╔" + "═"*48 + "╗")
    print("║" + " "*15 + "Any Command Server" + " "*16 + "║")
    print("╠" + "═"*48 + "╣")

    # Check if already running
    if check_already_running():
        print("║" + " "*2 + "❌ Server is already running!" + " "*21 + "║")
        print("║" + " "*2 + "Please close the existing server first." + " "*11 + "║")
        print("╚" + "═"*48 + "╝")
        input("\nPress Enter to exit...")
        sys.exit(1)

    try:
        # Get PIN configuration from user
        use_random_pin, custom_pin = get_pin_configuration()
        
        print("║" + " "*48 + "║")
        print("║" + " "*2 + "🚀 Starting server..." + " "*27 + "║")
        
        server = RemoteServer(pin_mode=use_random_pin, custom_pin=custom_pin)
        pin = server.get_current_pin()

        print("║" + " "*48 + "║")
        print("║" + " "*2 + "📱 Connection Details:" + " "*27 + "║")
        print("║" + " "*48 + "║")

        ips = get_ip_addresses()
        for i, ip in enumerate(ips, 1):
            print(f"║   • IP #{i}: {ip}" + " "*(41-len(ip)) + "║")

        print("║" + " "*48 + "║")
        print(f"║   • Port: 8000" + " "*35 + "║")
        print(f"║   • PIN:  {pin}" + " "*35 + "║")
        
        # Show PIN mode
        pin_mode_text = "Random PIN" if use_random_pin else "Custom PIN"
        print(f"║   • Mode: {pin_mode_text}" + " "*(34-len(pin_mode_text)) + "║")
        
        print("║" + " "*48 + "║")
        print("║" + " "*2 + "💡 Tips:" + " "*39 + "║")
        print("║" + " "*5 + "• Make sure phone and PC are on same network" + " "*4 + "║")
        print("║" + " "*5 + "• Try another IP if first one doesn't work" + " "*6 + "║")
        print("║" + " "*5 + "• Local IPs start with 192.168. or 10.0." + " "*7 + "║")

        print("╠" + "═"*48 + "╣")
        print("║" + " "*2 + "Server is running... Press Ctrl+C to stop" + " "*8 + "║")
        print("╚" + "═"*48 + "╝\n")

        server.start()
    except Exception as e:
        logging.error(f"Failed to start server: {e}")
        print("\n❌ Error starting server.")
        input("\nPress Enter to exit...")
        sys.exit(1)