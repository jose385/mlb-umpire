#!/usr/bin/env python3
"""
MLB Umpire Scorecard Scraper
=====================================

This script scrapes umpire scorecard data from umpscorecards.com with the following features:
- Search by date range and specific umpire
- Intercept dynamic API calls for raw data extraction
- Export data to CSV format
- Handle both individual umpire pages and game data

Requirements:
- pip install playwright pandas requests beautifulsoup4 python-dateutil
- playwright install chromium

Author: Claude
Date: September 2025
"""

import os
import json
import csv
import re
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin, urlparse
import asyncio

import pandas as pd
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from dateutil import parser as date_parser

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class UmpireScorecardScraper:
    """
    A comprehensive scraper for MLB umpire scorecard data from umpscorecards.com
    """
    
    def __init__(self):
        self.base_url = "https://umpscorecards.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.collected_data = []
        self.api_endpoints = []
        
    async def intercept_network_requests(self, url: str, timeout: int = 30000) -> List[Dict]:
        """
        Use Playwright to load a page and intercept network requests to find API endpoints
        """
        intercepted_requests = []
        responses = []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            )
            
            page = await context.new_page()
            
            # Intercept requests
            async def handle_request(request):
                if any(keyword in request.url.lower() for keyword in ['api', 'data', 'json', 'xhr']):
                    intercepted_requests.append({
                        'url': request.url,
                        'method': request.method,
                        'headers': dict(request.headers),
                        'resource_type': request.resource_type
                    })
                    logger.info(f"Intercepted request: {request.method} {request.url}")
            
            # Intercept responses
            async def handle_response(response):
                if any(keyword in response.url.lower() for keyword in ['api', 'data', 'json']) and response.status == 200:
                    try:
                        content_type = response.headers.get('content-type', '').lower()
                        if 'json' in content_type:
                            json_data = await response.json()
                            responses.append({
                                'url': response.url,
                                'status': response.status,
                                'data': json_data,
                                'headers': dict(response.headers)
                            })
                            logger.info(f"Captured JSON response from: {response.url}")
                    except Exception as e:
                        logger.warning(f"Failed to parse JSON from {response.url}: {e}")
            
            page.on("request", handle_request)
            page.on("response", handle_response)
            
            try:
                await page.goto(url, timeout=timeout, wait_until="networkidle")
                await page.wait_for_timeout(5000)  # Wait for any delayed requests
            except Exception as e:
                logger.error(f"Error loading page {url}: {e}")
            
            await browser.close()
        
        return intercepted_requests, responses
    
    def get_umpire_list(self) -> List[Dict[str, str]]:
        """
        Get list of all umpires from the main umpires page
        """
        umpires = []
        try:
            response = self.session.get(f"{self.base_url}/data/umpires", timeout=30)
            response.raise_for_status()
            
            # Since the page loads dynamically, we need to use Playwright
            logger.info("Fetching umpire list using browser automation...")
            
        except Exception as e:
            logger.error(f"Error fetching umpire list: {e}")
            
        return umpires
    
    async def get_umpire_data_async(self, umpire_name: str, start_date: str = None, end_date: str = None) -> List[Dict]:
        """
        Get scorecard data for a specific umpire using browser automation
        """
        umpire_url = f"{self.base_url}/data/single-umpire/{umpire_name.replace(' ', '%20')}"
        logger.info(f"Fetching data for umpire: {umpire_name}")
        
        requests, responses = await self.intercept_network_requests(umpire_url)
        
        collected_data = []
        
        # Process intercepted data
        for response in responses:
            if isinstance(response['data'], list):
                for item in response['data']:
                    if isinstance(item, dict):
                        # Add metadata
                        item['umpire_name'] = umpire_name
                        item['scraped_at'] = datetime.now().isoformat()
                        item['source_url'] = response['url']
                        collected_data.append(item)
            elif isinstance(response['data'], dict):
                response['data']['umpire_name'] = umpire_name
                response['data']['scraped_at'] = datetime.now().isoformat()
                response['data']['source_url'] = response['url']
                collected_data.append(response['data'])
        
        # Filter by date range if provided
        if start_date or end_date:
            collected_data = self.filter_by_date_range(collected_data, start_date, end_date)
        
        return collected_data
    
    async def get_game_data_async(self, game_id: str) -> Dict:
        """
        Get detailed data for a specific game
        """
        game_url = f"{self.base_url}/single_game/?game_id={game_id}"
        logger.info(f"Fetching game data for game ID: {game_id}")
        
        requests, responses = await self.intercept_network_requests(game_url)
        
        for response in responses:
            if isinstance(response['data'], dict):
                response['data']['game_id'] = game_id
                response['data']['scraped_at'] = datetime.now().isoformat()
                return response['data']
        
        return {}
    
    def filter_by_date_range(self, data: List[Dict], start_date: str = None, end_date: str = None) -> List[Dict]:
        """
        Filter data by date range
        """
        if not (start_date or end_date):
            return data
        
        filtered_data = []
        start_dt = date_parser.parse(start_date) if start_date else datetime.min
        end_dt = date_parser.parse(end_date) if end_date else datetime.max
        
        for item in data:
            # Try to find date field in various formats
            item_date = None
            date_fields = ['date', 'game_date', 'Date', 'gameDate', 'created_at', 'timestamp']
            
            for field in date_fields:
                if field in item:
                    try:
                        item_date = date_parser.parse(str(item[field]))
                        break
                    except:
                        continue
            
            if item_date and start_dt <= item_date <= end_dt:
                filtered_data.append(item)
        
        logger.info(f"Filtered {len(filtered_data)} items from {len(data)} total items")
        return filtered_data
    
    def save_to_csv(self, data: List[Dict], filename: str = None) -> str:
        """
        Save collected data to CSV file
        """
        if not data:
            logger.warning("No data to save")
            return None
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"umpire_scorecards_{timestamp}.csv"
        
        # Flatten nested dictionaries and ensure consistent structure
        flattened_data = []
        for item in data:
            flat_item = self.flatten_dict(item)
            flattened_data.append(flat_item)
        
        # Create DataFrame
        df = pd.DataFrame(flattened_data)
        
        # Save to CSV
        output_path = os.path.join(os.getcwd(), filename)
        df.to_csv(output_path, index=False)
        
        logger.info(f"Data saved to {output_path}")
        logger.info(f"Saved {len(df)} rows with {len(df.columns)} columns")
        
        return output_path
    
    def flatten_dict(self, d: Dict, parent_key: str = '', sep: str = '_') -> Dict:
        """
        Flatten nested dictionaries
        """
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self.flatten_dict(v, new_key, sep=sep).items())
            elif isinstance(v, list):
                # Handle lists by converting to string or taking first element if it's simple
                if v and isinstance(v[0], dict):
                    for i, item in enumerate(v):
                        items.extend(self.flatten_dict(item, f"{new_key}_{i}", sep=sep).items())
                else:
                    items.append((new_key, str(v)))
            else:
                items.append((new_key, v))
        return dict(items)
    
    async def search_umpires(self, name_pattern: str) -> List[str]:
        """
        Search for umpires matching a pattern
        """
        # This would need to be implemented based on the actual API structure
        # For now, return a list of common umpire names for testing
        common_umpires = [
            "Angel Hernandez", "Joe West", "Jerry Meals", "CB Bucknor", 
            "Laz Diaz", "Ron Kulpa", "Pat Hoberg", "Adam Beck",
            "Mark Ripperger", "Dan Bellino", "Chris Guccione"
        ]
        
        matches = [name for name in common_umpires if name_pattern.lower() in name.lower()]
        return matches
    
    async def bulk_scrape(self, umpire_names: List[str], start_date: str = None, end_date: str = None) -> List[Dict]:
        """
        Scrape data for multiple umpires
        """
        all_data = []
        
        for umpire_name in umpire_names:
            logger.info(f"Processing umpire: {umpire_name}")
            try:
                umpire_data = await self.get_umpire_data_async(umpire_name, start_date, end_date)
                all_data.extend(umpire_data)
                
                # Be respectful with requests
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Error processing umpire {umpire_name}: {e}")
                continue
        
        return all_data


async def main():
    """
    Example usage of the scraper
    """
    scraper = UmpireScorecardScraper()
    
    # Example 1: Get data for a specific umpire
    print("=== Example 1: Single Umpire Data ===")
    umpire_data = await scraper.get_umpire_data_async(
        umpire_name="Adam Beck",
        start_date="2024-01-01",
        end_date="2024-12-31"
    )
    
    if umpire_data:
        csv_file = scraper.save_to_csv(umpire_data, "adam_beck_2024.csv")
        print(f"Saved Adam Beck data to: {csv_file}")
    
    # Example 2: Search for umpires
    print("\n=== Example 2: Search Umpires ===")
    matching_umpires = await scraper.search_umpires("Angel")
    print(f"Found umpires matching 'Angel': {matching_umpires}")
    
    # Example 3: Bulk scrape multiple umpires
    print("\n=== Example 3: Bulk Scraping ===")
    umpires_to_scrape = ["Angel Hernandez", "Pat Hoberg"]
    bulk_data = await scraper.bulk_scrape(
        umpire_names=umpires_to_scrape,
        start_date="2024-06-01",
        end_date="2024-08-31"
    )
    
    if bulk_data:
        bulk_csv_file = scraper.save_to_csv(bulk_data, "bulk_umpire_data_summer_2024.csv")
        print(f"Saved bulk data to: {bulk_csv_file}")
    
    # Example 4: Get specific game data
    print("\n=== Example 4: Single Game Data ===")
    # Note: You would need to find actual game IDs from the umpire data
    # game_data = await scraper.get_game_data_async("715723")
    # if game_data:
    #     print(f"Game data keys: {list(game_data.keys())}")


if __name__ == "__main__":
    print("MLB Umpire Scorecard Scraper")
    print("==============================")
    print("This script will help you scrape umpire scorecard data from umpscorecards.com")
    print("\nFirst, install required dependencies:")
    print("pip install playwright pandas requests beautifulsoup4 python-dateutil")
    print("playwright install chromium")
    print("\nStarting scraper...")
    
    asyncio.run(main())