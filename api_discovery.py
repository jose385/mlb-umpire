#!/usr/bin/env python3
"""
UmpScorecards API Discovery Tool
================================

This script helps discover the API endpoints used by umpscorecards.com
by intercepting network requests and analyzing them.

Author: Claude
Date: September 2025
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Set
from urllib.parse import urlparse

from playwright.async_api import async_playwright

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class APIDiscovery:
    """Discover and analyze API endpoints from umpscorecards.com"""
    
    def __init__(self):
        self.base_url = "https://umpscorecards.com"
        self.discovered_endpoints = set()
        self.api_responses = []
        self.request_patterns = {}
    
    async def discover_endpoints(self, urls_to_check: List[str]) -> Dict:
        """
        Discover API endpoints by visiting various pages
        """
        all_requests = []
        all_responses = []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            )
            
            page = await context.new_page()
            
            # Track all requests
            async def handle_request(request):
                request_info = {
                    'url': request.url,
                    'method': request.method,
                    'headers': dict(request.headers),
                    'resource_type': request.resource_type,
                    'timestamp': datetime.now().isoformat()
                }
                all_requests.append(request_info)
                
                # Check if this looks like an API endpoint
                if self.is_api_endpoint(request.url):
                    self.discovered_endpoints.add(request.url)
                    logger.info(f"🔍 API Request: {request.method} {request.url}")
            
            # Track all responses
            async def handle_response(response):
                if self.is_api_endpoint(response.url):
                    try:
                        content_type = response.headers.get('content-type', '').lower()
                        if 'json' in content_type:
                            json_data = await response.json()
                            response_info = {
                                'url': response.url,
                                'status': response.status,
                                'headers': dict(response.headers),
                                'data': json_data,
                                'timestamp': datetime.now().isoformat()
                            }
                            all_responses.append(response_info)
                            logger.info(f"📊 API Response: {response.status} {response.url}")
                            
                            # Analyze the data structure
                            self.analyze_response_structure(response.url, json_data)
                            
                    except Exception as e:
                        logger.warning(f"Failed to parse JSON from {response.url}: {e}")
            
            page.on('request', handle_request)
            page.on('response', handle_response)
            
            # Visit each URL
            for url in urls_to_check:
                try:
                    logger.info(f"🌐 Visiting: {url}")
                    await page.goto(url, wait_until='networkidle', timeout=30000)
                    await page.wait_for_timeout(5000)  # Wait for lazy loading
                    
                    # Try to interact with the page to trigger more requests
                    await self.interact_with_page(page)
                    
                except Exception as e:
                    logger.error(f"Error visiting {url}: {e}")
                    continue
            
            await browser.close()
        
        return {
            'endpoints': list(self.discovered_endpoints),
            'requests': all_requests,
            'responses': all_responses,
            'patterns': self.request_patterns
        }
    
    def is_api_endpoint(self, url: str) -> bool:
        """Check if a URL looks like an API endpoint"""
        api_indicators = [
            '/api/',
            '/data/',
            '/json/',
            'ajax',
            'xhr',
            '.json',
            'graphql',
            'rest'
        ]
        
        url_lower = url.lower()
        return any(indicator in url_lower for indicator in api_indicators)
    
    def analyze_response_structure(self, url: str, data):
        """Analyze the structure of API responses"""
        if isinstance(data, dict):
            keys = list(data.keys())
            self.request_patterns[url] = {
                'type': 'object',
                'keys': keys,
                'sample_data': {k: type(v).__name__ for k, v in data.items()}
            }
        elif isinstance(data, list) and data:
            first_item = data[0]
            if isinstance(first_item, dict):
                keys = list(first_item.keys())
                self.request_patterns[url] = {
                    'type': 'array',
                    'count': len(data),
                    'item_keys': keys,
                    'sample_item': {k: type(v).__name__ for k, v in first_item.items()}
                }
    
    async def interact_with_page(self, page):
        """Try to interact with page elements to trigger more API calls"""
        try:
            # Look for common interactive elements
            selectors_to_try = [
                'button',
                '[role="button"]',
                '.load-more',
                '.show-more',
                'a[href*="umpire"]',
                'select',
                'input[type="date"]'
            ]
            
            for selector in selectors_to_try:
                elements = await page.query_selector_all(selector)
                for element in elements[:3]:  # Limit to first 3 elements
                    try:
                        await element.click()
                        await page.wait_for_timeout(1000)
                    except:
                        continue
                        
        except Exception as e:
            logger.debug(f"Page interaction error: {e}")
    
    def save_discovery_results(self, results: Dict, filename: str = None):
        """Save discovery results to file"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'/mnt/user-data/outputs/api_discovery_{timestamp}.json'
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info(f"Discovery results saved to {filename}")
        return filename
    
    def print_summary(self, results: Dict):
        """Print a summary of discovered endpoints"""
        print("\n" + "="*60)
        print("🔍 API DISCOVERY SUMMARY")
        print("="*60)
        
        endpoints = results['endpoints']
        responses = results['responses']
        patterns = results['patterns']
        
        print(f"\n📊 Discovered {len(endpoints)} API endpoints:")
        for endpoint in sorted(endpoints):
            print(f"  • {endpoint}")
        
        print(f"\n📈 Captured {len(responses)} API responses:")
        for response in responses[:10]:  # Show first 10
            print(f"  • {response['status']} {response['url']}")
        
        if len(responses) > 10:
            print(f"  ... and {len(responses) - 10} more")
        
        print(f"\n🏗️  Data structure patterns found:")
        for url, pattern in patterns.items():
            print(f"\n  URL: {url}")
            if pattern['type'] == 'object':
                print(f"    Type: Object with keys: {pattern['keys']}")
            elif pattern['type'] == 'array':
                print(f"    Type: Array of {pattern['count']} items")
                print(f"    Item keys: {pattern['item_keys']}")


async def main():
    """Main discovery function"""
    discovery = APIDiscovery()
    
    # URLs to check for API endpoints
    urls_to_check = [
        "https://umpscorecards.com",
        "https://umpscorecards.com/data/umpires",
        "https://umpscorecards.com/data/single-umpire/Angel%20Hernandez",
        "https://umpscorecards.com/data/single-umpire/Adam%20Beck",
        "https://umpscorecards.com/data/single-umpire/Pat%20Hoberg",
        "https://umpscorecards.com/single_game/?game_id=715723"
    ]
    
    print("🚀 Starting API Discovery...")
    print(f"🎯 Checking {len(urls_to_check)} URLs for API endpoints")
    
    results = await discovery.discover_endpoints(urls_to_check)
    
    # Save and display results
    results_file = discovery.save_discovery_results(results)
    discovery.print_summary(results)
    
    print(f"\n💾 Full results saved to: {results_file}")
    
    # Generate direct API test code
    if results['endpoints']:
        print("\n🔧 Generated code to test discovered endpoints:")
        print("-" * 50)
        
        for endpoint in list(results['endpoints'])[:5]:  # Show first 5
            print(f"""
# Test endpoint: {endpoint}
import requests
response = requests.get("{endpoint}")
if response.status_code == 200:
    data = response.json()
    print(f"Got {{len(data)}} items from {endpoint}")
            """)
    
    return results


if __name__ == "__main__":
    print("🕵️ UmpScorecards API Discovery Tool")
    print("=" * 40)
    
    try:
        results = asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Discovery interrupted by user")
    except Exception as e:
        logger.error(f"Discovery error: {e}")
        print(f"❌ Error: {e}")