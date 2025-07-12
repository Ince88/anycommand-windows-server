import socket
import threading
import pyperclip
import logging

class ClipboardService:
    def __init__(self, port=8084):
        self.port = port
        self.is_running = False
        self.server_socket = None
        self.clients = []
        self.lock = threading.Lock()
        
        # Set up logging
        self.logger = logging.getLogger('ClipboardService')
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def start(self):
        if self.is_running:
            return
            
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('0.0.0.0', self.port))
            self.server_socket.listen(5)
            self.is_running = True
            
            self.logger.info(f"Clipboard service started on port {self.port}")
            
            # Start accepting clients
            threading.Thread(target=self._accept_clients, daemon=True).start()
        except Exception as e:
            self.logger.error(f"Error starting clipboard service: {e}")
            self.stop()
    
    def _accept_clients(self):
        while self.is_running:
            try:
                client, addr = self.server_socket.accept()
                self.logger.info(f"New clipboard client connected: {addr}")
                
                with self.lock:
                    self.clients.append(client)
                
                # Start client handler thread
                threading.Thread(target=self._handle_client, args=(client,), daemon=True).start()
            except Exception as e:
                if self.is_running:
                    self.logger.error(f"Error accepting client: {e}")
                break
    
    def _handle_client(self, client):
        try:
            while self.is_running:
                data = client.recv(4096)
                if not data:
                    break
                    
                command = data.decode('utf-8')
                
                if command == 'GET_CLIPBOARD':
                    try:
                        content = pyperclip.paste()
                        # Add error handling for empty clipboard
                        if not content:
                            content = ""
                        client.sendall(content.encode('utf-8'))
                    except Exception as e:
                        self.logger.error(f"Error getting clipboard: {e}")
                        client.sendall("".encode('utf-8'))
                
                elif command.startswith('SET_CLIPBOARD:'):
                    try:
                        content = command[14:]  # Remove 'SET_CLIPBOARD:' prefix
                        if content:  # Only set if content is not empty
                            pyperclip.copy(content)
                            # Send confirmation back to client
                            client.sendall("SUCCESS".encode('utf-8'))
                    except Exception as e:
                        self.logger.error(f"Error setting clipboard: {e}")
                        client.sendall("ERROR".encode('utf-8'))
        except Exception as e:
            self.logger.error(f"Client connection error: {e}")
        finally:
            with self.lock:
                if client in self.clients:
                    self.clients.remove(client)
            try:
                client.close()
            except:
                pass
    
    def stop(self):
        self.is_running = False
        
        # Close all client connections
        with self.lock:
            for client in self.clients:
                try:
                    client.close()
                except:
                    pass
            self.clients = []
        
        # Close server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass 