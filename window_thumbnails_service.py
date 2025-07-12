import win32gui
import win32con
import win32ui
import win32process
import win32api
import psutil
import threading
import socket
import json
import time
import io
import base64
from PIL import Image, ImageGrab
import os
import ctypes
from ctypes import wintypes, byref

# Add these constants for icon extraction
SHGFI_ICON = 0x000000100
SHGFI_SMALLICON = 0x000000001
SHGFI_LARGEICON = 0x000000000
SHIL_JUMBO = 0x4
SHIL_EXTRALARGE = 0x2

class WindowThumbnailsService:
    def __init__(self, port=8083):
        self.port = port
        self.server_socket = None
        self.is_running = False
        self.clients = []
        self.lock = threading.Lock()
        self.update_interval = 2.0  # Update thumbnails every 2 seconds
        self.icon_cache = {}  # Cache for app icons
        
    def start(self):
        if self.is_running:
            return
            
        self.is_running = True
        self.server_thread = threading.Thread(target=self._run_server)
        self.server_thread.daemon = True
        self.server_thread.start()
        
    def stop(self):
        self.is_running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        with self.lock:
            for client in self.clients:
                try:
                    client.close()
                except:
                    pass
            self.clients.clear()
    
    def _run_server(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('0.0.0.0', self.port))
            self.server_socket.listen(5)
            print(f"Window thumbnails service running on port {self.port}")
            
            while self.is_running:
                try:
                    client, addr = self.server_socket.accept()
                    print(f"New window thumbnails client connected: {addr}")
                    client_thread = threading.Thread(
                        target=self._handle_client,
                        args=(client,)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                except:
                    if not self.is_running:
                        break
                    time.sleep(0.1)
        except Exception as e:
            print(f"Error in window thumbnails server: {e}")
        finally:
            if self.server_socket:
                self.server_socket.close()
    
    def _handle_client(self, client):
        try:
            with self.lock:
                self.clients.append(client)
            
            # Send initial window list
            self._send_window_list(client)
            
            # Start thumbnail update thread
            update_thread = threading.Thread(
                target=self._update_thumbnails,
                args=(client,)
            )
            update_thread.daemon = True
            update_thread.start()
            
            # Handle client commands
            while self.is_running:
                try:
                    data = client.recv(4096)
                    if not data:
                        break
                    
                    command = json.loads(data.decode('utf-8'))
                    self._handle_command(command)
                except Exception as e:
                    print(f"Error handling client command: {e}")
                    break
        except Exception as e:
            print(f"Error in client handler: {e}")
        finally:
            with self.lock:
                if client in self.clients:
                    self.clients.remove(client)
            try:
                client.close()
            except:
                pass
    
    def _update_thumbnails(self, client):
        """Periodically send updated thumbnails to the client"""
        while self.is_running and client in self.clients:
            try:
                self._send_window_list(client)
                time.sleep(self.update_interval)
            except Exception as e:
                print(f"Error updating thumbnails: {e}")
                break
    
    def _send_window_list(self, client):
        """Send list of windows with thumbnails to client"""
        windows = self._get_windows()
        try:
            client.sendall(json.dumps(windows).encode('utf-8') + b'\n')
        except Exception as e:
            print(f"Error sending window list: {e}")
    
    def _get_windows(self):
        """Get all visible windows with thumbnails"""
        windows = []
        print(f"Fetching window list...")
        
        def enum_windows_callback(hwnd, _):
            # Only include windows that are visible and have a title
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
                try:
                    # Get window info
                    title = win32gui.GetWindowText(hwnd)
                    print(f"Processing window: {title}")
                    
                    # Skip windows with empty titles or that are tool windows
                    if not title or win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE) & win32con.WS_EX_TOOLWINDOW:
                        return True
                    
                    # Skip windows that have zero size (not visible to user)
                    rect = win32gui.GetWindowRect(hwnd)
                    width = rect[2] - rect[0]
                    height = rect[3] - rect[1]
                    if width <= 0 or height <= 0:
                        print(f"Skipping zero-size window: {title}")
                        return True
                    
                    # Check if window is minimized
                    is_minimized = win32gui.IsIconic(hwnd)
                    
                    # Check if window is maximized
                    placement = win32gui.GetWindowPlacement(hwnd)
                    is_maximized = placement[1] == win32con.SW_SHOWMAXIMIZED
                    
                    # Skip windows that are cloaked (Windows 10+ feature)
                    try:
                        DWMWA_CLOAKED = 14
                        cloaked = ctypes.c_int(0)
                        ctypes.windll.dwmapi.DwmGetWindowAttribute(
                            hwnd, DWMWA_CLOAKED, 
                            ctypes.byref(cloaked), ctypes.sizeof(cloaked)
                        )
                        if cloaked.value:
                            print(f"Skipping cloaked window: {title}")
                            return True
                    except:
                        pass  # DWM API might not be available
                    
                    # Get process info
                    try:
                        _, pid = win32process.GetWindowThreadProcessId(hwnd)
                        process = psutil.Process(pid)
                        process_name = process.name()
                        process_path = process.exe()
                    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                        print(f"Error getting process info: {e}")
                        process_name = "Unknown"
                        process_path = ""
                    
                    # Get window rect
                    rect = win32gui.GetWindowRect(hwnd)
                    
                    # Skip tiny windows
                    width = rect[2] - rect[0]
                    height = rect[3] - rect[1]
                    if width < 50 or height < 50 and not is_minimized:  # Don't skip minimized windows based on size
                        return True
                    
                    # Get thumbnail (empty for minimized windows)
                    thumb_width = 320
                    thumb_height = 180
                    thumbnail = "" if is_minimized else self._capture_window_thumbnail(hwnd, thumb_width, thumb_height)
                    
                    # Get application icon
                    icon = self._get_app_icon(process_path, pid)
                    
                    # Add window info
                    category = self._categorize_window(process_name, title)
                    print(f"Added window: {title} ({process_name}) - Category: {category}, Minimized: {is_minimized}")
                    
                    windows.append({
                        'hwnd': hwnd,
                        'title': title,
                        'process': process_name,
                        'process_path': process_path,
                        'rect': {
                            'left': rect[0],
                            'top': rect[1],
                            'right': rect[2],
                            'bottom': rect[3],
                            'width': width,
                            'height': height,
                        },
                        'thumbnail': thumbnail,
                        'icon': icon,
                        'category': category,
                        'is_minimized': 1 if is_minimized else 0,
                        'is_maximized': 1 if is_maximized else 0,  # Add maximized state
                    })
                except Exception as e:
                    print(f"Error processing window {win32gui.GetWindowText(hwnd)}: {e}")
                
            return True
        
        try:
            win32gui.EnumWindows(enum_windows_callback, None)
            print(f"Found {len(windows)} windows")
            return windows
        except Exception as e:
            print(f"Error enumerating windows: {e}")
            return []
    
    def _capture_window_thumbnail(self, hwnd, width, height):
        """Capture a thumbnail of the window"""
        try:
            # Limit thumbnail size
            max_size = 200
            scale = min(1.0, max_size / max(width, height))
            thumb_width = int(width * scale)
            thumb_height = int(height * scale)
            
            # Try to capture the window
            hwndDC = win32gui.GetWindowDC(hwnd)
            mfcDC = win32ui.CreateDCFromHandle(hwndDC)
            saveDC = mfcDC.CreateCompatibleDC()
            saveBitMap = win32ui.CreateBitmap()
            saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
            saveDC.SelectObject(saveBitMap)
            
            # Copy window content
            result = saveDC.BitBlt((0, 0), (width, height), mfcDC, (0, 0), win32con.SRCCOPY)
            
            # Convert to PIL Image
            bmpinfo = saveBitMap.GetInfo()
            bmpstr = saveBitMap.GetBitmapBits(True)
            img = Image.frombuffer(
                'RGB',
                (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                bmpstr, 'raw', 'BGRX', 0, 1)
            
            # Resize thumbnail
            img = img.resize((thumb_width, thumb_height), Image.LANCZOS)
            
            # Convert to base64 for sending
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=70)
            img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            # Clean up
            win32gui.ReleaseDC(hwnd, hwndDC)
            mfcDC.DeleteDC()
            saveDC.DeleteDC()
            win32gui.DeleteObject(saveBitMap.GetHandle())
            
            return img_str
        except Exception as e:
            print(f"Error capturing window thumbnail: {e}")
            return ""
    
    def _get_app_icon(self, process_path, pid):
        """Extract application icon and convert to base64"""
        # Check cache first
        if process_path in self.icon_cache:
            return self.icon_cache[process_path]
            
        try:
            if not process_path or not os.path.exists(process_path):
                return ""
                
            # Use SHGetFileInfo to get the icon
            shell32 = ctypes.windll.shell32
            
            shinfo = ctypes.create_string_buffer(ctypes.sizeof(wintypes.SHFILEINFOW))
            shinfo_ptr = ctypes.cast(shinfo, ctypes.POINTER(wintypes.SHFILEINFOW))
            
            # Get large icon
            res = shell32.SHGetFileInfoW(
                process_path, 
                0, 
                byref(shinfo_ptr.contents), 
                ctypes.sizeof(wintypes.SHFILEINFOW), 
                SHGFI_ICON | SHGFI_LARGEICON
            )
            
            if not res:
                return ""
                
            hicon = shinfo_ptr.contents.hIcon
            
            # Convert icon to bitmap
            ico_x = win32api.GetSystemMetrics(win32con.SM_CXICON)
            ico_y = win32api.GetSystemMetrics(win32con.SM_CYICON)
            
            hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
            hbmp = win32ui.CreateBitmap()
            hbmp.CreateCompatibleBitmap(hdc, ico_x, ico_y)
            hdc = hdc.CreateCompatibleDC()
            
            hdc.SelectObject(hbmp)
            hdc.DrawIcon((0, 0), hicon)
            
            # Convert to PIL image
            bmpstr = hbmp.GetBitmapBits(True)
            img = Image.frombuffer(
                'RGBA', 
                (ico_x, ico_y),
                bmpstr, 
                'raw', 
                'BGRA', 
                0, 
                1
            )
            
            # Clean up
            win32gui.DestroyIcon(hicon)
            hdc.DeleteDC()
            win32gui.ReleaseDC(0, win32gui.GetDC(0))
            
            # Convert to base64
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            icon_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            # Cache the result
            self.icon_cache[process_path] = icon_str
            
            return icon_str
        except Exception as e:
            print(f"Error extracting icon: {e}")
            return ""
    
    def _categorize_window(self, process_name, title):
        """Categorize window based on process name and title"""
        process_lower = process_name.lower()
        title_lower = title.lower()
        
        # Browsers
        browsers = ['chrome.exe', 'firefox.exe', 'msedge.exe', 'iexplore.exe', 'opera.exe', 'brave.exe']
        if any(browser in process_lower for browser in browsers):
            return 'Browsers'
            
        # Media
        media_apps = ['vlc.exe', 'spotify.exe', 'wmplayer.exe', 'musicbee.exe', 'itunes.exe', 'obs64.exe', 'obs.exe']
        media_keywords = ['player', 'video', 'music', 'media', 'photo', 'image', 'camera']
        if any(app in process_lower for app in media_apps) or any(keyword in title_lower for keyword in media_keywords):
            return 'Media'
            
        # Documents
        document_apps = ['winword.exe', 'excel.exe', 'powerpnt.exe', 'acrobat.exe', 'notepad.exe', 'wordpad.exe']
        document_keywords = ['document', 'word', 'excel', 'powerpoint', 'pdf', 'text', 'note']
        if any(app in process_lower for app in document_apps) or any(keyword in title_lower for keyword in document_keywords):
            return 'Documents'
            
        # System
        system_apps = ['explorer.exe', 'taskmgr.exe', 'control.exe', 'cmd.exe', 'powershell.exe', 'regedit.exe']
        system_keywords = ['control panel', 'settings', 'system', 'task manager', 'file explorer']
        if any(app in process_lower for app in system_apps) or any(keyword in title_lower for keyword in system_keywords):
            return 'System'
            
        # Utilities
        utility_apps = ['calculator.exe', 'mspaint.exe', 'snippingtool.exe', 'notepad.exe']
        utility_keywords = ['calculator', 'paint', 'tool', 'utility']
        if any(app in process_lower for app in utility_apps) or any(keyword in title_lower for keyword in utility_keywords):
            return 'Utilities'
            
        # Default
        return 'Other'
    
    def _handle_command(self, command):
        """Handle commands from the client"""
        try:
            action = command.get('action')
            hwnd = command.get('hwnd')
            
            if not hwnd:
                return
                
            if action == 'activate':
                # First restore the window if it's minimized
                if win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                
                # Try to force the window to the foreground
                # This is a more aggressive approach that works in most cases
                try:
                    # Get the foreground window's thread
                    foreground_hwnd = win32gui.GetForegroundWindow()
                    foreground_thread = win32process.GetWindowThreadProcessId(foreground_hwnd)[0]
                    
                    # Get the target window's thread
                    target_thread = win32process.GetWindowThreadProcessId(hwnd)[0]
                    
                    # Attach the threads to bypass Windows security restrictions
                    win32process.AttachThreadInput(target_thread, foreground_thread, True)
                    
                    # Set our window to the foreground
                    win32gui.SetForegroundWindow(hwnd)
                    win32gui.BringWindowToTop(hwnd)
                    
                    # Detach the threads
                    win32process.AttachThreadInput(target_thread, foreground_thread, False)
                    
                    # Flash the window to draw attention to it
                    win32gui.FlashWindow(hwnd, True)
                except Exception as e:
                    print(f"Error bringing window to front: {e}")
                    # Fallback to simpler methods
                    win32gui.SetActiveWindow(hwnd)
                    win32gui.FlashWindow(hwnd, True)
                
            elif action == 'close':
                # Close window
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                
            elif action == 'minimize':
                # Minimize window
                win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                
            elif action == 'maximize':
                # Check if window is already maximized
                placement = win32gui.GetWindowPlacement(hwnd)
                is_maximized = placement[1] == win32con.SW_SHOWMAXIMIZED
                
                # First restore if minimized
                if win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                # Toggle between maximized and restored states
                elif is_maximized:
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                else:
                    win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
                
                # Activate the window without changing z-order
                win32gui.SetActiveWindow(hwnd)
        except Exception as e:
            print(f"Error handling command: {e}") 