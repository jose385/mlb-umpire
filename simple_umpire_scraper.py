#!/usr/bin/env python3
"""
Simple MLB Umpire Scorecard Scraper
===================================

A more straightforward approach to scraping umpire data with fallback methods.
This version focuses on reliability and ease of use.

Author: Claude
Date: September 2025
"""

import asyncio
import csv
import json
import logging
import os
import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import quote_plus

import pandas as pd
import requests
from playwright.async_api import async_playwright

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class SimpleUmpireScraper:
    """Simple and reliable umpire scorecard scraper"""
    
    def __init__(self):
        self.base_url = "https://umpscorecards.com"
        self.data = []
        
    async def scrape_umpire_page(self, umpire_name: str) -> List[Dict]:
        """
        Scrape a single umpire's page using Playwright
        """
        url = f"{self.base_url}/data/single-umpire/{quote_plus(umpire_name)}"
        logger.info(f"Scraping: {url}")
        
        collected_data = []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            
            try:
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                
                page = await context.new_page()
                
                # Capture network responses
                responses_data = []
                
                async def handle_response(response):
                    if 'json' in response.headers.get('content-type', '').lower():
                        try:
                            json_data = await response.json()
                            responses_data.append({
                                'url': response.url,
                                'data': json_data
                            })
                            logger.info(f"Captured JSON from: {response.url}")
                        except:
                            pass
                
                page.on('response', handle_response)
                
                # Navigate and wait for content
                await page.goto(url, wait_until='networkidle', timeout=60000)
                
                # Wait for potential dynamic loading
                await page.wait_for_timeout(5000)
                
                # Try to find and click any load more buttons or pagination
                try:
                    load_more_selectors = [
                        'button:has-text("Load")',
                        'button:has-text("More")',
                        'button:has-text("Show")',
                        '.load-more',
                        '.show-more'
                    ]
                    
                    for selector in load_more_selectors:
                        elements = await page.query_selector_all(selector)
                        for element in elements:
                            try:
                                await element.click()
                                await page.wait_for_timeout(2000)
                            except:
                                pass
                except:
                    pass
                
                # Process captured JSON responses
                for response in responses_data:
                    if isinstance(response['data'], list):
                        for item in response['data']:
                            if isinstance(item, dict):
                                item['umpire_name'] = umpire_name
                                item['scraped_timestamp'] = datetime.now().isoformat()
                                collected_data.append(item)
                    elif isinstance(response['data'], dict):
                        response['data']['umpire_name'] = umpire_name
                        response['data']['scraped_timestamp'] = datetime.now().isoformat()
                        collected_data.append(response['data'])
                
                # If no JSON data found, try to scrape visible content
                if not collected_data:
                    logger.info("No JSON data found, attempting to scrape visible content")
                    
                    # Look for table data or structured content
                    tables = await page.query_selector_all('table')
                    for table in tables:
                        rows = await table.query_selector_all('tr')
                        if len(rows) > 1:  # Has header row
                            # Extract table data
                            table_data = await self.extract_table_data(page, table)
                            for row in table_data:
                                row['umpire_name'] = umpire_name
                                row['scraped_timestamp'] = datetime.now().isoformat()
                                collected_data.append(row)
                
                logger.info(f"Collected {len(collected_data)} records for {umpire_name}")
                
            except Exception as e:
                logger.error(f"Error scraping {umpire_name}: {e}")
                
            finally:
                await browser.close()
        
        return collected_data
    
    async def extract_table_data(self, page, table) -> List[Dict]:
        """Extract data from HTML table"""
        try:
            rows = await table.query_selector_all('tr')
            if len(rows) < 2:
                return []
            
            # Get headers
            header_cells = await rows[0].query_selector_all('th, td')
            headers = []
            for cell in header_cells:
                text = await cell.inner_text()
                headers.append(text.strip())
            
            # Get data rows
            table_data = []
            for row in rows[1:]:
                cells = await row.query_selector_all('td')
                if len(cells) == len(headers):
                    row_data = {}
                    for i, cell in enumerate(cells):
                        text = await cell.inner_text()
                        row_data[headers[i]] = text.strip()
                    table_data.append(row_data)
            
            return table_data
            
        except Exception as e:
            logger.error(f"Error extracting table data: {e}")
            return []
    
    def filter_by_date_range(self, data: List[Dict], start_date: str = None, end_date: str = None) -> List[Dict]:
        """Filter data by date range"""
        if not (start_date or end_date):
            return data
        
        filtered_data = []
        
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d') if start_date else datetime.min
            end_dt = datetime.strptime(end_date, '%Y-%m-%d') if end_date else datetime.max
        except ValueError as e:
            logger.error(f"Invalid date format: {e}")
            return data
        
        for item in data:
            # Try to find date in common field names
            date_fields = ['date', 'game_date', 'Date', 'gameDate', 'Game Date']
            item_date = None
            
            for field in date_fields:
                if field in item and item[field]:
                    try:
                        # Try different date formats
                        date_str = str(item[field])
                        for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y-%m-%d %H:%M:%S']:
                            try:
                                item_date = datetime.strptime(date_str[:10], fmt)
                                break
                            except:
                                continue
                        if item_date:
                            break
                    except:
                        continue
            
            if item_date and start_dt <= item_date <= end_dt:
                filtered_data.append(item)
        
        logger.info(f"Filtered to {len(filtered_data)} records from {len(data)} total")
        return filtered_data
    
    def save_to_csv(self, data: List[Dict], filename: str = None) -> str:
        """Save data to CSV file"""
        if not data:
            logger.warning("No data to save")
            return None
        
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'umpire_data_{timestamp}.csv'
        
        # Ensure output directory exists
        output_dir = '/mnt/user-data/outputs'
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, filename)
        
        # Create DataFrame and save
        df = pd.DataFrame(data)
        
        # Clean up the data
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].astype(str).str.strip()
        
        df.to_csv(filepath, index=False)
        
        logger.info(f"Saved {len(df)} rows to {filepath}")
        print(f"✅ Data saved to: {filepath}")
        print(f"📊 Records: {len(df)} rows × {len(df.columns)} columns")
        
        # Print column names for reference
        print(f"📋 Columns: {', '.join(df.columns.tolist())}")
        
        return filepath
    
    async def scrape_multiple_umpires(self, umpire_names: List[str], 
                                    start_date: str = None, end_date: str = None) -> List[Dict]:
        """Scrape data for multiple umpires"""
        all_data = []
        
        for i, umpire_name in enumerate(umpire_names, 1):
            print(f"\n🔍 Processing umpire {i}/{len(umpire_names)}: {umpire_name}")
            
            try:
                umpire_data = await self.scrape_umpire_page(umpire_name)
                
                if start_date or end_date:
                    umpire_data = self.filter_by_date_range(umpire_data, start_date, end_date)
                
                all_data.extend(umpire_data)
                print(f"✅ Collected {len(umpire_data)} records for {umpire_name}")
                
                # Rate limiting - be respectful
                if i < len(umpire_names):
                    print("⏳ Waiting 3 seconds before next request...")
                    await asyncio.sleep(3)
                    
            except Exception as e:
                logger.error(f"Error processing {umpire_name}: {e}")
                print(f"❌ Failed to scrape {umpire_name}: {e}")
                continue
        
        return all_data


def get_common_umpires() -> List[str]:
    """Return list of common MLB umpires"""
    return [
        "Angel Hernandez",
        "Joe West", 
        "Jerry Meals",
        "CB Bucknor",
        "Laz Diaz",
        "Ron Kulpa", 
        "Pat Hoberg",
        "Adam Beck",
        "Mark Ripperger",
        "Dan Bellino",
        "Chris Guccione",
        "Nic Lentz",
        "Will Little",
        "James Hoye",
        "Hunter Wendelstedt",
        "Tom Hallion",
        "Todd Tichenor",
        "Tripp Gibson",
        "Ryan Additon",
        "Sean Barber"
    ]


async def interactive_mode():
    """Interactive mode for easy usage"""
    print("\n" + "="*50)
    print("🔍 MLB Umpire Scorecard Scraper")
    print("="*50)
    
    scraper = SimpleUmpireScraper()
    
    print("\nChoose an option:")
    print("1. Scrape specific umpire")
    print("2. Scrape multiple umpires")
    print("3. Show common umpire names")
    print("4. Scrape with date filtering")
    
    choice = input("\nEnter choice (1-4): ").strip()
    
    if choice == "1":
        umpire_name = input("Enter umpire name (e.g., 'Angel Hernandez'): ").strip()
        if umpire_name:
            print(f"🔍 Scraping data for: {umpire_name}")
            data = await scraper.scrape_umpire_page(umpire_name)
            if data:
                filename = f"{umpire_name.replace(' ', '_').lower()}_scorecard_data.csv"
                scraper.save_to_csv(data, filename)
            else:
                print("❌ No data found")
    
    elif choice == "2":
        names_input = input("Enter umpire names separated by commas: ").strip()
        if names_input:
            umpire_names = [name.strip() for name in names_input.split(',')]
            print(f"🔍 Scraping data for {len(umpire_names)} umpires")
            data = await scraper.scrape_multiple_umpires(umpire_names)
            if data:
                scraper.save_to_csv(data, "multiple_umpires_data.csv")
            else:
                print("❌ No data found")
    
    elif choice == "3":
        umpires = get_common_umpires()
        print("\n📋 Common MLB Umpires:")
        for i, name in enumerate(umpires, 1):
            print(f"{i:2d}. {name}")
        print(f"\nTotal: {len(umpires)} umpires")
    
    elif choice == "4":
        umpire_name = input("Enter umpire name: ").strip()
        start_date = input("Enter start date (YYYY-MM-DD) or press Enter to skip: ").strip()
        end_date = input("Enter end date (YYYY-MM-DD) or press Enter to skip: ").strip()
        
        if umpire_name:
            print(f"🔍 Scraping {umpire_name} from {start_date or 'beginning'} to {end_date or 'present'}")
            data = await scraper.scrape_umpire_page(umpire_name)
            
            if start_date or end_date:
                data = scraper.filter_by_date_range(data, start_date, end_date)
            
            if data:
                filename = f"{umpire_name.replace(' ', '_').lower()}_filtered_data.csv"
                scraper.save_to_csv(data, filename)
            else:
                print("❌ No data found")
    
    else:
        print("❌ Invalid choice")


async def main():
    """Main function with examples"""
    print("🚀 Starting MLB Umpire Scorecard Scraper")
    
    # Ask user if they want interactive mode or examples
    mode = input("\nChoose mode:\n1. Interactive mode\n2. Run examples\nEnter choice (1-2): ").strip()
    
    if mode == "1":
        await interactive_mode()
    else:
        # Run examples
        scraper = SimpleUmpireScraper()
        
        # Example 1: Single umpire
        print("\n📊 Example 1: Scraping Adam Beck")
        beck_data = await scraper.scrape_umpire_page("Adam Beck")
        if beck_data:
            scraper.save_to_csv(beck_data, "adam_beck_example.csv")
        
        # Example 2: Multiple umpires with date filter
        print("\n📊 Example 2: Multiple umpires (last 90 days)")
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
        
        test_umpires = ["Angel Hernandez", "Pat Hoberg"]
        multi_data = await scraper.scrape_multiple_umpires(
            test_umpires, 
            start_date=start_date, 
            end_date=end_date
        )
        
        if multi_data:
            scraper.save_to_csv(multi_data, "multiple_umpires_recent.csv")


if __name__ == "__main__":
    print("🏟️ MLB Umpire Scorecard Scraper")
    print("=" * 40)
    print("This tool helps you scrape umpire scorecard data from umpscorecards.com")
    print("\n📋 Requirements:")
    print("pip install playwright pandas requests")
    print("playwright install chromium")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Scraping interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"❌ Error: {e}")