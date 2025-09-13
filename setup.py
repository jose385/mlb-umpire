#!/usr/bin/env python3
"""
Setup Script for MLB Umpire Scorecard Scraper
==============================================

This script helps set up the environment and test the scraper tools.

Author: Claude
Date: September 2025
"""

import os
import sys
import subprocess
import asyncio
from pathlib import Path


def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 7):
        print("❌ Python 3.7 or higher is required")
        return False
    print(f"✅ Python {sys.version.split()[0]} detected")
    return True


def install_requirements():
    """Install required packages"""
    print("\n📦 Installing required packages...")
    
    requirements = [
        "playwright>=1.40.0",
        "pandas>=1.3.0", 
        "requests>=2.25.0",
        "beautifulsoup4>=4.9.0",
        "python-dateutil>=2.8.0"
    ]
    
    for package in requirements:
        try:
            print(f"Installing {package}...")
            subprocess.run([sys.executable, "-m", "pip", "install", package], 
                         capture_output=True, check=True)
            print(f"✅ {package} installed")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install {package}: {e}")
            return False
    
    return True


def install_playwright():
    """Install Playwright browser"""
    print("\n🌐 Installing Playwright browser...")
    
    try:
        # Install playwright browsers
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], 
                      capture_output=True, check=True)
        print("✅ Playwright chromium browser installed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install Playwright browser: {e}")
        print("Try running manually: python -m playwright install chromium")
        return False


def create_output_directory():
    """Create output directory if it doesn't exist"""
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    print(f"✅ Output directory created: {output_dir.absolute()}")


def test_basic_imports():
    """Test if all required modules can be imported"""
    print("\n🧪 Testing imports...")
    
    modules = [
        ("playwright", "playwright.async_api"),
        ("pandas", "pandas"),
        ("requests", "requests"),
        ("beautifulsoup4", "bs4"),
        ("dateutil", "dateutil")
    ]
    
    for name, module in modules:
        try:
            __import__(module)
            print(f"✅ {name} import successful")
        except ImportError as e:
            print(f"❌ {name} import failed: {e}")
            return False
    
    return True


async def test_scraper():
    """Test the scraper with a simple example"""
    print("\n🔧 Testing scraper functionality...")
    
    try:
        # Import the simple scraper
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from simple_umpire_scraper import SimpleUmpireScraper
        
        scraper = SimpleUmpireScraper()
        
        # Test with a minimal scrape (just check if it loads)
        print("Testing page loading...")
        
        from playwright.async_api import async_playwright
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            try:
                await page.goto("https://umpscorecards.com", timeout=30000)
                print("✅ Successfully loaded umpscorecards.com")
                
                # Check if we can access an umpire page
                await page.goto("https://umpscorecards.com/data/single-umpire/Adam%20Beck", timeout=30000)
                print("✅ Successfully loaded umpire page")
                
            except Exception as e:
                print(f"❌ Page loading test failed: {e}")
                return False
            finally:
                await browser.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Scraper test failed: {e}")
        return False


def show_usage_examples():
    """Show usage examples"""
    print("\n" + "="*60)
    print("🎯 SETUP COMPLETE - USAGE EXAMPLES")
    print("="*60)
    
    print("\n1. Quick Start (Interactive Mode):")
    print("   python simple_umpire_scraper.py")
    
    print("\n2. Discover API Endpoints:")
    print("   python api_discovery.py")
    
    print("\n3. Programmatic Usage:")
    print("""
import asyncio
from simple_umpire_scraper import SimpleUmpireScraper

async def main():
    scraper = SimpleUmpireScraper()
    
    # Single umpire
    data = await scraper.scrape_umpire_page("Angel Hernandez")
    scraper.save_to_csv(data, "angel_hernandez.csv")
    
    # Multiple umpires
    umpires = ["Angel Hernandez", "Pat Hoberg"]
    data = await scraper.scrape_multiple_umpires(umpires)
    scraper.save_to_csv(data, "multiple_umpires.csv")

asyncio.run(main())
    """)
    
    print("\n4. Common Umpire Names:")
    umpires = [
        "Angel Hernandez", "Joe West", "Jerry Meals", "CB Bucknor",
        "Laz Diaz", "Ron Kulpa", "Pat Hoberg", "Adam Beck"
    ]
    for umpire in umpires:
        print(f"   • {umpire}")
    
    print(f"\n📁 Output files will be saved to: {Path('output').absolute()}")


async def main():
    """Main setup function"""
    print("🏟️ MLB Umpire Scorecard Scraper - Setup")
    print("=" * 50)
    
    # Check Python version
    if not check_python_version():
        return False
    
    # Install requirements
    if not install_requirements():
        print("\n❌ Setup failed during package installation")
        return False
    
    # Install Playwright
    if not install_playwright():
        print("\n⚠️  Playwright installation failed, but you can try manually:")
        print("   python -m playwright install chromium")
    
    # Create output directory
    create_output_directory()
    
    # Test imports
    if not test_basic_imports():
        print("\n❌ Setup failed during import testing")
        return False
    
    # Test scraper functionality
    if await test_scraper():
        print("✅ Scraper test successful")
    else:
        print("⚠️  Scraper test failed, but basic setup is complete")
    
    # Show usage examples
    show_usage_examples()
    
    print("\n🎉 Setup completed successfully!")
    print("\nNext steps:")
    print("1. Run: python simple_umpire_scraper.py")
    print("2. Choose option 1 to test with a single umpire")
    print("3. Check the output directory for your CSV files")
    
    return True


if __name__ == "__main__":
    print("Starting setup...")
    
    try:
        success = asyncio.run(main())
        if success:
            print("\n👍 You're ready to start scraping MLB umpire data!")
        else:
            print("\n❌ Setup encountered errors. Please check the messages above.")
    except KeyboardInterrupt:
        print("\n👋 Setup interrupted by user")
    except Exception as e:
        print(f"\n❌ Setup failed with error: {e}")
        print("\nTry running individual setup steps manually:")
        print("1. pip install -r requirements.txt")
        print("2. python -m playwright install chromium")