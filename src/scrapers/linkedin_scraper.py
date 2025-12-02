import time
import logging
from typing import List, Dict, Any
from playwright.sync_api import sync_playwright
from src.scrapers.base_scraper import BaseScraper

class LinkedInScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.linkedin.com/jobs/search"

    def scrape(self, job_titles: List[str], locations: List[str], remote_only: bool) -> List[Dict[str, Any]]:
        all_jobs = []
        
        with sync_playwright() as p:
            # Launch browser (headless=False for debugging/visibility if needed, but True for production)
            # We use a user agent to mimic a real browser
            browser = p.chromium.launch(headless=True) 
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
            page = context.new_page()

            for title in job_titles:
                for location in locations:
                    try:
                        keywords = title.replace(" ", "%20")
                        loc = location.replace(" ", "%20")
                        f_remote = "&f_WT=2" if remote_only else ""
                        
                        search_url = f"{self.base_url}?keywords={keywords}&location={loc}{f_remote}"
                        logging.info(f"Scraping LinkedIn: {search_url}")
                        
                        page.goto(search_url, timeout=60000)
                        page.wait_for_selector(".jobs-search__results-list", timeout=10000)
                        
                        # Scroll to load more jobs (basic implementation)
                        for _ in range(3):
                            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                            time.sleep(2)

                        job_cards = page.query_selector_all("li")
                        
                        for card in job_cards:
                            try:
                                # Extract basic info from the card
                                title_elem = card.query_selector(".base-search-card__title")
                                company_elem = card.query_selector(".base-search-card__subtitle")
                                location_elem = card.query_selector(".job-search-card__location")
                                link_elem = card.query_selector("a.base-card__full-link")
                                time_elem = card.query_selector("time")

                                if title_elem and link_elem:
                                    job = {
                                        "title": title_elem.inner_text().strip(),
                                        "company": company_elem.inner_text().strip() if company_elem else "Unknown",
                                        "location": location_elem.inner_text().strip() if location_elem else "Unknown",
                                        "url": link_elem.get_attribute("href"),
                                        "source": "LinkedIn",
                                        "date_posted": time_elem.get_attribute("datetime") if time_elem else None,
                                        "description": "Description not scraped in list view" # Would need to visit page to get full desc
                                    }
                                    all_jobs.append(job)
                            except Exception as e:
                                continue # Skip card if parsing fails

                    except Exception as e:
                        logging.error(f"Error scraping {title} in {location}: {e}")
            
            browser.close()
            
        return all_jobs

if __name__ == "__main__":
    # Test run
    logging.basicConfig(level=logging.INFO)
    scraper = LinkedInScraper()
    jobs = scraper.scrape(["Python Developer"], ["United States"], True)
    print(f"Found {len(jobs)} jobs")
    for job in jobs[:5]:
        print(job)
