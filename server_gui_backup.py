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
import webbrowser

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
            self.show_already_running_dialog()
            return

        super().__init__()
        
        # Load preferences
        self.load_preferences()
        
        # Apply a modern theme
        self.configure(fg_color="#1E1E2E")  # Dark background with a hint of blue
        
        # Configure window
        self.title("Any Command Server")
        self.geometry("400x450")  # Reduced from whatever the previous size was
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
        self.minsize(380, 400)    # Set minimum size to prevent too small window
        
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
            logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.ico')
            if os.path.exists(logo_path):
                logo_image = ctk.CTkImage(Image.open(logo_path), size=(48, 48))
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
        network_icon = self.create_icon("\uf1eb", "#7EB6FF", icon_size)  # WiFi icon
        key_icon = self.create_icon("\uf084", "#FFD166", icon_size)      # Key icon
        status_icon = self.create_icon("\uf058", "#4CAF50", icon_size)   # Check icon
        
        # IP Address
        ip_row = ctk.CTkFrame(status_container, fg_color="transparent")
        ip_row.pack(fill="x", pady=(8, 4))  # Reduced padding
        
        ctk.CTkLabel(ip_row, image=network_icon, text="").pack(side="left", padx=(0, 15))
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
        
        ctk.CTkLabel(pin_row, image=key_icon, text="").pack(side="left", padx=(0, 15))
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
        
        ctk.CTkLabel(status_row, image=status_icon, text="").pack(side="left", padx=(0, 15))
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
        
        # Online Help button (new)
        online_help_button = self.create_gradient_button(
            second_row,
            "Help",
            self.open_help_page,
            gradient=["#8e44ad", "#9b59b6"],  # Professional purple
        )
        online_help_button.pack(side="left", fill="x", expand=True, padx=(0, 4))
        
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

    def load_preferences(self):
        """Load user preferences from file"""
        self.preferences = {}
        try:
            config = configparser.ConfigParser()
            config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'preferences.ini')
            config.read(config_file)
            if 'Preferences' in config:
                self.preferences = dict(config['Preferences'])
                # Convert string 'True'/'False' to boolean
                if 'auto_hide' in self.preferences:
                    self.preferences['auto_hide'] = config['Preferences'].getboolean('auto_hide')
        except:
            pass

    def save_preferences(self):
        """Save user preferences to file"""
        try:
            config = configparser.ConfigParser()
            config['Preferences'] = {
                'auto_hide': str(self.preferences.get('auto_hide', False))
            }
            config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'preferences.ini')
            with open(config_file, 'w') as f:
                config.write(f)
        except:
            pass

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
            self.server = RemoteServer()
            
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
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            toaster.show_toast(title, message, duration=3, threaded=True)
        except:
            # Fallback if win10toast is not installed
            pass

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
        # This is a simple implementation - you can expand it as needed
        settings_window = ctk.CTkToplevel(self)
        settings_window.title("Settings")
        settings_window.geometry("400x300")
        settings_window.resizable(False, False)
        settings_window.focus_force()
        
        # Add a label
        ctk.CTkLabel(
            settings_window, 
            text="Settings", 
            font=("Arial", 18, "bold")
        ).pack(pady=20)
        
        # Add some example settings
        autostart_var = ctk.BooleanVar(value=self.get_autostart_setting())
        ctk.CTkCheckBox(
            settings_window,
            text="Start with Windows",
            variable=autostart_var,
            command=lambda: self.set_autostart_setting(autostart_var.get())
        ).pack(pady=10, padx=20, anchor="w")
        
        # Close button
        ctk.CTkButton(
            settings_window,
            text="Close",
            command=settings_window.destroy
        ).pack(pady=20)

    def get_autostart_setting(self):
        """Get autostart setting from registry or config"""
        # Placeholder - implement actual logic
        return False

    def set_autostart_setting(self, enabled):
        """Set autostart setting in registry or config"""
        # Placeholder - implement actual logic
        pass

    def on_tray_click(self, icon, button, time=0):
        """Handle tray icon clicks"""
        # For left click (button=1), show the window
        if button == 1:
            self.show_from_tray()

    def create_icon(self, text, color, size=(20, 20)):
        """Create a FontAwesome icon"""
        try:
            # Load FontAwesome if available
            from tkinter import font
            if "FontAwesome" not in font.families():
                return None
            
            icon = ctk.CTkCanvas(self, width=size[0], height=size[1], highlightthickness=0)
            icon.create_text(size[0]/2, size[1]/2, text=text, fill=color, font=("FontAwesome", 16))
            return icon
        except:
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
            
                self.show_notification("Opened transfer folder")
            else:
                self.show_notification("Transfer folder not found", "error")
        except Exception as e:
            logging.error(f"Error opening transfer directory: {e}")
            self.show_notification(f"Error opening folder: {str(e)}", "error")

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
            self.show_notification("Opening help page in browser")
        except Exception as e:
            logging.error(f"Error opening help page: {e}")
            self.show_notification(f"Error opening help page: {str(e)}", "error")

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