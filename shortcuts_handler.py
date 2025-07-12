from pynput.keyboard import Key, Controller
import time

keyboard = Controller()

# Map special key names to pynput Keys
SPECIAL_KEYS = {
    'ctrl': Key.ctrl,
    'shift': Key.shift,
    'alt': Key.alt,
    'win': Key.cmd,  # or Key.cmd_l for left Windows key
    'tab': Key.tab,
    'enter': Key.enter,
    'space': Key.space,
    'up': Key.up,
    'down': Key.down,
    'left': Key.left,
    'right': Key.right,
    'esc': Key.esc,
    'f': 'f',
    'n': 'n',
    'p': 'p',
    't': 't',
    'r': 'r',
    'm': 'm',
    'c': 'c',
    'k': 'k',
    'l': 'l',
    'j': 'j',
    'w': 'w',
    'd': 'd',
    'e': 'e',
    'i': 'i',
    'x': 'x',
    's': 's',
    'b': 'b',
    'h': 'h',
    ',': ',',
    '.': '.',
    '+': '+',
    '-': '-',
    'plus': '+',    # For zoom in (Ctrl+=)
    'minus': '-',    # For zoom out (Ctrl+-)
}

def send_shortcut(keys):
    """Send keyboard shortcut by pressing all keys in sequence"""
    pressed_keys = []
    try:
        # Press all keys in sequence
        for key in keys:
            key_lower = key.lower()
            if key_lower in SPECIAL_KEYS:
                k = SPECIAL_KEYS[key_lower]
                keyboard.press(k)
                pressed_keys.append(k)
            else:
                keyboard.press(key)
                pressed_keys.append(key)
        
        # Small delay to ensure keys are registered
        time.sleep(0.1)
        
    finally:
        # Release all keys in reverse order
        for key in reversed(pressed_keys):
            keyboard.release(key)

def handle_shortcut(shortcut_id, app_id, keys=None):
    """Handle shortcuts based on ID and application"""
    if keys:
        # If keys are provided, use them directly
        send_shortcut(keys)
    else:
        # Fallback to predefined shortcuts if no keys provided
        default_shortcuts = {
            'windows': {
                'show_desktop': ['win', 'd'],
                'task_view': ['win', 'tab'],
                'switch_apps': ['alt', 'tab'],
                'lock_pc': ['win', 'l'],
                # ... add more defaults
            },
            'chrome': {
                'new_tab': ['ctrl', 't'],
                'close_tab': ['ctrl', 'w'],
                # ... add more defaults
            },
            # ... add more apps
        }
        
        if app_id in default_shortcuts and shortcut_id in default_shortcuts[app_id]:
            send_shortcut(default_shortcuts[app_id][shortcut_id])

        # Add more specific shortcuts
        if app_id == 'youtube':
            if shortcut_id == 'play_pause':
                send_shortcut(['k'])
            elif shortcut_id == 'next_video':
                send_shortcut(['shift', 'n'])
            # Add more YouTube shortcuts...
        
        elif app_id == 'spotify':
            if shortcut_id == 'play_pause':
                send_shortcut(['space'])
            elif shortcut_id == 'next_track':
                send_shortcut(['ctrl', 'right'])
            # Add more Spotify shortcuts...
        
        elif app_id == 'vlc':
            if shortcut_id == 'play_pause':
                send_shortcut(['space'])
            elif shortcut_id == 'next_track':
                send_shortcut(['n'])
            # Add more VLC shortcuts... 