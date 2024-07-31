import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urldefrag
from aiohttp import ClientError, TCPConnector
from robotexclusionrulesparser import RobotExclusionRulesParser
import logging
from trafilatura import extract
from collections import deque
import time
import ssl

class WebScraper:
    def __init__(self, base_url, max_depth=5, max_pages=300, delay=0.1, verify_ssl=True):
        self.base_url = base_url
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.delay = delay
        self.verify_ssl = verify_ssl
        self.visited_urls = set()
        self.robots_parser = RobotExclusionRulesParser()
        self.logger = logging.getLogger(__name__)
        self.last_request_time = {}

    async def setup_robots_parser(self):
        robots_url = urljoin(self.base_url, "/robots.txt")
        try:
            async with self.create_session() as session:
                async with session.get(robots_url) as response:
                    robots_content = await response.text()
                    self.robots_parser.parse(robots_content)
        except ClientError as e:
            self.logger.warning(f"Could not fetch robots.txt: {e}")

    def create_session(self):
        if not self.verify_ssl:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            connector = TCPConnector(ssl=ssl_context)
            return aiohttp.ClientSession(connector=connector)
        else:
            return aiohttp.ClientSession()

    def is_allowed(self, url):
        return self.robots_parser.is_allowed("*", url)

    async def scrape_page(self, url, depth):
        if not self.is_allowed(url):
            self.logger.info(f"Skipping {url} as per robots.txt rules")
            return None

        current_time = time.time()
        if url in self.last_request_time:
            time_since_last_request = current_time - self.last_request_time[url]
            if time_since_last_request < self.delay:
                await asyncio.sleep(self.delay - time_since_last_request)
        self.last_request_time[url] = current_time

        try:
            async with self.create_session() as session:
                async with session.get(url) as response:
                    content = await response.text()
                    extracted_content = extract(content)
                    if not extracted_content:
                        self.logger.warning(f"No content extracted from {url}")
                        extracted_content = content  # Fallback to raw content

                    soup = BeautifulSoup(content, 'html.parser')
                    title = soup.title.string if soup.title else ''
                    
                    return {
                        'url': url,
                        'title': title,
                        'content': extracted_content,
                        'raw_html': content,
                        'depth': depth
                    }
        except ClientError as e:
            self.logger.error(f"Error scraping {url}: {e}")
            return None

    def get_links(self, url, content):
        soup = BeautifulSoup(content, 'html.parser')
        links = set()
        for link in soup.find_all('a', href=True):
            href = link['href']
            full_url = urljoin(url, href)
            if self.is_valid_url(full_url):
                links.add(full_url)
        self.logger.info(f"Found {len(links)} links on {url}")
        return links

    def is_valid_url(self, url):
        parsed_url = urlparse(url)
        base_parsed = urlparse(self.base_url)
        
        # Remove the fragment (everything after #) from the URL
        url_without_fragment, _ = urldefrag(url)
        
        return (
            parsed_url.netloc.endswith(base_parsed.netloc) and 
            parsed_url.scheme in ('http', 'https') and
            url_without_fragment not in self.visited_urls
        )
    async def scrape_site(self):
        await self.setup_robots_parser()
        to_visit = deque([(self.base_url, 0)])  # (url, depth)
        scraped_data = {}

        while to_visit and len(scraped_data) < self.max_pages:
            url, depth = to_visit.popleft()
            if url in self.visited_urls or depth > self.max_depth:
                continue

            self.visited_urls.add(url)
            self.logger.info(f"Scraping: {url} at depth {depth}")

            page_data = await self.scrape_page(url, depth)
            if page_data:
                scraped_data[url] = page_data
                self.logger.info(f"Successfully scraped {url}")

                if depth < self.max_depth:
                    new_links = self.get_links(url, page_data['raw_html'])
                    self.logger.info(f"Found {len(new_links)} new links on {url}")
                    for link in new_links:
                        url_without_fragment, _ = urldefrag(link)
                        if url_without_fragment not in self.visited_urls:
                            to_visit.append((url_without_fragment, depth + 1))
                            self.logger.info(f"Added {url_without_fragment} to visit queue at depth {depth + 1}")

            self.logger.info(f"Queue size: {len(to_visit)}, Scraped so far: {len(scraped_data)}")

        self.logger.info(f"Finished scraping. Visited {len(self.visited_urls)} URLs, scraped {len(scraped_data)} pages.")
        return scraped_data

# for testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    scraper = WebScraper("https://docs.zaros.fi/overview", verify_ssl=False)
    data = asyncio.run(scraper.scrape_site())
    print(f"Scraped {len(data)} pages")