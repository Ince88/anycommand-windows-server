import os
import socket
import threading
import logging
import time
import json
import configparser
from pathlib import Path

class FileTransferService:
    def __init__(self, port=8082):
        self.port = port
        self.server_socket = None
        self.is_running = False
        self.clients = []
        self.lock = threading.Lock()
        
        # Create transfer directory
        self.transfer_dir = self._get_transfer_directory()
        os.makedirs(self.transfer_dir, exist_ok=True)
        
        # Set up logging
        self.logger = logging.getLogger('FileTransferService')
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
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
            self.logger.error(f"Error getting transfer directory: {e}")
            return os.path.join(os.path.expanduser("~"), "AnyCommand Transfers")
    
    def start(self):
        """Start the file transfer server"""
        if self.is_running:
            return
        
        self.is_running = True
        self.server_thread = threading.Thread(target=self._run_server)
        self.server_thread.daemon = True
        self.server_thread.start()
        self.logger.info(f"File transfer server started on port {self.port}")
        self.logger.info(f"Transfer directory: {self.transfer_dir}")
    
    def stop(self):
        """Stop the file transfer server"""
        self.is_running = False
        if self.server_socket:
            self.server_socket.close()
        
        with self.lock:
            for client in self.clients:
                try:
                    client.close()
                except:
                    pass
            self.clients.clear()
        
        self.logger.info("File transfer server stopped")
    
    def _run_server(self):
        """Run the server socket"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('0.0.0.0', self.port))
            self.server_socket.settimeout(1.0)  # 1 second timeout for accept
            self.server_socket.listen(5)
            
            while self.is_running:
                try:
                    client, address = self.server_socket.accept()
                    self.logger.info(f"New file transfer client connected: {address}")
                    
                    with self.lock:
                        self.clients.append(client)
                    
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client, address)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.is_running:
                        self.logger.error(f"Error accepting connection: {e}")
                    time.sleep(0.1)
        except Exception as e:
            self.logger.error(f"Server error: {e}")
        finally:
            if self.server_socket:
                self.server_socket.close()
            self.logger.info("File transfer server socket closed")
    
    def handle_client(self, client, addr):
        """Handle client connection for file transfer"""
        try:
            self.logger.info(f"Client connected: {addr}")
            client.settimeout(60)  # Set a longer timeout for multiple transfers
            
            while True:  # Keep connection open for multiple transfers
                try:
                    # Wait for command
                    data = client.recv(1024).decode('utf-8')
                    if not data:
                        break
                    
                    # Process command
                    if data.startswith('LIST'):
                        self.send_file_list(client)
                    elif data.startswith('SEND:'):
                        # Extract file info
                        parts = data.strip().split(':', 2)
                        if len(parts) < 3:
                            client.sendall("ERROR:Invalid file info format\n".encode())
                            continue
                        
                        filename = parts[1]
                        filesize = int(parts[2])
                        
                        # Handle the file transfer
                        self.receive_file(client, filename, filesize)
                        
                        # Send confirmation
                        client.sendall(f"OK:File {filename} received successfully\n".encode())
                    elif data.startswith('GET:'):
                        # Extract filename
                        parts = data.strip().split(':', 1)
                        if len(parts) < 2:
                            client.sendall("ERROR:Invalid get request format\n".encode())
                            continue
                        
                        filename = parts[1]
                        self.send_file(client, filename)
                    else:
                        client.sendall("ERROR:Unknown command\n".encode())
                except socket.timeout:
                    # Just a timeout, client might send another command
                    continue
                except Exception as e:
                    self.logger.error(f"Error handling client request: {e}")
                    try:
                        client.sendall(f"ERROR:{str(e)}\n".encode())
                    except:
                        pass
                    break
        except Exception as e:
            self.logger.error(f"Error handling client: {e}")
        finally:
            with self.lock:
                if client in self.clients:
                    self.clients.remove(client)
            try:
                client.close()
            except:
                pass
            self.logger.info(f"Client disconnected: {addr}")
    
    def send_file_list(self, client):
        """Send a list of files in the transfer directory"""
        files = []
        for item in os.listdir(self.transfer_dir):
            item_path = os.path.join(self.transfer_dir, item)
            if os.path.isfile(item_path):
                files.append(item)
        
        client.sendall(f"FILES:{','.join(files)}\n".encode())
        self.logger.info(f"Sent file list: {len(files)} files")
    
    def receive_file(self, client, filename, filesize):
        """Receive a file from the client"""
        try:
            # Sanitize filename
            safe_name = os.path.basename(filename)
            file_path = os.path.join(self.transfer_dir, safe_name)
            
            # Receive file data
            self.logger.info(f"Receiving file: {safe_name} ({filesize} bytes)")
            
            with open(file_path, 'wb') as f:
                bytes_received = 0
                buffer_size = 4096  # Match client chunk size
                
                # Set a timeout for receiving data
                original_timeout = client.gettimeout()
                client.settimeout(30)  # 30 seconds timeout
                
                try:
                    while bytes_received < filesize:
                        # Calculate remaining bytes
                        remaining = filesize - bytes_received
                        chunk_size = min(buffer_size, remaining)
                        
                        chunk = client.recv(chunk_size)
                        if not chunk:
                            break
                            
                        f.write(chunk)
                        bytes_received += len(chunk)
                        
                        # Log progress periodically
                        if bytes_received % (buffer_size * 20) == 0 or bytes_received == filesize:
                            progress = int((bytes_received / filesize) * 100)
                            self.logger.info(f"Receiving progress: {progress}% ({bytes_received}/{filesize})")
                
                finally:
                    # Restore original timeout
                    client.settimeout(original_timeout)
            
            # Check if we received the complete file
            if bytes_received == filesize:
                self.logger.info(f"File received successfully: {safe_name} ({filesize} bytes)")
            else:
                self.logger.error(f"Incomplete file: {bytes_received}/{filesize} bytes")
        except Exception as e:
            self.logger.error(f"Error receiving file: {e}")
    
    def send_file(self, client, filename):
        """Send a file to the client"""
        try:
            # Sanitize filename to prevent directory traversal
            safe_name = os.path.basename(filename)
            file_path = os.path.join(self.transfer_dir, safe_name)
            
            if not os.path.exists(file_path):
                client.sendall(f"ERROR:File not found: {safe_name}\n".encode())
                return
            
            file_size = os.path.getsize(file_path)
            
            # Send file info
            client.sendall(f"SENDING:{safe_name}:{file_size}\n".encode())
            
            # Add a small delay to ensure the header is processed separately
            time.sleep(0.1)
            
            # Send file data
            with open(file_path, 'rb') as f:
                bytes_sent = 0
                while bytes_sent < file_size:
                    chunk = f.read(min(8192, file_size - bytes_sent))
                    if not chunk:
                        break
                    client.sendall(chunk)
                    bytes_sent += len(chunk)
            
            self.logger.info(f"File sent: {safe_name} ({file_size} bytes)")
        except Exception as e:
            self.logger.error(f"Error sending file: {e}")
            client.sendall(f"ERROR:Failed to send file: {str(e)}\n".encode()) 