import io
import time
import threading
import socket
import numpy as np
from PIL import ImageGrab, Image, ImageDraw
import win32gui
import win32con

class ScreenShareService:
    def __init__(self, port=8081):
        self.port = port
        self.is_running = False
        self.server_socket = None
        self.clients = []
        self.stream_clients = []  # Separate list for stream clients
        self.lock = threading.Lock()
        self.quality = 75     # Slightly increase JPEG quality from 70 to 75
        self.fps = 20         # Increase FPS from 15 to 20 for better responsiveness
        self.scale = 0.9      # Increase scale from 0.85 to 0.9 for better quality
        self.show_cursor = True
        self.is_viewing = False  # Track if screen is being viewed
        
        # Connection health monitoring
        self.client_health = {}  # Track client connection health
        self.max_connection_errors = 3
        self.connection_check_interval = 5.0  # seconds
        
        # Performance optimization
        self.frame_skip_threshold = 0.033  # Skip frames if we're falling behind (30fps)
        self.last_successful_frame = time.time()
        
        # Error recovery
        self.capture_errors = 0
        self.max_capture_errors = 10
        self.error_recovery_delay = 1.0
    
        # Resource management
        self.max_clients = 3  # Limit concurrent clients
        self.frame_buffer_size = 2  # Limit frame buffer to reduce memory usage
    
    def start(self):
        if self.is_running:
            return
            
        self.is_running = True
        self.server_thread = threading.Thread(target=self._run_server)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        # Start capture thread immediately (it will wait for clients)
        self.capture_thread = threading.Thread(target=self._capture_screen)
        self.capture_thread.daemon = True
        self.capture_thread.start()
        
        # Start connection health monitor
        self.health_thread = threading.Thread(target=self._monitor_connection_health)
        self.health_thread.daemon = True
        self.health_thread.start()
        
        print(f"Screen sharing server started on port {self.port}")
        print("Screen capture thread started (waiting for clients)")
    
    def set_viewing_status(self, is_viewing):
        """Set whether client is currently viewing the screen"""
        old_status = self.is_viewing
        self.is_viewing = is_viewing
        
        if is_viewing and not old_status:
            # Reset error counters when starting
            self.capture_errors = 0
            self.last_successful_frame = time.time()
            print("Screen viewing enabled")
        elif not is_viewing and old_status:
            print("Screen viewing disabled")
    
    def stop(self):
        self.is_running = False
        self.is_viewing = False
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
            for client in self.stream_clients:
                try:
                    client.close()
                except:
                    pass
            self.clients = []
            self.stream_clients = []
            self.client_health = {}
    
    def _monitor_connection_health(self):
        """Monitor client connection health and clean up dead connections"""
        while self.is_running:
            try:
                time.sleep(self.connection_check_interval)
                
                with self.lock:
                    # Check stream clients
                    clients_to_remove = []
                    for client in self.stream_clients:
                        client_id = id(client)
                        
                        # Track connection errors
                        if client_id not in self.client_health:
                            self.client_health[client_id] = {'errors': 0, 'last_success': time.time()}
                        
                        # Test connection with a small keepalive
                        try:
                            # Send a small test frame to check connection
                            test_data = b'--ping\r\n\r\n'
                            client.send(test_data)
                            self.client_health[client_id]['last_success'] = time.time()
                            self.client_health[client_id]['errors'] = 0
                        except:
                            self.client_health[client_id]['errors'] += 1
                            
                            # Remove client if too many errors
                            if self.client_health[client_id]['errors'] >= self.max_connection_errors:
                                clients_to_remove.append(client)
                                print(f"Removing unhealthy client after {self.client_health[client_id]['errors']} errors")
                    
                    # Clean up unhealthy clients
                    for client in clients_to_remove:
                        self._remove_client(client)
                        
            except Exception as e:
                print(f"Error in connection health monitor: {e}")
    
    def _remove_client(self, client):
        """Safely remove a client and clean up resources"""
        try:
            if client in self.stream_clients:
                self.stream_clients.remove(client)
            if client in self.clients:
                self.clients.remove(client)
            
            client_id = id(client)
            if client_id in self.client_health:
                del self.client_health[client_id]
            
            client.close()
        except:
            pass
    
    def _run_server(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.settimeout(1.0)  # Add timeout to prevent blocking
            self.server_socket.bind(('0.0.0.0', self.port))
            self.server_socket.listen(5)
            
            while self.is_running:
                try:
                    client, addr = self.server_socket.accept()
                    print(f"New screen share client connected from {addr}")
                    
                    with self.lock:
                        if len(self.stream_clients) >= self.max_clients:
                            print(f"Maximum clients ({self.max_clients}) reached, rejecting new connection")
                            client.close()
                            return
                        self.clients.append(client)
                    
                    # Start a thread to handle this client
                    client_thread = threading.Thread(target=self._handle_client, args=(client,))
                    client_thread.daemon = True
                    client_thread.start()
                except socket.timeout:
                    continue  # Continue the loop on timeout
                except Exception as e:
                    if self.is_running:  # Only log if not shutting down
                        print(f"Error accepting client: {e}")
                    break
        except Exception as e:
            print(f"Error starting screen share server: {e}")
    
    def _handle_client(self, client):
        try:
            # Set socket timeout for client operations
            client.settimeout(30.0)
            
            # Read the HTTP request
            request = client.recv(1024).decode('utf-8')
            print(f"Received request: {request[:200]}...")  # Log first 200 chars
            
            # Check if this is a request for the stream or the HTML page
            if '/stream' in request:
                print("Stream request detected, adding to stream clients")
                # Add to stream clients
                with self.lock:
                    if len(self.stream_clients) >= self.max_clients:
                        print(f"Maximum clients ({self.max_clients}) reached, rejecting new connection")
                        client.close()
                        return
                    self.stream_clients.append(client)
                    print(f"Added stream client. Total stream clients: {len(self.stream_clients)}")
                
                # Send MJPEG stream header with better caching control
                headers = [
                    b'HTTP/1.1 200 OK\r\n',
                    b'Content-Type: multipart/x-mixed-replace; boundary=frame\r\n',
                    b'Cache-Control: no-cache, no-store, must-revalidate\r\n',
                    b'Pragma: no-cache\r\n',
                    b'Expires: 0\r\n',
                    b'Access-Control-Allow-Origin: *\r\n',
                    b'Connection: keep-alive\r\n\r\n'
                ]
                
                for header in headers:
                    client.send(header)
                
                print("Stream headers sent, keeping connection alive")
                # Keep connection alive for streaming - don't exit on viewing status change
                while self.is_running:
                    try:
                        # Send a keepalive ping every 5 seconds to prevent timeout
                        time.sleep(5.0)
                        
                        # Check if client is still connected
                        try:
                            # Send a small ping to test connection
                            client.send(b'--ping\r\n\r\n')
                        except Exception as ping_error:
                            print(f"Client connection lost: {ping_error}")
                            break
                            
                    except Exception as loop_error:
                        print(f"Error in stream loop: {loop_error}")
                        break
            else:
                print("HTML page request detected")
                # Send HTML page
                html_content = self._get_html_page()
                response = f'HTTP/1.1 200 OK\r\n'
                response += f'Content-Type: text/html\r\n'
                response += f'Content-Length: {len(html_content)}\r\n'
                response += f'Cache-Control: no-cache, no-store, must-revalidate\r\n'
                response += f'Pragma: no-cache\r\n'
                response += f'Expires: 0\r\n'
                response += f'Access-Control-Allow-Origin: *\r\n\r\n'
                response += html_content
                
                client.send(response.encode('utf-8'))
                print("HTML page sent and connection closed")
                client.close()
                
        except Exception as e:
            print(f"Error handling client: {e}")
        finally:
            with self.lock:
                self._remove_client(client)
    
    def _capture_screen(self):
        """Capture screen and send to clients with improved reliability"""
        last_capture_time = 0
        frame_interval = 1.0 / self.fps  # Time between frames
        consecutive_errors = 0
        last_successful_screenshot = None
        error_recovery_delay = 1.0
        
        print(f"Starting screen capture at {self.fps} FPS with {self.quality}% quality")
        
        while self.is_running:
            try:
                # Check if we have any stream clients before capturing
                with self.lock:
                    has_stream_clients = len(self.stream_clients) > 0
                
                # Only capture if we have stream clients or viewing is active
                if not has_stream_clients and not self.is_viewing:
                    time.sleep(0.5)  # Longer sleep when no clients
                    continue
                
                current_time = time.time()
                elapsed = current_time - last_capture_time
                
                # Adaptive frame rate - skip frames if we're falling behind
                if elapsed >= frame_interval or (current_time - self.last_successful_frame) > self.frame_skip_threshold:
                    last_capture_time = current_time
                    
                    # Capture screen with improved error handling
                    try:
                        screenshot = ImageGrab.grab()
                        if screenshot is None:
                            raise Exception("Failed to capture screen - got None")
                        
                        # Verify screenshot is not empty or black
                        if screenshot.size[0] == 0 or screenshot.size[1] == 0:
                            raise Exception("Screenshot has zero dimensions")
                        
                        # Check if screenshot is completely black (common issue)
                        if self._is_image_black(screenshot):
                            if last_successful_screenshot is not None:
                                print("Detected black screen, using last successful screenshot")
                                screenshot = last_successful_screenshot
                            else:
                                raise Exception("Screenshot is black and no fallback available")
                        
                        # Resize image if needed
                        if self.scale != 1.0:
                            new_size = (int(screenshot.width * self.scale), 
                                       int(screenshot.height * self.scale))
                            screenshot = screenshot.resize(new_size, Image.LANCZOS)
                        
                        # Add cursor if enabled
                        if self.show_cursor:
                            self._add_cursor_to_image(screenshot)
                        
                        # Convert to JPEG with optimization
                        buffer = io.BytesIO()
                        screenshot.save(buffer, format='JPEG', quality=self.quality, 
                                       optimize=True, progressive=True)
                        jpeg_bytes = buffer.getvalue()
                        
                        if len(jpeg_bytes) == 0:
                            raise Exception("Empty JPEG data")
                        
                        # Store successful screenshot for fallback
                        last_successful_screenshot = screenshot.copy()
                        
                        # Send to stream clients with better error handling
                        self._send_frame_to_clients(jpeg_bytes)
                        
                        # Reset error counter on success
                        consecutive_errors = 0
                        self.last_successful_frame = current_time
                        error_recovery_delay = 1.0  # Reset delay
                        
                    except Exception as capture_error:
                        consecutive_errors += 1
                        self.capture_errors += 1
                        print(f"Screen capture error ({consecutive_errors}/{self.max_capture_errors}): {capture_error}")
                        
                        # Try to send last successful frame if available
                        if last_successful_screenshot is not None and consecutive_errors <= 3:
                            try:
                                print("Attempting to send last successful frame")
                                buffer = io.BytesIO()
                                last_successful_screenshot.save(buffer, format='JPEG', quality=self.quality)
                                jpeg_bytes = buffer.getvalue()
                                self._send_frame_to_clients(jpeg_bytes)
                            except Exception as fallback_error:
                                print(f"Fallback frame failed: {fallback_error}")
                        
                        if consecutive_errors >= self.max_capture_errors:
                            print(f"Too many consecutive capture errors, pausing capture for {error_recovery_delay}s")
                            time.sleep(error_recovery_delay)
                            consecutive_errors = 0
                            error_recovery_delay = min(error_recovery_delay * 2, 10.0)  # Exponential backoff
                        else:
                            time.sleep(0.1)  # Short delay on capture error
                        continue
                else:
                    # Sleep for remaining time to maintain frame rate
                    sleep_time = frame_interval - elapsed
                    if sleep_time > 0:
                        time.sleep(min(sleep_time, 0.01))
                        
            except Exception as e:
                print(f"Error in capture loop: {e}")
                time.sleep(1.0)  # Longer delay on general error
    
    def _send_frame_to_clients(self, jpeg_bytes):
        """Send frame to all connected stream clients with error handling"""
        with self.lock:
            if not self.stream_clients:
                return  # No clients to send to
                
            clients_to_remove = []
            print(f"Sending frame ({len(jpeg_bytes)} bytes) to {len(self.stream_clients)} clients")
            
            for client in self.stream_clients[:]:  # Create a copy of the list
                try:
                    # Send frame with proper MJPEG format
                    frame_data = [
                        b'--frame\r\n',
                        b'Content-Type: image/jpeg\r\n',
                        f'Content-Length: {len(jpeg_bytes)}\r\n'.encode(),
                        b'\r\n',
                        jpeg_bytes,
                        b'\r\n'
                    ]
                    
                    # Send all frame data atomically
                    for data in frame_data:
                        client.send(data)
                    
                    # Update client health
                    client_id = id(client)
                    if client_id in self.client_health:
                        self.client_health[client_id]['last_success'] = time.time()
                        self.client_health[client_id]['errors'] = 0
                        
                except Exception as send_error:
                    print(f"Error sending frame to client: {send_error}")
                    clients_to_remove.append(client)
            
            # Remove failed clients
            for client in clients_to_remove:
                self._remove_client(client)
                print("Removed disconnected client")
                
            # If we have no more stream clients, reset error counters
            if not self.stream_clients:
                self.capture_errors = 0
                print("No stream clients remaining, resetting error counters")
    
    def _add_cursor_to_image(self, image):
        try:
            cursor_info = win32gui.GetCursorInfo()
            if cursor_info[1] == 0:  # Not visible
                return
                
            cursor_pos = win32gui.GetCursorPos()
            
            # Scale cursor position to match image scale
            scaled_x = int(cursor_pos[0] * self.scale)
            scaled_y = int(cursor_pos[1] * self.scale)
            
            # Ensure cursor is within image bounds
            if 0 <= scaled_x < image.width and 0 <= scaled_y < image.height:
                # Draw cursor on image with better visibility
                draw = ImageDraw.Draw(image)
                cursor_size = 6
                draw.ellipse(
                    (scaled_x-cursor_size, scaled_y-cursor_size, 
                     scaled_x+cursor_size, scaled_y+cursor_size),
                    fill='red', outline='white', width=2
                )
                # Add a small crosshair for better precision
                draw.line((scaled_x-cursor_size*2, scaled_y, scaled_x+cursor_size*2, scaled_y), 
                         fill='white', width=1)
                draw.line((scaled_x, scaled_y-cursor_size*2, scaled_x, scaled_y+cursor_size*2), 
                         fill='white', width=1)
        except Exception as e:
            print(f"Error adding cursor: {e}") 
    
    def _get_html_page(self):
        """Generate HTML page for screen sharing"""
        return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=3.0, user-scalable=yes">
    <title>Screen Share</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        html, body {
            width: 100%;
            height: 100%;
            overflow: hidden;
            background-color: #000;
            touch-action: manipulation;
            -webkit-user-select: none;
            -moz-user-select: none;
            -ms-user-select: none;
            user-select: none;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }
        
        #screen-container {
            width: 100%;
            height: 100%;
            display: flex;
            justify-content: center;
            align-items: center;
            background-color: #000;
            position: relative;
        }
        
        #screen-image {
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
            display: block;
            image-rendering: optimizeSpeed;
            image-rendering: -webkit-optimize-contrast;
            image-rendering: crisp-edges;
            transform: translateZ(0);
            backface-visibility: hidden;
        }
        
        #loading {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            color: white;
            text-align: center;
            z-index: 10;
        }
        
        #error {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            color: #ff6b6b;
            text-align: center;
            z-index: 10;
            display: none;
        }
        
        .spinner {
            border: 3px solid rgba(255,255,255,0.3);
            border-radius: 50%;
            border-top: 3px solid white;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 16px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div id="screen-container">
        <div id="loading">
            <div class="spinner"></div>
            <div>Connecting to screen...</div>
        </div>
        <div id="error">
            <div>⚠️ Connection Error</div>
            <div style="font-size: 14px; margin-top: 8px; opacity: 0.8;">Tap to retry</div>
        </div>
        <img id="screen-image" src="/stream" alt="Screen Share" 
             onload="hideLoading()" 
             onerror="showError()" 
             style="display: none;">
    </div>
    
    <script>
            let reconnectAttempts = 0;
        const maxReconnectAttempts = 5;
        let reconnectTimer = null;
        
        function hideLoading() {
            document.getElementById('loading').style.display = 'none';
            document.getElementById('screen-image').style.display = 'block';
            reconnectAttempts = 0; // Reset on successful load
            }
            
        function showError() {
            document.getElementById('loading').style.display = 'none';
            document.getElementById('error').style.display = 'block';
            document.getElementById('screen-image').style.display = 'none';
            
            // Auto-retry with exponential backoff
            if (reconnectAttempts < maxReconnectAttempts) {
                reconnectAttempts++;
                const delay = Math.min(1000 * Math.pow(2, reconnectAttempts - 1), 10000);
                
                if (reconnectTimer) clearTimeout(reconnectTimer);
                reconnectTimer = setTimeout(() => {
                    console.log('Attempting to reconnect... (attempt ' + reconnectAttempts + ')');
                    document.getElementById('loading').style.display = 'block';
                    document.getElementById('error').style.display = 'none';
                    
                    const img = document.getElementById('screen-image');
                    img.src = '/stream?t=' + Date.now(); // Add cache buster
                }, delay);
                }
            }
            
        // Handle clicks on error message to retry
        document.getElementById('error').addEventListener('click', function() {
            reconnectAttempts = 0;
            showError(); // This will trigger a retry
        });
        
        // Handle visibility change to pause/resume
        document.addEventListener('visibilitychange', function() {
            const img = document.getElementById('screen-image');
            if (document.hidden) {
                // Page is hidden, pause updates
                img.style.display = 'none';
            } else {
                // Page is visible, resume updates
                img.style.display = 'block';
                img.src = '/stream?t=' + Date.now();
                }
        });
            
        // Prevent context menu
            document.addEventListener('contextmenu', function(e) {
                e.preventDefault();
            });
            
        // Prevent text selection
        document.addEventListener('selectstart', function(e) {
                e.preventDefault();
        });
            
        // Optimize for performance
        if ('requestIdleCallback' in window) {
            requestIdleCallback(function() {
                // Apply optimizations when browser is idle
                const img = document.getElementById('screen-image');
                img.style.imageRendering = 'optimizeSpeed';
                img.style.transform = 'translateZ(0)';
                });
            }
    </script>
</body>
</html>''' 

    def _is_image_black(self, image, threshold=0.95):
        """Check if image is mostly black (common screen capture issue)"""
        try:
            # Convert to grayscale and check if mostly black
            gray = image.convert('L')
            pixels = list(gray.getdata())
            black_pixels = sum(1 for p in pixels if p < 10)  # Very dark pixels
            total_pixels = len(pixels)
            
            if total_pixels == 0:
                return True
                
            black_ratio = black_pixels / total_pixels
            return black_ratio > threshold
        except Exception as e:
            print(f"Error checking if image is black: {e}")
            return False 