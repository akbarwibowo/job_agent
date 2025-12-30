import asyncio
import logging
import os
from typing import List, Dict, Any
from playwright.async_api import async_playwright
from dotenv import load_dotenv, find_dotenv
from src.scrapers.base_scraper import BaseScraper
from bs4 import BeautifulSoup

load_dotenv(find_dotenv())

class GlintsScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.base_url = "https://glints.com/id/opportunities/jobs/explore"

    def scrape(self, job_titles: List[str], locations: List[str], remote_only: bool, limit: int | None = None) -> List[Dict[str, Any]]:
        """
        Synchronous wrapper for the async scraping logic.
        """
        return asyncio.run(self.scrape_async(job_titles, locations, remote_only, limit))

    async def scrape_async(self, job_titles: List[str], locations: List[str], remote_only: bool, limit: int | None = None) -> List[Dict[str, Any]]:
        all_jobs = []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
            page = await context.new_page()

            # Login Flow
            try:
                logging.info("Starting Glints Login...")
                await page.goto(self.base_url, timeout=60000)
                
                # 2. Click Login Button
                try:
                    await page.click("button:has-text('Masuk')", timeout=5000)
                except:
                    try:
                        await page.click("button:has-text('Login')", timeout=5000)
                    except:
                        await page.click('//*[@id="__next"]/div[1]/div[2]/div[1]/div/div[2]/nav/div[4]/div[4]/button')
                
                # 3. Click "Login with Email" link
                await page.wait_for_selector("div[role='dialog']", timeout=5000)
                await page.click("a:has-text('Email')")
                
                # 4. Input Email
                email = os.getenv("GLINTS_EMAIL")
                if not email:
                    raise ValueError("GLINTS_EMAIL not found in .env")
                await page.fill('//*[@id="login-form-email"]', email)
                
                # 5. Input Password
                password = os.getenv("GLINTS_PASSWORD")
                if not password:
                    raise ValueError("GLINTS_PASSWORD not found in .env")
                await page.fill('//*[@id="login-form-password"]', password)
                
                # 6. Click Submit Button
                await page.click('//*[@id="login-signup-modal"]/section/div[2]/div/div/div[1]/form/div[4]/button')
                
                logging.info("Glints Login Submitted. Waiting for navigation...")
                await page.wait_for_timeout(5000)
                
            except Exception as e:
                logging.error(f"Glints Login Failed: {e}")
                pass

            queue = asyncio.Queue()
            seen_all_urls = set()
            
            # Start consumers (workers)
            # 5 concurrent workers
            consumers = [asyncio.create_task(self.worker(context, queue, all_jobs)) for _ in range(5)]
            
            limit_per_job = limit // len(job_titles) if limit is not None else 100
            for title in job_titles:
                try:
                    keyword = title.replace(" ", "+")
                    search_url = f"https://glints.com/id/opportunities/jobs/explore?keyword={keyword}&country=ID&locationName=All+Cities%2FProvinces&lowestLocationLevel=1"
                    
                    if remote_only:
                        search_url += "&remote=true" 
                    
                    logging.info(f"Scraping Glints: {search_url}")
                    
                    await page.goto(search_url, timeout=60000)
                    
                    try:
                        await page.wait_for_selector("div[class*='CompactOpportunityCard']", timeout=10000)
                    except:
                        logging.warning("Glints job cards not found.")

                    last_height = await page.evaluate("document.body.scrollHeight")

                    seen_job_urls = set()
                    while True:
                        # Re-query cards
                        job_cards = await page.query_selector_all("div[class*='CompactOpportunityCard']")
                        if not job_cards:
                            job_cards = await page.query_selector_all("a[href*='/opportunities/jobs/']")
                        
                        new_jobs_found_in_this_batch = False
                        
                        for card in job_cards:
                            try:
                                # Extract basic info
                                card_href = await card.get_attribute("href")
                                if not card_href:
                                    link_elem = await card.query_selector("h2 a") or await card.query_selector("a[href*='/opportunities/jobs/']")
                                    if link_elem:
                                        card_href = await link_elem.get_attribute("href")
                                
                                if not card_href:
                                    continue
                                    
                                job_url = "https://glints.com" + card_href if card_href.startswith("/") else card_href
                                
                                if job_url in seen_job_urls:
                                    continue
                                
                                seen_job_urls.add(job_url)
                                new_jobs_found_in_this_batch = True
                                
                                # Extract details for the job object
                                title_elem = await card.query_selector("h2 a")
                                company_elem = await card.query_selector("a[href*='/companies/']")
                                location_elem = await card.query_selector("div[class*='CardJobLocation']")
                                
                                job_basic = {
                                    "title": (await title_elem.inner_text()).strip() if title_elem else (await card.inner_text()).split("\n")[0],
                                    "company": (await company_elem.inner_text()).strip() if company_elem else "Unknown",
                                    "location": (await location_elem.inner_text()).strip() if location_elem else "Unknown",
                                    "url": job_url,
                                    "source": "Glints",
                                    "description": "Description not scraped" # Will be updated by worker
                                }
                                
                                # Put into queue for processing
                                await queue.put(job_basic)
                                
                                if limit_per_job and len(seen_job_urls) >= limit_per_job:
                                    seen_all_urls.update(seen_job_urls)
                                    break
                            except Exception as e:
                                logging.error(f"Error processing card: {e}")
                                continue
                        
                        if limit_per_job and len(seen_job_urls) >= limit_per_job:
                            break
                            
                        # Scroll down
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        await page.wait_for_timeout(2000)
                        
                        # Check if we reached bottom
                        new_height = await page.evaluate("document.body.scrollHeight")
                        if new_height == last_height and not new_jobs_found_in_this_batch:
                            logging.info("Reached end of infinite scroll.")
                            break
                        last_height = new_height
                        
                except Exception as e:
                    logging.error(f"Error scraping {title}: {e}")

            # Wait for all jobs in queue to be processed
            await queue.join()
            
            # Cancel consumers
            for c in consumers:
                c.cancel()
            
            await browser.close()
            
            # If limit was applied, trim the result (though seen_urls check should handle it mostly)
            if limit:
                return all_jobs[:limit]
            return all_jobs

    async def worker(self, context, queue, all_jobs):
        while True:
            job = await queue.get()
            try:
                job_url = job['url']
                description = "Description not scraped"
                
                page = None
                try:
                    page = await context.new_page()
                    await page.goto(job_url, timeout=60000)
                    try:
                        await page.wait_for_load_state("domcontentloaded", timeout=10000)
                    except:
                        pass # Proceed even if timeout, content might be there
                    
                    content = await page.content()
                    soup = BeautifulSoup(content, "html.parser")
                    
                    main_content = soup.find("main") or soup.find("div", {"id": "__next"})
                    if main_content:
                        text_content = main_content.get_text(separator="\n")
                        if "Deskripsi pekerjaan" in text_content and "Tentang Perusahaan" in text_content:
                            start = text_content.find("Deskripsi pekerjaan")
                            end = text_content.find("Tentang Perusahaan")
                            if start != -1 and end != -1 and end > start:
                                description = text_content[start:end].strip()
                            else:
                                description = text_content.split("Tentang Perusahaan")[0].strip()
                        elif "Tentang Perusahaan" in text_content:
                            description = text_content.split("Tentang Perusahaan")[0].strip()
                        else:
                            description = text_content[:2000]
                    
                    if page is not None:
                        await page.close()
                except Exception as e:
                    logging.error(f"Worker error for {job_url}: {e}")
                    if page is not None:
                        await page.close()
                
                job['description'] = description
                all_jobs.append(job)
                
            except Exception as e:
                logging.error(f"Worker critical error: {e}")
            finally:
                queue.task_done()
