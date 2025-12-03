import time
import logging
from typing import List, Dict, Any
from playwright.sync_api import sync_playwright
import os
from dotenv import load_dotenv
from src.scrapers.base_scraper import BaseScraper

load_dotenv()

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

            # Login Flow
            try:
                logging.info("Starting Glints Login...")
                page.goto(self.base_url, timeout=60000)
                
                # 2. Click Login Button - Try multiple selectors
                try:
                    page.click("button:has-text('Masuk')", timeout=5000)
                except:
                    try:
                        page.click("button:has-text('Login')", timeout=5000)
                    except:
                        # Try the specific class if text fails
                        page.click('//*[@id="__next"]/div[1]/div[2]/div[1]/div/div[2]/nav/div[4]/div[4]/button')
                
                # 3. Click "Login with Email" link
                # Wait for modal to appear
                page.wait_for_selector("div[role='dialog']", timeout=5000)
                page.click("a:has-text('Email')") # More robust than XPath
                
                # 4. Input Email
                email = os.getenv("GLINTS_EMAIL")
                if not email:
                    raise ValueError("GLINTS_EMAIL not found in .env")
                page.fill('//*[@id="login-form-email"]', email)
                
                # 5. Input Password
                password = os.getenv("GLINTS_PASSWORD")
                if not password:
                    raise ValueError("GLINTS_PASSWORD not found in .env")
                page.fill('//*[@id="login-form-password"]', password)
                
                # 6. Click Submit Button
                page.click('//*[@id="login-signup-modal"]/section/div[2]/div/div/div[1]/form/div[4]/button')
                
                logging.info("Glints Login Submitted. Waiting for navigation...")
                page.wait_for_timeout(5000) # Wait for login to complete
                
            except Exception as e:
                logging.error(f"Glints Login Failed: {e}")
                # Continue scraping even if login fails? Or return? 
                # For now, we'll try to continue as some jobs might be visible without login
                pass

            for title in job_titles:
                try:
                    keyword = title.replace(" ", "+")
                    # Using the user-specified base URL format
                    # Defaulting to Indonesia (ID) and All Cities for now as per the example
                    search_url = f"https://glints.com/id/opportunities/jobs/explore?keyword={keyword}&country=ID&locationName=All+Cities%2FProvinces&lowestLocationLevel=1"
                    
                    if remote_only:
                        search_url += "&remote=true" 
                    
                    logging.info(f"Scraping Glints: {search_url}")
                    
                    page.goto(search_url, timeout=60000)
                    # Wait for job cards
                    try:
                        page.wait_for_selector("div[class*='CompactOpportunityCard']", timeout=10000)
                    except:
                        logging.warning("Glints job cards not found.")
                    
                    # Select all job cards - trying a broader selector if specific one fails
                    job_cards = page.query_selector_all("div[class*='CompactOpportunityCard']")
                    if not job_cards:
                        logging.warning("No job cards found with primary selector. Trying generic 'a' tags...")
                        job_cards = page.query_selector_all("a[href*='/opportunities/jobs/']")

                    if not job_cards:
                        logging.error("No jobs found!")
                    
                    for card in job_cards:
                        try:
                            # If card is just the link (fallback)
                            if card.get_attribute("href") and "/opportunities/jobs/" in card.get_attribute("href"):
                                title = card.inner_text().split("\n")[0] # Heuristic
                                url = "https://glints.com" + card.get_attribute("href") if card.get_attribute("href").startswith("/") else card.get_attribute("href")
                                job = {
                                    "title": title,
                                    "company": "Unknown", # Hard to get from just link
                                    "location": "Unknown",
                                    "url": url,
                                    "source": "Glints",
                                    "description": "Description not scraped"
                                }
                                all_jobs.append(job)
                                continue

                            # Extract details using updated selectors based on HTML dump
                            # Title is in h2 > a
                            title_elem = card.query_selector("h2 a")
                            
                            # Company link contains /companies/ (plural)
                            company_elem = card.query_selector("a[href*='/companies/']")
                            
                            # Location wrapper
                            location_elem = card.query_selector("div[class*='CardJobLocation']")
                            
                            # Link is the same as title link
                            link_elem = title_elem
                            
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
                            else:
                                pass # Skip incomplete cards
                        except Exception as e:
                            continue

                except Exception as e:
                    logging.error(f"Error scraping {title}: {e}")
            
            browser.close()
            
        return all_jobs
