#!/usr/bin/env python3
"""
Setup script for Marktplaats TV Monitor
"""

import os
import sys
import subprocess
from pathlib import Path

# Required modules for the application
REQUIRED_MODULES = [
    'requests',
    'bs4',
    'google.genai',
    'json',
    'logging'
]

def check_python_version():
    """Check if Python version is compatible."""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        print(f"Current version: {sys.version}")
        return False
    print(f"✅ Python version: {sys.version.split()[0]}")
    return True

def install_dependencies():
    """Install required dependencies."""
    print("\n📦 Installing dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False

def setup_environment():
    """Set up environment file."""
    env_file = Path(".env")
    example_file = Path("env.example")
    
    if env_file.exists():
        print("✅ .env file already exists")
        return True
    
    if example_file.exists():
        print("\n📋 Setting up environment file...")
        
        # Copy example to .env
        with open(example_file, 'r') as f:
            content = f.read()
        
        with open(env_file, 'w') as f:
            f.write(content)
        
        print("✅ Created .env file from template")
        print("⚠️  Please edit .env with your Discord webhook URL and Gemini API key")
        return True
    else:
        print("❌ env.example file not found")
        return False

def validate_config():
    """Validate configuration."""
    print("\n🔍 Validating configuration...")
    
    try:
        from config import Config
        
        # Configuration is automatically loaded from .env file
        if Config.validate():
            print("✅ Configuration is valid")
            Config.print_config()
            return True
        else:
            print("❌ Configuration validation failed")
            return False
    except Exception as e:
        print(f"❌ Error validating configuration: {e}")
        return False

def test_imports():
    """Test if all required modules can be imported."""
    print("\n🧪 Testing imports...")
    
    failed_imports = []
    
    for module in REQUIRED_MODULES:
        try:
            __import__(module)
            print(f"✅ {module}")
        except ImportError as e:
            print(f"❌ {module}: {e}")
            failed_imports.append(module)
    
    if failed_imports:
        print(f"\n⚠️  Some modules failed to import: {', '.join(failed_imports)}")
        print("Try running: pip install -r requirements.txt")
        return False
    
    print("✅ All imports successful")
    return True

def main():
    """Main setup function."""
    print("🚀 Marktplaats TV Monitor Setup")
    print("=" * 40)
    
    success = True
    
    # Check Python version
    if not check_python_version():
        success = False
    
    # Install dependencies
    if success and not install_dependencies():
        success = False
    
    # Test imports
    if success and not test_imports():
        success = False
    
    # Setup environment
    if success and not setup_environment():
        success = False
    
    # Validate configuration
    if success:
        validate_config()
    
    print("\n" + "=" * 40)
    
    if success:
        print("🎉 Setup completed successfully!")
        print("\n📝 Next steps:")
        print("1. Copy env.example to .env: cp env.example .env")
        print("2. Edit .env with your Discord webhook URL and Gemini API key")
        print("3. Run: python marktplaats_scraper.py")
        print("\n💡 The application will automatically load your .env file - no exports needed!")
    else:
        print("❌ Setup incomplete. Please fix the errors above.")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
