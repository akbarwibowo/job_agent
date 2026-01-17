import asyncio
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, NoReturn
from playwright.async_api import async_playwright, BrowserContext
from dotenv import load_dotenv, find_dotenv
from bs4 import BeautifulSoup, Tag
from playwright.async_api._generated import Browser, ElementHandle, Page
from rpds import Queue

load_dotenv(find_dotenv())

SCROLL_HEIGHT_SCRIPT = "document.body.scrollHeight"

class Scraper(ABC):
    # set the common attributes for all scrapers
    """
    Base class for job scrapers.
    Attributes:
        base_url (str): The base URL of the job platform.
        platform_name (str): The name of the job platform.
        search_page_url (str): The URL template for job searches.
        job_desc_class (str): The CSS class for job description elements.
        search_splitter (str): The character used to replace spaces in search keywords.
        search_results_class (str): The CSS class for job listing elements in search results.
        job_title_class (str): The CSS class for job title elements.
        company_name_class (str): The CSS class for company name elements.
        location_class (str): The CSS class for job location elements.
        date_posted_class (str | None): The CSS class for the date posted elements.
        pagination_next_button_class (str | None): The CSS class for the pagination next button elements.
    """
    
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
            ) -> None:
        self.base_url: str = base_url
        self.platform_name: str = platform_name
        self.search_page_url: str = search_page_url
        self.job_desc_class: str = job_desc_class
        self.search_splitter: str = search_splitter
        self.search_results_class: str = search_results_class
        self.job_title_class: str = job_title_class
        self.company_name_class: str = company_name_class
        self.location_class: str = location_class
        self.date_posted_class: str | None = date_posted_class
        self.pagination_next_button_class: str | None = pagination_next_button_class


    def scrape(self, job_titles: List[str], locations: List[str], remote_only: bool, limit: int | None = None) -> List[Dict[str, Any]]:
        """
        Synchronous wrapper for the async scraping logic.
        Args:
            job_titles (List[str]): List of job titles to search for.
            locations (List[str]): List of locations to search in.
            remote_only (bool): Whether to filter for remote jobs only.
            limit (int | None): Maximum number of job listings to scrape.
        Returns:
            (List[Dict[str, Any]]): List of scraped job listings. Dict scheme:
                {
                    "title": str,
                    "company": str,
                    "location": str,
                    "url": str,
                    "source": str,
                    "description": str,
                    "date_posted": str
                }
        """
        return asyncio.run(self.scrape_async(job_titles, locations, remote_only, limit))
    

    @abstractmethod
    async def login(self, page) -> Page:
        """
        Abstract method for logging into the platform.
        Args:
            page (Page): Playwright page object.
        Returns:
            (Page): Authenticated Playwright page object.
        """
        pass


    async def scrape_async(self, job_titles: List[str], locations: List[str], remote_only: bool, limit: int | None = None) -> List[Dict[str, Any]]:
        """
        Asynchronous method to scrape job listings.
        Args:
            job_titles (List[str]): List of job titles to search for.
            locations (List[str]): List of locations to search in.
            remote_only (bool): Whether to filter for remote jobs only.
            limit (int | None): Maximum number of job listings to scrape.
        Returns:
            (List[Dict[str, Any]]): List of scraped job listings. Dict scheme:
                {
                    "title": str,
                    "company": str,
                    "location": str,
                    "url": str,
                    "source": str,
                    "description": str,
                    "date_posted": str
                }
        """
        all_jobs: List[Dict[str, Any]] = []

        async with async_playwright() as p:
            browser: Browser = await p.chromium.launch(headless=False)
            context: BrowserContext = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
            page: Page = await context.new_page()

            try:
                await self.login(page)
            except Exception as e:
                logging.error(f"Login failed: {e}")
                await browser.close()
                return all_jobs

            queue: asyncio.Queue[Any] = asyncio.Queue()
            seen_all_urls: set[Any] = set()

            consumers: List[asyncio.Task[NoReturn]] = [asyncio.create_task(self.scrape_description(context, queue, all_jobs)) for _ in range(5)]

            limit_per_job: int = limit // len(job_titles) if limit and job_titles is not None else 100
            # TODO improve efficiency
            for title in job_titles:
                for location in locations:
                    try:
                        title_search_keyword: str = title.replace(" ", self.search_splitter)
                        location_search_keyword: str = location.replace(" ", self.search_splitter)
                        search_url: str = self.search_page_url.format(job_title=title_search_keyword, location=location_search_keyword)
                        await page.goto(search_url, timeout=60000)

                        try:
                            await page.wait_for_selector(self.search_results_class, timeout=10000)
                        except Exception as e:
                            logging.error(f"Search results did not load properly: {e}")
                        
                        last_height: str = await page.evaluate(SCROLL_HEIGHT_SCRIPT)
                        seen_job_urls: set[str | None] = set()
                        while True:
                            job_lists: List[ElementHandle] = await page.query_selector_all(self.search_results_class)
                            new_jobs_found_in_this_batch = False

                            for job_list in job_lists:
                                try:
                                    job_href: str | None= await job_list.get_attribute("href")
                                    job_url: str | None = self.base_url + job_href if job_href and job_href.startswith("/") else job_href
                                    
                                    if job_url in seen_all_urls:
                                        continue
                                    
                                    seen_job_urls.add(job_url)
                                    new_jobs_found_in_this_batch = True

                                    title_element: ElementHandle | None = await job_list.query_selector(self.job_title_class)
                                    company_element: ElementHandle | None = await job_list.query_selector(self.company_name_class)
                                    location_element: ElementHandle | None = await job_list.query_selector(self.location_class)
                                    date_posted_element: ElementHandle | None = await job_list.query_selector(self.date_posted_class) if self.date_posted_class else None

                                    job_info: dict = {
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

                                new_height: Any = await page.evaluate("document.body.scrollHeight")
                                if new_height == last_height and not new_jobs_found_in_this_batch:
                                    logging.info("No more new jobs found, ending search.")
                                    break
                                last_height = new_height
                            else:
                                # flow if there is pagination button
                                # TODO: be caution with this loop
                                next_button: ElementHandle | None = await page.query_selector(self.pagination_next_button_class)
                                if next_button:
                                    # click the next button if available
                                    await next_button.click()
                                    await page.wait_for_timeout(3000)
                                else:
                                    # scroll down to get the next button if not seen yet
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
            
            # Wait for all consumers to be cancelled
            try:
                await asyncio.gather(*consumers)
            except asyncio.CancelledError:
                logging.info("All consumer tasks have been cancelled")
                
            await browser.close()
            return all_jobs

    
    async def scrape_description(self, context: BrowserContext, queue: asyncio.Queue, all_jobs) -> NoReturn:
        """
        Worker coroutine to process job descriptions.
        Args:
            context (BrowserContext): The browser context to create new pages.
            queue (asyncio.Queue): Queue containing jobs to process.
            all_jobs (list): Shared list to store processed job descriptions.
        """
        while True:
            job: dict = await queue.get()
            try:
                job_url: str = job['url']
                job_description: str = "Description not found"

                page: Page | None = None
                try:
                    page = await context.new_page()
                    await page.goto(job_url, timeout=60000)
                    try:
                        await page.wait_for_selector("body", timeout=10000)
                    except:
                        pass

                    content: str = await page.content()
                    soup = BeautifulSoup(content, "html.parser")
# TODO check for the bs4 selector
                    selector: str = self.job_desc_class
                    if selector and not selector.startswith((".", "#", "[", ":")):
                        selector = f".{selector}"
                    job_desc_element: Tag | None = soup.select_one(selector) if selector else None

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
