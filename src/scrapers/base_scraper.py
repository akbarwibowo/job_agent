import asyncio
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from playwright.async_api import async_playwright, BrowserContext
from dotenv import load_dotenv, find_dotenv
from src.scrapers.base_scraper import BaseScraper
from bs4 import BeautifulSoup

load_dotenv(find_dotenv())

class BaseScraper(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def scrape(self, job_titles: List[str], locations: List[str], remote_only: bool) -> List[Dict[str, Any]]:
        """
        Scrapes jobs based on the provided criteria.
        
        Args:
            job_titles: List of job titles to search for.
            locations: List of locations to search in.
            remote_only: Boolean indicating if only remote jobs should be scraped.
            
        Returns:
            A list of dictionaries, where each dictionary represents a job.
            Expected keys: title, company, location, description, url, source, date_posted.
        """
        pass


class Scraper(ABC):
    def __init__(
            self, 
            base_url: str, 
            platform_name: str, 
            search_page_url: str, 
            job_desc_class: str, 
            search_splitter: str,
            search_results_class: str,
            job_title_class: str,
            company_name_class: str,
            location_class: str,
            date_posted_class: str | None = None,
            pagination_next_button_class: str | None = None
            ):
        self.base_url = base_url
        self.platform_name = platform_name
        self.search_page_url = search_page_url
        self.job_desc_class = job_desc_class
        self.search_splitter = search_splitter
        self.search_results_class = search_results_class
        self.job_title_class = job_title_class
        self.company_name_class = company_name_class
        self.location_class = location_class
        self.date_posted_class = date_posted_class
        self.pagination_next_button_class = pagination_next_button_class

    def scrape(self, job_titles: List[str], locations: List[str], remote_only: bool, limit: int | None = None) -> List[Dict[str, Any]]:
        """
        Synchronous wrapper for the async scraping logic.
        """
        return asyncio.run(self.scrape_async(job_titles, locations, remote_only, limit))
    

    @abstractmethod
    async def login(self, page):
        """
        Abstract method for logging into the platform.
        """
        pass


    async def scrape_async(self, job_titles: List[str], locations: List[str], remote_only: bool, limit: int | None = None) -> List[Dict[str, Any]]:
        all_jobs = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
            page = await context.new_page()

            try:
                await self.login(page)
            except Exception as e:
                logging.error(f"Login failed: {e}")
                await browser.close()
                return all_jobs
            
            queue = asyncio.Queue()
            seen_all_urls = set()

            consumers = [asyncio.create_task(self.worker(context, queue, all_jobs)) for _ in range(5)]

            limit_per_job = limit // len(job_titles) if limit is not None else 100
            # TODO improve efficiency
            for title in job_titles:
                for location in locations:
                    try:
                        title_search_keyword = title.replace(" ", self.search_splitter)
                        location_search_keyword = location.replace(" ", self.search_splitter)
                        search_url = self.search_page_url.format(job_title=title_search_keyword, location=location_search_keyword)
                        await page.goto(search_url, timeout=60000)

                        try:
                            await page.wait_for_selector(self.search_results_class, timeout=10000)
                        except Exception as e:
                            logging.error(f"Search results did not load properly: {e}")
                        
                        last_height = await page.evaluate("document.body.scrollHeight")

                        seen_job_urls = set()
                        while True:
                            job_lists = await page.query_selector_all(self.search_results_class)
                            new_jobs_found_in_this_batch = False

                            for job_list in job_lists:
                                try:
                                    job_href = await job_list.get_attribute("href")
                                    job_url = self.base_url + job_href if job_href and job_href.startswith("/") else job_href
                                    
                                    if job_url in seen_all_urls:
                                        continue
                                    
                                    seen_job_urls.add(job_url)
                                    new_jobs_found_in_this_batch = True

                                    title_element = await job_list.query_selector(self.job_title_class)
                                    company_element = await job_list.query_selector(self.company_name_class)
                                    location_element = await job_list.query_selector(self.location_class)
                                    date_posted_element = await job_list.query_selector(self.date_posted_class) if self.date_posted_class else None

                                    job_info = {
                                        "title": (await title_element.inner_text()).strip() if title_element else "N/A",
                                        "company": (await company_element.inner_text()).strip() if company_element else "N/A",
                                        "location": (await location_element.inner_text()).strip() if location_element else "N/A",
                                        "url": job_url,
                                        "source": self.platform_name,
                                        "description": "",
                                        "date_posted": (await date_posted_element.inner_text()).strip() if date_posted_element else "N/A"
                                    }
                                    
                                    await queue.put(job_info)

                                    if len(seen_job_urls) >= limit_per_job:
                                        seen_all_urls.update(seen_job_urls)
                                        break
                                except Exception as e:
                                    logging.error(f"Error processing job listing: {e}")
                                    continue
                            
                            if len(seen_job_urls) >= limit_per_job:
                                break

                            if not self.pagination_next_button_class:
                                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                                await page.wait_for_timeout(2000)

                                new_height = await page.evaluate("document.body.scrollHeight")
                                if new_height == last_height and not new_jobs_found_in_this_batch:
                                    logging.info("No more new jobs found, ending search.")
                                    break
                                last_height = new_height
                            else:
                                # TODO: be caution with this loop
                                next_button = await page.query_selector(self.pagination_next_button_class)
                                if next_button:
                                    await next_button.click()
                                    await page.wait_for_timeout(3000)
                                else:
                                    while True:
                                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                                        await page.wait_for_timeout(2000)

                                        new_height = await page.evaluate("document.body.scrollHeight")
                                        if new_height == last_height and not new_jobs_found_in_this_batch:
                                            logging.info("No more new jobs found, ending search.")
                                            break
                                        last_height = new_height
                                        next_button = await page.query_selector(self.pagination_next_button_class)
                                        if next_button:
                                            await next_button.click()
                                            await page.wait_for_timeout(3000)
                                            break
                    except Exception as e:
                        logging.error(f"Error during search for title '{title}' and location '{location}': {e}")
            await queue.join()
            for c in consumers:
                c.cancel()
            await browser.close()
            return all_jobs

    
    async def worker(self, context: BrowserContext, queue: asyncio.Queue, all_jobs):
        while True:
            job = await queue.get()
            try:
                job_url = job['url']
                job_description = "Description not found"

                page = None
                try:
                    page = await context.new_page()
                    await page.goto(job_url, timeout=60000)
                    try:
                        await page.wait_for_selector("body", timeout=10000)
                    except:
                        pass

                    content = await page.content()
                    soup = BeautifulSoup(content, soup = BeautifulSoup(content, "html.parser"))

                    job_desc_element = soup.find("div", attrs=({"class": self.job_desc_class}))

                    if job_desc_element:
                        job_description = job_desc_element.get_text(separator="\n").strip()
                    
                    if page is not None:
                        await page.close()
                except Exception as e:
                    logging.error(f"worker error for {job_url}: {e}")
                    if page is not None:
                        await page.close()
                job['description'] = job_description
                all_jobs.append(job)
            except Exception as e:
                logging.error(f"worker critical error: {e}")
            finally:
                queue.task_done()
