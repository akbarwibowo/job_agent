from abc import ABC, abstractmethod
from typing import List, Dict, Any

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
