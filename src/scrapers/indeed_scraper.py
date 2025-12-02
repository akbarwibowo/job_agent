import time
import logging
from typing import List, Dict, Any
from playwright.sync_api import sync_playwright
from src.scrapers.base_scraper import BaseScraper

class IndeedScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.indeed.com/jobs"

    def scrape(self, job_titles: List[str], locations: List[str], remote_only: bool) -> List[Dict[str, Any]]:
        all_jobs = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
            page = context.new_page()

            for title in job_titles:
                for location in locations:
                    try:
                        q = title.replace(" ", "+")
                        l = location.replace(" ", "+")
                        sc = "0kf%3Aattr%28DSQF7%29%3B" if remote_only else "" # Indeed remote filter param (approximate)
                        
                        search_url = f"{self.base_url}?q={q}&l={l}&{sc}"
                        logging.info(f"Scraping Indeed: {search_url}")
                        
                        page.goto(search_url, timeout=60000)
                        try:
                            page.wait_for_selector(".jobsearch-ResultsList", timeout=10000)
                        except:
                            logging.warning("Indeed results list not found, might be blocked or empty.")
                            continue

                        job_cards = page.query_selector_all(".job_seen_beacon")
                        
                        for card in job_cards:
                            try:
                                title_elem = card.query_selector("h2.jobTitle span")
                                company_elem = card.query_selector(".companyName") or card.query_selector('[data-testid="company-name"]')
                                location_elem = card.query_selector(".companyLocation") or card.query_selector('[data-testid="text-location"]')
                                link_elem = card.query_selector("a.jcs-JobTitle")
                                
                                if title_elem and link_elem:
                                    job = {
                                        "title": title_elem.inner_text().strip(),
                                        "company": company_elem.inner_text().strip() if company_elem else "Unknown",
                                        "location": location_elem.inner_text().strip() if location_elem else "Unknown",
                                        "url": "https://www.indeed.com" + link_elem.get_attribute("href") if link_elem.get_attribute("href").startswith("/") else link_elem.get_attribute("href"),
                                        "source": "Indeed",
                                        "description": "Description not scraped in list view"
                                    }
                                    all_jobs.append(job)
                            except Exception as e:
                                continue

                    except Exception as e:
                        logging.error(f"Error scraping {title} in {location}: {e}")
            
            browser.close()
            
        return all_jobs
