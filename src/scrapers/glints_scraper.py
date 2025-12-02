import time
import logging
from typing import List, Dict, Any
from playwright.sync_api import sync_playwright
from src.scrapers.base_scraper import BaseScraper

class GlintsScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.base_url = "https://glints.com/id/opportunities/jobs/explore"

    def scrape(self, job_titles: List[str], locations: List[str], remote_only: bool) -> List[Dict[str, Any]]:
        all_jobs = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
            page = context.new_page()

            for title in job_titles:
                try:
                    keyword = title.replace(" ", "%20")
                    # Location handling for Glints is tricky via URL, usually defaults to country or specific IDs.
                    # We'll just use keyword for now and filter later if needed, or try to pass locationName
                    # remote_only might need specific filter ID
                    
                    search_url = f"{self.base_url}?keyword={keyword}"
                    if remote_only:
                        search_url += "&remote=true" # Hypothetical param, need to verify
                    
                    logging.info(f"Scraping Glints: {search_url}")
                    
                    page.goto(search_url, timeout=60000)
                    page.wait_for_selector(".JobCard-sc-", timeout=10000) # Partial class match might be needed
                    
                    # Glints classes are often generated (sc-...), so we might need more robust selectors
                    # Looking for common attributes
                    
                    job_cards = page.query_selector_all("div[class*='JobCard']")
                    
                    for card in job_cards:
                        try:
                            title_elem = card.query_selector("h3")
                            company_elem = card.query_selector("a[href*='/company/']")
                            location_elem = card.query_selector("div[class*='Location']")
                            link_elem = card.query_selector("a[href*='/opportunities/jobs/']")
                            
                            if title_elem and link_elem:
                                job = {
                                    "title": title_elem.inner_text().strip(),
                                    "company": company_elem.inner_text().strip() if company_elem else "Unknown",
                                    "location": location_elem.inner_text().strip() if location_elem else "Unknown",
                                    "url": "https://glints.com" + link_elem.get_attribute("href") if link_elem.get_attribute("href").startswith("/") else link_elem.get_attribute("href"),
                                    "source": "Glints",
                                    "description": "Description not scraped in list view"
                                }
                                all_jobs.append(job)
                        except Exception as e:
                            continue

                except Exception as e:
                    logging.error(f"Error scraping {title}: {e}")
            
            browser.close()
            
        return all_jobs
