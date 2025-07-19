import customtkinter as ctk
import socket
import pyautogui
import keyboard
import threading
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
import win32event
import winerror
import win32security
import psutil
from pystray import Icon as TrayIcon, Menu as TrayMenu, MenuItem as TrayMenuItem
from PIL import Image, ImageDraw
import shutil
from file_transfer_service import FileTransferService
from window_thumbnails_service import WindowThumbnailsService
import webbrowser
import winreg

# Update mutex name
MUTEX_NAME = "Global\\AnyCommandServer_SingleInstance"

def kill_other_instances():
    """Kill any other running instances of the server"""
    current_pid = os.getpid()
    current_process = psutil.Process(current_pid)
    current_name = current_process.name()
    
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            # If it's the same executable but different PID
            if proc.name() == current_name and proc.pid != current_pid:
                proc.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

class ServerGUI(ctk.CTk):
    def __init__(self):
        # Check for existing instance before initializing GUI
        self.mutex = None
        if self.is_already_running():
            # Instead of showing a dialog, try to activate the existing window
            self.activate_existing_instance()
            return

        super().__init__()
        
        # Load preferences
        self.load_preferences()
        
        # Apply a modern theme
        self.configure(fg_color="#1E1E2E")  # Dark background with a hint of blue
        
        # Configure window
        self.title("Any Command Server")
        self.geometry("400x650")  # Increased height to accommodate PIN configuration
        self.resizable(True, True)
        self.attributes('-alpha', 0.97)  # Slight transparency
        
        # Set custom fonts
        self.title_font = ("Segoe UI", 22, "bold")
        self.heading_font = ("Segoe UI", 14, "bold")
        self.normal_font = ("Segoe UI", 12)
        self.small_font = ("Segoe UI", 11)
        
        # Allow window resizing
        self.resizable(True, True)
        
        # Set minimum window size to prevent layout issues
        self.minsize(380, 600)    # Increased minimum height for PIN configuration
        
        # Create main container with weight to allow proper resizing
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.pack(fill="both", expand=True, padx=15, pady=12)  # Reduced padding
        
        # Use grid instead of pack for better resizing
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        main_container.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        
        # Header with logo and title
        header = ctk.CTkFrame(main_container, fg_color="transparent")
        header.pack(fill="x", pady=(0, 20))
        
        # Try to load logo image
        try:
            # Use the robust icon loading method that handles packaged applications
            logo_image_pil = self.load_app_icon()
            if logo_image_pil:
                logo_image = ctk.CTkImage(logo_image_pil, size=(48, 48))
                logo_label = ctk.CTkLabel(header, image=logo_image, text="")
                logo_label.pack(side="left", padx=(0, 15))
        except Exception as e:
            logging.error(f"Failed to load logo: {e}")
        
        # App title
        title_label = ctk.CTkLabel(
            header, 
            text="Any Command Server",
            font=self.title_font,
            text_color="#C0E1FF"  # Light blue text
        )
        title_label.pack(side="left", fill="x", expand=True, pady=(0, 8))  # Reduced top padding
        
        # Status card
        status_card = ctk.CTkFrame(
            main_container,
            fg_color="#262639",  # Slightly lighter background
            corner_radius=15,
            border_width=1,
            border_color="#3D3D5C"  # Subtle border
        )
        status_card.pack(fill="x", pady=(0, 12), ipady=8)  # Reduced padding and internal padding
        
        # Card title
        ctk.CTkLabel(
            status_card,
            text="CONNECTION STATUS",
            font=self.heading_font,
            text_color="#7EB6FF"  # Bright blue for headings
        ).pack(pady=(15, 20))
        
        # Status indicators with better styling
        status_container = ctk.CTkFrame(status_card, fg_color="transparent")
        status_container.pack(fill="x", padx=25)
        
        # Status icons
        icon_size = (24, 24)
        network_icon = self.create_icon("🌐", "#7EB6FF", icon_size)  # Network icon
        key_icon = self.create_icon("🔑", "#FFD166", icon_size)      # Key icon
        status_icon = self.create_icon("✅", "#4CAF50", icon_size)   # Check icon
        
        # IP Address
        ip_row = ctk.CTkFrame(status_container, fg_color="transparent")
        ip_row.pack(fill="x", pady=(8, 4))  # Reduced padding
        
        if network_icon:
            ctk.CTkLabel(ip_row, image=network_icon, text="").pack(side="left", padx=(0, 15))
        else:
            ctk.CTkLabel(ip_row, text="🌐", font=self.normal_font).pack(side="left", padx=(0, 15))
        ctk.CTkLabel(ip_row, text="IP Address:", width=100, anchor="w", font=self.normal_font).pack(side="left")
        
        self.ip_label = ctk.CTkLabel(
            ip_row,
            text="Connecting...",
            font=self.normal_font,
            fg_color="#31314A",
            corner_radius=6,
            height=32,
            anchor="w",
            padx=10
        )
        self.ip_label.pack(side="left", fill="x", expand=True)
        
        # PIN
        pin_row = ctk.CTkFrame(status_container, fg_color="transparent")
        pin_row.pack(fill="x", pady=(8, 4))  # Reduced padding
        
        if key_icon:
            ctk.CTkLabel(pin_row, image=key_icon, text="").pack(side="left", padx=(0, 15))
        else:
            ctk.CTkLabel(pin_row, text="🔑", font=self.normal_font).pack(side="left", padx=(0, 15))
        ctk.CTkLabel(pin_row, text="PIN Code:", width=100, anchor="w", font=self.normal_font).pack(side="left")
        
        self.pin_label = ctk.CTkLabel(
            pin_row,
            text="------",
            font=self.normal_font,
            fg_color="#31314A",
            corner_radius=6,
            height=32,
            anchor="w",
            padx=10
        )
        self.pin_label.pack(side="left", fill="x", expand=True)
        
        # Server Status
        status_row = ctk.CTkFrame(main_container, fg_color="transparent")
        status_row.pack(fill="x", pady=(0, 8))  # Reduced padding
        
        if status_icon:
            ctk.CTkLabel(status_row, image=status_icon, text="").pack(side="left", padx=(0, 15))
        else:
            ctk.CTkLabel(status_row, text="✅", font=self.normal_font).pack(side="left", padx=(0, 15))
        ctk.CTkLabel(status_row, text="Status:", width=100, anchor="w", font=self.normal_font).pack(side="left")
        
        self.status_label = ctk.CTkLabel(
            status_row,
            text="Starting...",
            font=("Segoe UI", 11),  # Smaller font
            fg_color="#1E5B2D",
            text_color="#AAFFAA",
            corner_radius=4,  # Less rounded corners
            height=26,  # Smaller height
            anchor="w",
            padx=8
        )
        self.status_label.pack(side="left", fill="x", expand=True)
        
        # PIN Configuration Section
        pin_config_card = ctk.CTkFrame(
            main_container,
            fg_color="#262639",  # Slightly lighter background
            corner_radius=15,
            border_width=1,
            border_color="#3D3D5C"  # Subtle border
        )
        pin_config_card.pack(fill="x", pady=(12, 0), ipady=8)
        
        # PIN Config title
        ctk.CTkLabel(
            pin_config_card,
            text="PIN CONFIGURATION",
            font=self.heading_font,
            text_color="#7EB6FF"  # Bright blue for headings
        ).pack(pady=(15, 10))
        
        # PIN mode selection frame
        pin_mode_frame = ctk.CTkFrame(pin_config_card, fg_color="transparent")
        pin_mode_frame.pack(fill="x", padx=25, pady=(0, 10))
        
        # PIN mode toggle
        pin_mode_row = ctk.CTkFrame(pin_mode_frame, fg_color="transparent")
        pin_mode_row.pack(fill="x", pady=(0, 10))
        
        # Random PIN mode switch
        ctk.CTkLabel(pin_mode_row, text="PIN Mode:", font=self.normal_font, anchor="w").pack(side="left")
        
        # Use saved preference for PIN mode, default to True (Random) if not found
        pin_mode_default = self.preferences.get('use_random_pin', True)
        self.pin_mode_var = ctk.BooleanVar(value=pin_mode_default)
        self.pin_mode_switch = ctk.CTkSwitch(
            pin_mode_row,
            text="Random PIN",
            variable=self.pin_mode_var,
            font=self.small_font,
            command=self.on_pin_mode_changed
        )
        self.pin_mode_switch.pack(side="right")
        
        # PIN mode info label
        self.pin_mode_info = ctk.CTkLabel(
            pin_mode_frame,
            text="Random PIN mode: Server generates a new PIN each restart (More Secure)",
            font=self.small_font,
            text_color="#AAB2BD",
            anchor="w",
            wraplength=350,
            justify="left"
        )
        self.pin_mode_info.pack(fill="x", pady=(0, 10))
        
        # Custom PIN input frame (initially hidden)
        self.custom_pin_frame = ctk.CTkFrame(pin_mode_frame, fg_color="transparent")
        
        custom_pin_row = ctk.CTkFrame(self.custom_pin_frame, fg_color="transparent")
        custom_pin_row.pack(fill="x", pady=(0, 8))
        
        ctk.CTkLabel(custom_pin_row, text="Custom PIN:", font=self.normal_font, anchor="w").pack(side="left")
        
        self.custom_pin_entry = ctk.CTkEntry(
            custom_pin_row,
            placeholder_text="Enter 6-digit PIN",
            font=self.normal_font,
            width=120,
            justify="center"
        )
        self.custom_pin_entry.pack(side="right")
        self.custom_pin_entry.bind('<KeyRelease>', self.on_custom_pin_changed)
        
        # Custom PIN save button
        self.save_pin_button = ctk.CTkButton(
            self.custom_pin_frame,
            text="Apply PIN Settings",
            font=self.small_font,
            height=28,
            command=self.save_pin_configuration,
            fg_color="#28a745",
            hover_color="#218838"
        )
        self.save_pin_button.pack(pady=(5, 0))
        
        # Add restart server button for PIN changes
        restart_button = ctk.CTkButton(
            pin_config_card,
            text="🔄 Restart Server",
            font=self.normal_font,
            height=32,
            command=self.restart_server,
            fg_color="#007bff",
            hover_color="#0056b3"
        )
        restart_button.pack(pady=(10, 15))
        
        # Now add a row of buttons for all functions
        buttons_frame = ctk.CTkFrame(main_container, fg_color="transparent")
        buttons_frame.pack(fill="x", pady=(10, 0))
        
        # First row of buttons
        first_row = ctk.CTkFrame(buttons_frame, fg_color="transparent")
        first_row.pack(fill="x", pady=(0, 8))  # Reduced padding
        
        # How to Connect button
        help_button = self.create_gradient_button(
            first_row,
            "How to Connect",
            self.show_instructions,
            gradient=["#3867d6", "#4b7bec"],  # Professional blue
        )
        help_button.pack(side="left", fill="x", expand=True, padx=(0, 4))
        
        # Open folder button
        open_folder_button = self.create_gradient_button(
            first_row,
            "Open Transfer Folder",
            self.open_transfer_directory,
            gradient=["#20bf6b", "#26de81"],  # Professional green
        )
        open_folder_button.pack(side="left", fill="x", expand=True, padx=(4, 0))
        
        # Second row of buttons
        second_row = ctk.CTkFrame(buttons_frame, fg_color="transparent")
        second_row.pack(fill="x", pady=(0, 8))  # Add padding between rows
        
        # Settings button
        settings_button = self.create_gradient_button(
            second_row,
            "Settings",
            self.show_settings,
            gradient=["#f39c12", "#e67e22"],  # Professional orange
        )
        settings_button.pack(side="left", fill="x", expand=True, padx=(0, 4))
        
        # Online Help button (new)
        online_help_button = self.create_gradient_button(
            second_row,
            "Help",
            self.open_help_page,
            gradient=["#8e44ad", "#9b59b6"],  # Professional purple
        )
        online_help_button.pack(side="left", fill="x", expand=True, padx=(4, 4))
        
        # Minimize button
        minimize_button = self.create_gradient_button(
            second_row,
            "Minimize to Tray",
            self.minimize_window,
            gradient=["#4b6584", "#778ca3"],  # Professional slate
        )
        minimize_button.pack(side="left", fill="x", expand=True, padx=(4, 0))
        
        # Third row of buttons
        third_row = ctk.CTkFrame(buttons_frame, fg_color="transparent")
        third_row.pack(fill="x")
        
        # Exit button (moved to its own row)
        quit_button = self.create_gradient_button(
            third_row,
            "Exit",
            self.quit_app,
            gradient=["#eb3b5a", "#fc5c65"],  # Professional red
        )
        quit_button.pack(fill="x", expand=True)
        
        # Version info at bottom
        version_label = ctk.CTkLabel(
            main_container,
            text="v1.2.7",
            font=("Segoe UI", 9),  # Smaller font
            text_color="#4D4D6F"  # More subtle color
        )
        version_label.pack(side="right", pady=(8, 0))  # Less padding
        
        # Start server in separate thread
        self.server = None
        self.start_server_thread()

        # Setup global hotkey
        keyboard.hook(self.handle_hotkey)
        self.is_hidden = False
        
        # Initialize the tray icon but don't show it yet
        self.tray_icon = None
        self.setup_tray_icon()
        
        # Center window on screen
        self.center_window()

        # Activity tracking variables
        self.last_activity_time = time.time()
        self.inactivity_timeout = 7200  # 2 hours in seconds
        self.auto_disconnect_enabled = False  # Changed from True to False

        # Add file transfer service
        self.file_transfer_service = FileTransferService()
        
        # Add window thumbnails service
        self.window_thumbnails_service = WindowThumbnailsService()

        # Apply PIN configuration to UI now that all elements are created
        self.apply_pin_configuration_to_ui()
        
        # Debug: Log the loaded PIN configuration
        use_random_pin = self.preferences.get('use_random_pin', True)
        custom_pin = self.preferences.get('custom_pin', '')
        logging.info(f"Loaded PIN configuration: use_random_pin={use_random_pin}, has_custom_pin={bool(custom_pin)}")

    def get_config_directory(self):
        """Get the appropriate directory for configuration files"""
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            # Use %APPDATA%/AnyCommand for persistent storage
            appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
            config_dir = os.path.join(appdata, 'AnyCommand')
        else:
            # Running as script - use script directory
            config_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Create directory if it doesn't exist
        os.makedirs(config_dir, exist_ok=True)
        return config_dir

    def load_preferences(self):
        """Load user preferences from file"""
        self.preferences = {}
        try:
            config = configparser.ConfigParser()
            config_dir = self.get_config_directory()
            config_file = os.path.join(config_dir, 'preferences.ini')
            
            logging.info(f"Attempting to load preferences from: {config_file}")
            
            if os.path.exists(config_file):
                config.read(config_file)
                if 'Preferences' in config:
                    self.preferences = dict(config['Preferences'])
                    # Convert string 'True'/'False' to boolean
                    if 'auto_hide' in self.preferences:
                        self.preferences['auto_hide'] = config['Preferences'].getboolean('auto_hide')
                    if 'use_random_pin' in self.preferences:
                        self.preferences['use_random_pin'] = config['Preferences'].getboolean('use_random_pin')
                    logging.info(f"Loaded preferences from {config_file}: {self.preferences}")
                else:
                    logging.info(f"No [Preferences] section found in {config_file}")
            else:
                logging.info(f"Preferences file {config_file} does not exist, using defaults")
        except Exception as e:
            logging.error(f"Error loading preferences: {e}")

    def save_preferences(self):
        """Save user preferences to file"""
        try:
            config = configparser.ConfigParser()
            config['Preferences'] = {
                'auto_hide': str(self.preferences.get('auto_hide', False)),
                'use_random_pin': str(self.preferences.get('use_random_pin', True)),
                'custom_pin': str(self.preferences.get('custom_pin', ''))
            }
            config_dir = self.get_config_directory()
            config_file = os.path.join(config_dir, 'preferences.ini')
            
            logging.info(f"Saving preferences to: {config_file}")
            
            with open(config_file, 'w') as f:
                config.write(f)
                
            logging.info(f"Preferences saved successfully: {config['Preferences']}")
        except Exception as e:
            logging.error(f"Error saving preferences: {e}")

    def minimize_window(self):
        """Minimize to tray instead of taskbar"""
        # Hide the window
        self.withdraw()
        
        # Show the tray icon if it's not already visible
        if self.tray_icon and not self.tray_icon.visible:
            self.tray_icon.run_detached()

    def start_server_thread(self):
        self.server_thread = threading.Thread(target=self.start_server)
        self.server_thread.daemon = True
        self.server_thread.start()

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def stop_move(self, event):
        self.x = None
        self.y = None

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.winfo_x() + deltax
        y = self.winfo_y() + deltay
        self.geometry(f"+{x}+{y}")

    def get_ip_addresses(self):
        ips = []
        try:
            # Try to get the IP used for internet connection
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ips.append(s.getsockname()[0])
            s.close()
        except:
            # Fallback to hostname method
            try:
                hostname = socket.gethostname()
                ips = [ip for ip in socket.gethostbyname_ex(hostname)[2] 
                       if not ip.startswith("127.")]
            except:
                pass
        return ips or ["127.0.0.1"]

    def update_status(self, ip, pin, status):
        self.ip_label.configure(text=f"📡 IP: {ip}")
        self.pin_label.configure(text=f"🔑 PIN: {pin}")
        self.status_label.configure(text=f"📊 Status: {status}")

    def start_server(self):
        try:
            from remote_server import RemoteServer
            
            # Get PIN configuration from preferences
            use_random_pin = self.preferences.get('use_random_pin', True)
            custom_pin = self.preferences.get('custom_pin', '')
            
            # Initialize server with PIN configuration
            if use_random_pin:
                self.server = RemoteServer(pin_mode=True, custom_pin='')
            else:
                if len(custom_pin) == 6 and custom_pin.isdigit():
                    self.server = RemoteServer(pin_mode=False, custom_pin=custom_pin)
                else:
                    # Fallback to random if custom PIN is invalid
                    logging.warning("Invalid custom PIN, falling back to random mode")
                    self.server = RemoteServer(pin_mode=True, custom_pin='')
            
            # Update GUI with connection info
            ip = self.get_ip_addresses()[0]
            pin = self.server.get_current_pin()
            self.update_status(ip, pin, "Running")
            
            self.server.start()

            # Start file transfer service
            self.file_transfer_service.start()
            self.window_thumbnails_service.start()
        except Exception as e:
            self.update_status("Error", "Error", f"Failed: {str(e)}")
            logging.error(f"Error starting server: {e}")

    def restart_server(self):
        try:
            if self.server:
                self.server.server.close()
            self.update_status("...", "...", "Restarting...")
            self.start_server_thread()
        except Exception as e:
            self.update_status("Error", "Error", f"Restart failed: {str(e)}")

    def confirm_hide(self):
        """Show confirmation dialog before hiding"""
        # Check if user chose to remember and skip dialog
        if self.preferences.get('auto_hide', False):
            self.hide_window()
            return

        # Create a new root window for the dialog
        root = ctk.CTk()
        root.withdraw()  # Hide the root window
        
        dialog = ctk.CTkToplevel(root)  # Make dialog a child of the new root
        dialog.title("Hide Server")
        dialog.geometry("400x200")
        dialog.attributes('-topmost', True)
        dialog.resizable(False, False)
        dialog.focus_force()  # Force focus to the dialog
        
        # Force the dialog to update its internal state before calculating screen geometry
        dialog.update_idletasks()
        
        # Center on screen
        width = 400
        height = 200
        screen_width = dialog.winfo_screenwidth()
        screen_height = dialog.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        dialog.geometry(f'{width}x{height}+{x}+{y}')
        
        frame = ctk.CTkFrame(dialog, fg_color="#1E1E1E")
        frame.pack(expand=True, fill="both", padx=20, pady=20)
        
        # Title
        ctk.CTkLabel(
            frame,
            text="Hide Server Window",
            font=("Arial", 16, "bold"),
            text_color="#FFFFFF"
        ).pack(pady=(0, 5))
        
        # Message
        ctk.CTkLabel(
            frame,
            text="The server will continue running in the background\nPress Ctrl + R to show the window again",
            font=("Arial", 13),
            justify="center",
            text_color="#E0E0E0"
        ).pack(pady=(5, 15))
        
        # Remember choice checkbox
        remember_var = ctk.BooleanVar(value=False)
        remember_checkbox = ctk.CTkCheckBox(
            frame,
            text="Don't show this message again",
            variable=remember_var,
            font=("Arial", 12),
            text_color="#E0E0E0",
            fg_color="#2E7D32",
            hover_color="#1B5E20"
        )
        remember_checkbox.pack(pady=(0, 15))
        
        # Button frame
        button_frame = ctk.CTkFrame(frame, fg_color="transparent")
        button_frame.pack(fill="x")
        
        # Cancel button
        ctk.CTkButton(
            button_frame,
            text="Cancel",
            command=dialog.destroy,
            width=100,
            height=32,
            font=("Arial", 13),
            fg_color="#424242",
            hover_color="#616161"
        ).pack(side="left", padx=10, expand=True)
        
        def hide_with_preference():
            if remember_var.get():
                self.preferences['auto_hide'] = True
                self.save_preferences()
            dialog.destroy()
            self.hide_window()
        
        # Hide button
        ctk.CTkButton(
            button_frame,
            text="Hide",
            command=hide_with_preference,
            width=100,
            height=32,
            font=("Arial", 13, "bold"),
            fg_color="#2E7D32",
            hover_color="#1B5E20"
        ).pack(side="right", padx=10, expand=True)

    def hide_window(self):
        """Hide the window"""
        self.withdraw()
        self.is_hidden = True
        # Show system tray notification
        self.show_notification("Server Hidden", "Press Ctrl + R to show the server window")

    def show_window(self):
        """Show the window"""
        if self.is_hidden:
            self.deiconify()
            self.lift()
            self.is_hidden = False

    def handle_hotkey(self, event):
        """Handle global hotkeys"""
        try:
            # Check for Ctrl+Alt+A
            if event.event_type == keyboard.KEY_DOWN and event.name == 'a' and keyboard.is_pressed('ctrl') and keyboard.is_pressed('alt'):
                # Toggle window visibility
                if self.is_hidden or not self.winfo_viewable():
                    self.show_from_tray()
                    self.is_hidden = False
                else:
                    self.minimize_window()
                    self.is_hidden = True
        except Exception as e:
            logging.error(f"Error in hotkey handler: {e}")

    def show_notification(self, title, message):
        """Show Windows notification"""
        try:
            # Try system tray balloon first (most reliable)
            if hasattr(self, 'tray_icon') and self.tray_icon:
                # Use the tray icon to show balloon tip
                import threading
                def show_balloon():
                    try:
                        # This uses the system tray icon's balloon notification
                        from pystray import Icon
                        if hasattr(self.tray_icon, '_icon') and self.tray_icon._icon:
                            # Show notification through system tray
                            self._show_tray_notification(title, message)
                        else:
                            raise Exception("Tray icon not available")
                    except:
                        self._show_fallback_notification(title, message)
                
                thread = threading.Thread(target=show_balloon, daemon=True)
                thread.start()
                return
        except:
            pass
        
        # Fallback to simple notification
        self._show_fallback_notification(title, message)

    def _show_tray_notification(self, title, message):
        """Show notification using system tray"""
        try:
            # Use Windows shell_notify_icon for balloon tip
            import ctypes
            from ctypes import wintypes, Structure, POINTER
            
            # Constants for balloon notification
            NIM_MODIFY = 0x00000001
            NIF_INFO = 0x00000010
            NIIF_INFO = 0x00000001
            
            class NOTIFYICONDATA(Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("hWnd", wintypes.HWND),
                    ("uID", wintypes.UINT),
                    ("uFlags", wintypes.UINT),
                    ("uCallbackMessage", wintypes.UINT),
                    ("hIcon", wintypes.HICON),
                    ("szTip", wintypes.WCHAR * 128),
                    ("dwState", wintypes.DWORD),
                    ("dwStateMask", wintypes.DWORD),
                    ("szInfo", wintypes.WCHAR * 256),
                    ("uTimeout", wintypes.UINT),
                    ("szInfoTitle", wintypes.WCHAR * 64),
                    ("dwInfoFlags", wintypes.DWORD),
                    ("guidItem", wintypes.BYTE * 16),
                    ("hBalloonIcon", wintypes.HICON)
                ]
            
            # This is a simplified approach - just use the fallback for now
            raise Exception("Use fallback")
            
        except:
            self._show_fallback_notification(title, message)

    def _show_fallback_notification(self, title, message):
        """Fallback notification method"""
        try:
            # Use simple console output and optional message box
            logging.info(f"Notification: {title} - {message}")
            print(f"📢 {title}: {message}")
            
            # For important notifications, show a non-blocking message box
            if any(keyword in title.lower() for keyword in ['error', 'failed', 'invalid']):
                import threading
                def show_error_box():
                    try:
                        import ctypes
                        # Non-blocking message box for errors only
                        ctypes.windll.user32.MessageBoxW(
                            0, message, f"Any Command - {title}", 
                            0x40 | 0x1000  # MB_ICONINFORMATION | MB_SYSTEMMODAL
                        )
                    except:
                        pass
                
                thread = threading.Thread(target=show_error_box, daemon=True)
                thread.start()
                
        except Exception as e:
            # Ultimate fallback - just log
            print(f"Notification (fallback failed): {title} - {message}")
            logging.error(f"Notification system failed: {e}")

    def is_already_running(self):
        """Check if another instance is already running"""
        try:
            # Try to create mutex with initial ownership
            security_attributes = win32security.SECURITY_ATTRIBUTES()
            security_attributes.bInheritHandle = 1
            
            self.mutex = win32event.CreateMutex(security_attributes, True, MUTEX_NAME)
            if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
                if self.mutex:
                    win32api.CloseHandle(self.mutex)
                    self.mutex = None
                return True
            return False
        except Exception as e:
            logging.error(f"Mutex error: {e}")
            if self.mutex:
                win32api.CloseHandle(self.mutex)
                self.mutex = None
            return True

    def activate_existing_instance(self):
        """Activate the existing running instance instead of showing a dialog"""
        try:
            import win32gui
            import win32con
            
            def enum_window_callback(hwnd, pid):
                if win32gui.IsWindowVisible(hwnd):
                    window_title = win32gui.GetWindowText(hwnd)
                    if "Any Command Server" in window_title:
                        # Found the existing window, restore and bring to front
                        if win32gui.IsIconic(hwnd):
                            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                        win32gui.SetForegroundWindow(hwnd)
                        return False  # Stop enumeration
                return True  # Continue enumeration
            
            # Enumerate all windows to find the existing server window
            win32gui.EnumWindows(enum_window_callback, None)
            
        except Exception as e:
            logging.error(f"Error activating existing instance: {e}")
            # Fallback: do nothing instead of showing dialog
            pass

    def show_already_running_dialog(self):
        """Show dialog when another instance is already running"""
        # Get the root window for the system-level dialog
        from tkinter import Tk, messagebox
        root = Tk()
        root.withdraw()  # Hide the root window
        
        messagebox.showinfo(
            "Any Command Server",
            "The server is running.\n\n"
            "You can access it by pressing Ctrl+Alt+A or by clicking the tray icon."
        )
        root.destroy()

    def quit_app(self):
        """Clean up before quitting"""
        try:
            # Stop tray icon if active
            if self.tray_icon and self.tray_icon.visible:
                self.tray_icon.stop()
                
            keyboard.unhook_all()
            if hasattr(self, 'server') and self.server:
                self.server.quit()
            if self.mutex:
                win32api.CloseHandle(self.mutex)
                self.mutex = None

            # Stop file transfer service
            self.file_transfer_service.stop()
            
            # Stop window thumbnails service
            if hasattr(self, 'window_thumbnails_service'):
                self.window_thumbnails_service.stop()
        except Exception as e:
            logging.error(f"Error during cleanup: {e}")
        finally:
            self.quit()

    def __del__(self):
        if hasattr(self, 'mutex') and self.mutex:
            win32api.CloseHandle(self.mutex)
            self.mutex = None

    def setup_tray_icon(self):
        """Set up the system tray icon and menu"""
        # Load the actual app icon instead of creating one
        icon_image = self.load_app_icon()
        
        # Create the tray menu
        tray_menu = TrayMenu(
            TrayMenuItem('Show Window', self.show_from_tray),
            TrayMenuItem('Settings', self.show_settings),
            TrayMenu.SEPARATOR,
            TrayMenuItem('Exit', self.quit_app)
        )
        
        # Create the tray icon with double-click support
        self.tray_icon = TrayIcon(
            'AnyCommandServer', 
            icon_image,
            'Any Command Server', 
            tray_menu
        )
        
        # Set the left-click and double-click behavior
        self.tray_icon.on_click = self.on_tray_click

    def load_app_icon(self):
        """Load the application icon file"""
        # First check in the same directory as the executable (install location)
        executable_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(executable_dir, 'icon.ico')
        
        # For PyInstaller bundled applications, check for bundled data
        if getattr(sys, 'frozen', False):
            try:
                # PyInstaller creates a temp folder and stores path in _MEIPASS
                bundle_dir = sys._MEIPASS
                bundled_icon_path = os.path.join(bundle_dir, 'icon.ico')
                if os.path.exists(bundled_icon_path):
                    logging.info(f"Loading icon from PyInstaller bundle: {bundled_icon_path}")
                    return Image.open(bundled_icon_path)
            except Exception as e:
                logging.error(f"Error loading icon from bundle: {e}")
        
        # Try to load from the executable directory first (where it should be when installed)
        if os.path.exists(icon_path):
            try:
                logging.info(f"Loading icon from executable directory: {icon_path}")
                return Image.open(icon_path)
            except Exception as e:
                logging.error(f"Error loading icon from {icon_path}: {e}")
        
        # Look for icon in the server directory
        server_dir = os.path.dirname(os.path.abspath(__file__))
        server_icon_path = os.path.join(server_dir, 'icon.ico')
        
        if os.path.exists(server_icon_path) and server_icon_path != icon_path:
            try:
                logging.info(f"Loading icon from server directory: {server_icon_path}")
                return Image.open(server_icon_path)
            except Exception as e:
                logging.error(f"Error loading icon from {server_icon_path}: {e}")
        
        # If all fails, try to find it in the installer directory
        try:
            installer_dir = os.path.join(os.path.dirname(server_dir), 'installer')
            installer_icon = os.path.join(installer_dir, 'icon.ico')
            
            if os.path.exists(installer_icon):
                try:
                    # Copy to the executable directory
                    shutil.copy2(installer_icon, icon_path)
                    logging.info(f"Copied icon from installer to executable directory")
                    return Image.open(icon_path)
                except Exception as e:
                    logging.error(f"Failed to copy icon from installer: {e}")
        except Exception:
            pass
        
        # Fallback to creating a simple icon
        logging.warning("Could not find icon file, using generated icon")
        return self.create_tray_icon_image()

    def create_tray_icon_image(self):
        """Create a simple square icon with AC text"""
        # Create a 64x64 image with a blue background
        image = Image.new('RGB', (64, 64), color=(0, 120, 212))
        draw = ImageDraw.Draw(image)
        
        # Draw "AC" text in white
        # Note: In a production app, you would load an actual icon file
        draw.text((20, 20), "AC", fill=(255, 255, 255))
        
        return image

    def show_from_tray(self):
        """Show window from tray icon"""
        # Make window visible again
        self.deiconify()
        self.lift()
        self.focus_force()
        
        # Optional: Hide the tray icon when window is visible
        # self.tray_icon.stop()

    def hide_to_tray(self):
        """Hide to tray manually (for the hide button)"""
        self.minimize_window()

    def toggle_window(self):
        """Toggle window visibility - useful for hotkey"""
        if self.winfo_viewable():
            self.minimize_window()
        else:
            self.show_from_tray()

    def show_settings(self):
        """Show settings window"""
        settings_window = ctk.CTkToplevel(self)
        settings_window.title("Settings")
        settings_window.geometry("450x400")
        settings_window.resizable(False, False)
        settings_window.focus_force()
        
        # Make it modal and center it
        settings_window.grab_set()
        settings_window.transient(self)
        settings_window.update_idletasks()
        width = settings_window.winfo_width()
        height = settings_window.winfo_height()
        x = self.winfo_rootx() + (self.winfo_width() // 2) - (width // 2)
        y = self.winfo_rooty() + (self.winfo_height() // 2) - (height // 2)
        settings_window.geometry(f"{width}x{height}+{x}+{y}")
        
        # Main content frame
        content_frame = ctk.CTkFrame(
            settings_window,
            fg_color="#262639",
            corner_radius=15,
        )
        content_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Title
        ctk.CTkLabel(
            content_frame, 
            text="SETTINGS", 
            font=self.heading_font,
            text_color="#7EB6FF"
        ).pack(pady=(15, 20))
        
        # Settings sections
        settings_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        settings_frame.pack(fill="both", expand=True, padx=25, pady=(0, 15))
        
        # Startup section
        startup_section = ctk.CTkFrame(settings_frame, fg_color="#31314A", corner_radius=10)
        startup_section.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(
            startup_section,
            text="Startup Settings",
            font=self.normal_font,
            text_color="#FFFFFF"
        ).pack(pady=(10, 5))
        
        # Autostart checkbox
        autostart_var = ctk.BooleanVar(value=self.get_autostart_setting())
        autostart_checkbox = ctk.CTkCheckBox(
            startup_section,
            text="Start with Windows",
            variable=autostart_var,
            font=self.small_font,
            command=lambda: self.set_autostart_setting(autostart_var.get()),
            fg_color="#2E7D32",
            hover_color="#1B5E20"
        )
        autostart_checkbox.pack(pady=(5, 10), padx=20, anchor="w")
        
        # Behavior section
        behavior_section = ctk.CTkFrame(settings_frame, fg_color="#31314A", corner_radius=10)
        behavior_section.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(
            behavior_section,
            text="Behavior Settings",
            font=self.normal_font,
            text_color="#FFFFFF"
        ).pack(pady=(10, 5))
        
        # Auto-hide setting
        auto_hide_var = ctk.BooleanVar(value=self.preferences.get('auto_hide', False))
        auto_hide_checkbox = ctk.CTkCheckBox(
            behavior_section,
            text="Auto-hide confirmation (Skip hide dialog)",
            variable=auto_hide_var,
            font=self.small_font,
            command=lambda: self._update_auto_hide_setting(auto_hide_var.get()),
            fg_color="#2E7D32",
            hover_color="#1B5E20"
        )
        auto_hide_checkbox.pack(pady=(5, 10), padx=20, anchor="w")
        
        # Information section
        info_section = ctk.CTkFrame(settings_frame, fg_color="#31314A", corner_radius=10)
        info_section.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(
            info_section,
            text="Information",
            font=self.normal_font,
            text_color="#FFFFFF"
        ).pack(pady=(10, 5))
        
        ctk.CTkLabel(
            info_section,
            text="Version: 1.2.7\nAny Command Server",
            font=self.small_font,
            text_color="#AAB2BD",
            justify="center"
        ).pack(pady=(0, 10))
        
        # Buttons frame
        buttons_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        buttons_frame.pack(fill="x", padx=25, pady=(0, 15))
        
        # Close button
        close_button = ctk.CTkButton(
            buttons_frame,
            text="Close",
            command=settings_window.destroy,
            font=self.normal_font,
            height=36,
            corner_radius=8,
            fg_color="#3498db",
            hover_color="#2980b9",
        )
        close_button.pack(fill="x")

    def _update_auto_hide_setting(self, enabled):
        """Update the auto-hide setting"""
        self.preferences['auto_hide'] = enabled
        self.save_preferences()
        mode_text = "enabled" if enabled else "disabled"
        self.show_notification("Settings", f"Auto-hide confirmation {mode_text}")

    def get_autostart_setting(self):
        """Get autostart setting from Windows registry"""
        try:
            import winreg
            registry_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                         "Software\\Microsoft\\Windows\\CurrentVersion\\Run", 
                                         0, winreg.KEY_READ)
            try:
                value, _ = winreg.QueryValueEx(registry_key, "AnyCommandServer")
                winreg.CloseKey(registry_key)
                return True
            except FileNotFoundError:
                winreg.CloseKey(registry_key)
                return False
        except Exception as e:
            logging.error(f"Error checking autostart setting: {e}")
            return False

    def set_autostart_setting(self, enabled):
        """Set autostart setting in Windows registry"""
        try:
            import winreg
            registry_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                         "Software\\Microsoft\\Windows\\CurrentVersion\\Run", 
                                         0, winreg.KEY_ALL_ACCESS)
            
            if enabled:
                # Add to startup
                if getattr(sys, 'frozen', False):
                    # Running as compiled executable
                    executable_path = sys.executable
                else:
                    # Running as script - use python with script path
                    executable_path = f'"{sys.executable}" "{os.path.abspath(__file__)}"'
                
                winreg.SetValueEx(registry_key, "AnyCommandServer", 0, winreg.REG_SZ, executable_path)
                logging.info(f"Added to startup: {executable_path}")
                self.show_notification("Autostart", "Server will now start with Windows")
            else:
                # Remove from startup
                try:
                    winreg.DeleteValue(registry_key, "AnyCommandServer")
                    logging.info("Removed from startup")
                    self.show_notification("Autostart", "Server will no longer start with Windows")
                except FileNotFoundError:
                    logging.info("Autostart entry not found (already removed)")
            
            winreg.CloseKey(registry_key)
            
        except Exception as e:
            logging.error(f"Error setting autostart: {e}")
            self.show_notification("Error", f"Failed to modify autostart setting: {str(e)}")

    def on_tray_click(self, icon, button, time=0):
        """Handle tray icon clicks"""
        # For left click (button=1), show the window
        if button == 1:
            self.show_from_tray()

    def create_icon(self, text, color, size=(20, 20)):
        """Create a simple icon using PIL Image"""
        try:
            # Create a simple colored circle as an icon
            from PIL import Image, ImageDraw
            
            # Create a square image with transparency
            image = Image.new('RGBA', size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            
            # Parse color if it's a hex string
            if isinstance(color, str) and color.startswith('#'):
                color = tuple(int(color[i:i+2], 16) for i in (1, 3, 5))
            elif isinstance(color, str):
                # Default colors for common color names
                color_map = {
                    '#7EB6FF': (126, 182, 255),
                    '#FFD166': (255, 209, 102),
                    '#4CAF50': (76, 175, 80)
                }
                color = color_map.get(color, (100, 100, 100))
            
            # Draw a simple circle
            margin = 2
            draw.ellipse([margin, margin, size[0]-margin, size[1]-margin], fill=color)
            
            # Convert to CTkImage
            return ctk.CTkImage(light_image=image, dark_image=image, size=size)
        except Exception as e:
            logging.error(f"Error creating icon: {e}")
            # Return None if icon creation fails
            return None

    def create_gradient_button(self, parent, text, command, gradient=None, icon=None):
        """Create a button with a more professional look"""
        button_frame = ctk.CTkFrame(parent, fg_color="transparent")
        
        # More professional color schemes
        if gradient is None:
            gradient = ["#2C3E50", "#4CA1AF"]  # Default blue-gray gradient
        
        # Professional color palettes
        if text == "How to Connect":
            gradient = ["#3867d6", "#4b7bec"]  # Professional blue
        elif text == "Open Transfer Folder":
            gradient = ["#20bf6b", "#26de81"]  # Professional green
        elif text == "Settings":
            gradient = ["#f39c12", "#e67e22"]  # Professional orange
        elif text == "Minimize to Tray":
            gradient = ["#4b6584", "#778ca3"]  # Professional slate
        elif text == "Exit":
            gradient = ["#eb3b5a", "#fc5c65"]  # Professional red
        elif text == "Help":
            gradient = ["#8e44ad", "#9b59b6"]  # Professional purple
        
        button = ctk.CTkButton(
            button_frame,
            text=text,  # No icon, just clean text
            command=command,
            font=self.normal_font,
            height=36,  # Slightly smaller height for professional look
            corner_radius=6,  # Less rounded corners for professional look
            border_width=0,
            fg_color=gradient[0],
            hover_color=gradient[1],
            text_color="#FFFFFF",
        )
        button.pack(fill="both", expand=True)
        
        return button_frame

    def center_window(self):
        """Center the window on the screen"""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')

    def open_transfer_directory(self):
        """Open the directory where transferred files are stored"""
        try:
            # Get the transfer directory path
            transfer_dir = self._get_transfer_directory()
            
            # Open the directory using the default file explorer
            if os.path.exists(transfer_dir):
                # Use the appropriate command based on the OS
                if os.name == 'nt':  # Windows
                    os.startfile(transfer_dir)
                elif os.name == 'posix':  # macOS and Linux
                    if sys.platform == 'darwin':  # macOS
                        subprocess.call(['open', transfer_dir])
                    else:  # Linux
                        subprocess.call(['xdg-open', transfer_dir])
            
                self.show_notification("Transfer Folder", "Opened transfer folder")
            else:
                self.show_notification("Transfer Folder", "Transfer folder not found")
        except Exception as e:
            logging.error(f"Error opening transfer directory: {e}")
            self.show_notification("Error", f"Error opening folder: {str(e)}")

    def _get_transfer_directory(self):
        """Get the transfer directory from config or use default"""
        try:
            config = configparser.ConfigParser()
            config_path = os.path.join(os.path.expanduser("~"), ".anycommand", "config.ini")
            
            if os.path.exists(config_path):
                config.read(config_path)
                if 'Paths' in config and 'transfer_dir' in config['Paths']:
                    return config['Paths']['transfer_dir']
            
            # Default: create 'AnyCommand Transfers' in user's Documents folder
            docs_path = os.path.join(os.path.expanduser("~"), "Documents")
            return os.path.join(docs_path, "AnyCommand Transfers")
        except Exception as e:
            logging.error(f"Error getting transfer directory: {e}")
            return os.path.join(os.path.expanduser("~"), "AnyCommand Transfers")

    def show_instructions(self):
        """Show connection instructions in a dialog"""
        instructions_window = ctk.CTkToplevel(self)
        instructions_window.title("How to Connect")
        instructions_window.geometry("400x300")
        instructions_window.resizable(False, False)
        instructions_window.focus_set()
        
        # Make it modal
        instructions_window.grab_set()
        instructions_window.transient(self)
        
        # Center the window
        instructions_window.update_idletasks()
        width = instructions_window.winfo_width()
        height = instructions_window.winfo_height()
        x = self.winfo_rootx() + (self.winfo_width() // 2) - (width // 2)
        y = self.winfo_rooty() + (self.winfo_height() // 2) - (height // 2)
        instructions_window.geometry(f"{width}x{height}+{x}+{y}")
        
        # Content frame
        content_frame = ctk.CTkFrame(
            instructions_window,
            fg_color="#262639",
            corner_radius=15,
        )
        content_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Title
        ctk.CTkLabel(
            content_frame,
            text="HOW TO CONNECT",
            font=self.heading_font,
            text_color="#7EB6FF"
        ).pack(pady=(15, 20))
        
        # Instructions content
        instructions_text = (
            "1. Install 'Any Command' app on your phone\n\n"
            "2. Make sure your phone and PC are on the same network\n\n"
            "3. Enter the IP address and PIN shown in the main window\n\n"
            "4. If connection fails, try another IP address\n\n"
            "5. Press Ctrl+Alt+A to show the main window anytime"
        )
        
        instructions_label = ctk.CTkLabel(
            content_frame,
            text=instructions_text,
            font=self.normal_font,
            justify="left",
            padx=25
        )
        instructions_label.pack(pady=(0, 15))
        
        # Close button
        close_button = ctk.CTkButton(
            content_frame,
            text="Close",
            command=instructions_window.destroy,
            font=self.normal_font,
            height=36,
            corner_radius=8,
            fg_color="#3498db",
            hover_color="#2980b9",
        )
        close_button.pack(pady=(0, 15), padx=50)

    def open_help_page(self):
        """Open the help page in the default web browser"""
        try:
            help_url = "https://www.reddit.com/r/AnyCommand/comments/1jy06cm/having_trouble_connecting_read_this_first/"
            webbrowser.open(help_url)
            self.show_notification("Help", "Opening help page in browser")
        except Exception as e:
            logging.error(f"Error opening help page: {e}")
            self.show_notification("Error", f"Error opening help page: {str(e)}")

    def on_pin_mode_changed(self):
        """Handle change in PIN mode"""
        self.update_pin_mode_ui()
        
        # Auto-save the preference when PIN mode is toggled
        try:
            use_random_pin = self.pin_mode_var.get()
            self.preferences['use_random_pin'] = use_random_pin
            self.save_preferences()
            
            # Show notification about the change
            mode_text = "Random PIN" if use_random_pin else "Custom PIN"
            self.show_notification("PIN Mode Changed", f"PIN mode set to: {mode_text}\nRestart server to apply changes")
            
        except Exception as e:
            logging.error(f"Error auto-saving PIN mode: {e}")

    def update_pin_mode_ui(self):
        """Update UI elements based on PIN mode"""
        if not hasattr(self, 'pin_mode_var') or not self.pin_mode_var:
            logging.warning("update_pin_mode_ui called but pin_mode_var not available")
            return
            
        use_random_pin = self.pin_mode_var.get()
        logging.info(f"Updating PIN mode UI for: {'Random' if use_random_pin else 'Custom'}")
        
        if use_random_pin:
            # Random PIN mode
            if hasattr(self, 'pin_mode_info') and self.pin_mode_info:
                self.pin_mode_info.configure(
                    text="Random PIN mode: Server generates a new PIN each restart (More Secure)"
                )
            if hasattr(self, 'custom_pin_frame') and self.custom_pin_frame:
                self.custom_pin_frame.pack_forget()  # Hide custom PIN input
                logging.info("Hid custom PIN frame")
        else:
            # Custom PIN mode
            if hasattr(self, 'pin_mode_info') and self.pin_mode_info:
                self.pin_mode_info.configure(
                    text="Custom PIN mode: Use your own PIN that persists across restarts (Less Secure)"
                )
            if hasattr(self, 'custom_pin_frame') and self.custom_pin_frame:
                self.custom_pin_frame.pack(fill="x", pady=(10, 0))  # Show custom PIN input
                logging.info("Showed custom PIN frame")

    def on_custom_pin_changed(self, event):
        """Handle change in custom PIN"""
        if not hasattr(self, 'custom_pin_entry') or not self.custom_pin_entry:
            return
            
        pin_text = self.custom_pin_entry.get()
        
        # Validate PIN format (only digits, max 6 characters)
        if pin_text and not pin_text.isdigit():
            # Remove non-digit characters
            clean_pin = ''.join(filter(str.isdigit, pin_text))
            self.custom_pin_entry.delete(0, ctk.END)
            self.custom_pin_entry.insert(0, clean_pin)
            pin_text = clean_pin
            
        # Limit to 6 digits
        if len(pin_text) > 6:
            self.custom_pin_entry.delete(6, ctk.END)
            pin_text = pin_text[:6]
        
        # Update button color based on PIN validity
        if hasattr(self, 'save_pin_button') and self.save_pin_button:
            if len(pin_text) == 6 and pin_text.isdigit():
                self.save_pin_button.configure(fg_color="#28a745", hover_color="#218838")
            else:
                self.save_pin_button.configure(fg_color="#6c757d", hover_color="#545b62")

    def save_pin_configuration(self):
        """Save the current PIN configuration"""
        try:
            if not hasattr(self, 'pin_mode_var') or not self.pin_mode_var:
                return
                
            use_random_pin = self.pin_mode_var.get()
            custom_pin = self.custom_pin_entry.get() if hasattr(self, 'custom_pin_entry') and self.custom_pin_entry else ''
            
            # Validate custom PIN if not using random
            if not use_random_pin:
                if len(custom_pin) != 6 or not custom_pin.isdigit():
                    self.show_notification("Invalid PIN", "Custom PIN must be exactly 6 digits")
                    return
            
            # Update preferences
            self.preferences['use_random_pin'] = use_random_pin
            self.preferences['custom_pin'] = custom_pin if not use_random_pin else ''
            
            # Save to file
            self.save_preferences()
            
            # Show success message
            mode_text = "Random PIN" if use_random_pin else f"Custom PIN ({custom_pin})"
            self.show_notification("PIN Configuration Saved", f"Mode: {mode_text}\nRestart server to apply changes")
            
            logging.info(f"PIN configuration saved: use_random_pin={use_random_pin}, custom_pin={'***' if custom_pin else 'None'}")
            
        except Exception as e:
            logging.error(f"Error saving PIN configuration: {e}")
            self.show_notification("Error", f"Failed to save PIN configuration: {str(e)}")

    def apply_pin_configuration_to_ui(self):
        """Apply PIN configuration to UI after elements are created"""
        # Get PIN configuration from preferences
        use_random_pin = self.preferences.get('use_random_pin', True)
        custom_pin = self.preferences.get('custom_pin', '')
        
        logging.info(f"Applying PIN configuration to UI: use_random_pin={use_random_pin}, custom_pin={'***' if custom_pin else 'None'}")
        
        # Set UI values if elements exist
        if hasattr(self, 'pin_mode_var') and self.pin_mode_var:
            self.pin_mode_var.set(use_random_pin)
            logging.info(f"Set pin_mode_var to {use_random_pin}")
        
        # Set custom PIN value regardless of mode (for when user switches modes)
        if hasattr(self, 'custom_pin_entry') and self.custom_pin_entry and custom_pin:
            self.custom_pin_entry.delete(0, ctk.END)
            self.custom_pin_entry.insert(0, custom_pin)
            logging.info(f"Set custom PIN entry to saved value")
        
        # Update UI based on PIN mode (this will show/hide custom PIN fields)
        if hasattr(self, 'update_pin_mode_ui'):
            self.update_pin_mode_ui()
            logging.info(f"Updated PIN mode UI for mode: {'Random' if use_random_pin else 'Custom'}")

if __name__ == "__main__":
    # Set up logging
    log_dir = os.path.join(os.path.expanduser('~'), '.anycommand')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'server.log')
    
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    app = None  # Initialize app variable
    try:
        ctk.set_appearance_mode("dark")
        app = ServerGUI()
        if hasattr(app, 'mutex') and app.mutex:  # Only run mainloop if we have the mutex
            app.mainloop()
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        # Show error message to user
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()  # Hide the root window
            messagebox.showerror("Error", f"Failed to start Any Command Server:\n\n{str(e)}\n\nPlease check the log file for more details.")
            root.destroy()
        except:
            pass  # If even basic tkinter fails, just continue
        
        if app and hasattr(app, 'mutex') and app.mutex:
            win32api.CloseHandle(app.mutex)
        sys.exit(1) 