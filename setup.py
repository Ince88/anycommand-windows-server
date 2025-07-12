#!/usr/bin/env python3
"""
Setup script for AnyCommand Windows Server
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        print(f"Current version: {sys.version}")
        return False
    print(f"✅ Python {sys.version.split()[0]} detected")
    return True

def install_dependencies():
    """Install required Python packages"""
    print("\n📦 Installing dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False

def create_config_files():
    """Create necessary configuration files"""
    print("\n⚙️  Creating configuration files...")
    
    # Create preferences.ini if it doesn't exist
    if not os.path.exists("preferences.ini"):
        with open("preferences.ini", "w") as f:
            f.write("""[General]
auto_hide=false
minimize_to_tray=true
start_minimized=false
""")
        print("✅ Created preferences.ini")
    
    # Create preferences.json if it doesn't exist
    if not os.path.exists("preferences.json"):
        with open("preferences.json", "w") as f:
            f.write('{"auto_hide": false, "minimize_to_tray": true, "start_minimized": false}')
        print("✅ Created preferences.json")
    
    # Create paired_devices.json if it doesn't exist
    if not os.path.exists("paired_devices.json"):
        with open("paired_devices.json", "w") as f:
            f.write("[]")
        print("✅ Created paired_devices.json")

def check_firebase_config():
    """Check if Firebase configuration is set up"""
    if not os.path.exists("firebase-service-account.json"):
        print("\n⚠️  Firebase configuration not found")
        print("If you need Firebase features, copy firebase-service-account.template.json")
        print("to firebase-service-account.json and fill in your credentials")
    else:
        print("✅ Firebase configuration found")

def create_directories():
    """Create necessary directories"""
    print("\n📁 Creating directories...")
    
    directories = ["assets", "logs", "temp"]
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"✅ Created {directory}/ directory")

def main():
    """Main setup function"""
    print("🚀 AnyCommand Windows Server Setup")
    print("=" * 40)
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Install dependencies
    if not install_dependencies():
        sys.exit(1)
    
    # Create configuration files
    create_config_files()
    
    # Check Firebase configuration
    check_firebase_config()
    
    # Create directories
    create_directories()
    
    print("\n🎉 Setup completed successfully!")
    print("\nNext steps:")
    print("1. Run 'python server_gui.py' to start the server")
    print("2. Configure your PIN settings in the GUI")
    print("3. Connect from your mobile device using the AnyCommand app")
    print("\nFor more information, see README.md")

if __name__ == "__main__":
    main() 