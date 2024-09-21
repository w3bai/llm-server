import asyncio
from firecrawl import FirecrawlApp
import os


class WebScraper:
    def __init__(self, base_url, max_depth=5, max_pages=300):
        self.base_url = base_url
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.firecrawl = FirecrawlApp(api_key=os.getenv("FIRECRAWL_API_KEY"))

    async def scrape_site(self):
        try:
            crawl_status = self.firecrawl.crawl_url(
                self.base_url,
                params={
                    "limit": self.max_pages,
                    "scrapeOptions": {"formats": ["markdown"]},
                },
            )
            return crawl_status
        except Exception as e:
            print(f"An error occurred during the crawl: {e}")
            return None

    async def get_scraped_data(self, id_or_url):
        if id_or_url.startswith("http"):
            # It's a next URL
            return self.firecrawl.get(id_or_url)
        else:
            # It's a crawl ID
            return self.firecrawl.get_crawl_status(id_or_url)


if __name__ == "__main__":
    scraper = WebScraper("https://docs.royco.org/")
    loop = asyncio.get_event_loop()
    crawl_status = loop.run_until_complete(scraper.scrape_site())
    if crawl_status:
        print(crawl_status)
    else:
        print("Crawl job failed or was stopped.")
