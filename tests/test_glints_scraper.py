import unittest
import os
from dotenv import load_dotenv
from src.scrapers.glints_scraper import GlintsScraper

load_dotenv()

class TestGlintsScraper(unittest.TestCase):
    def setUp(self):
        self.scraper = GlintsScraper()

    def test_scrape_ai_engineer(self):
        # Ensure credentials are present (skip if not, or fail?)
        if not os.getenv("GLINTS_EMAIL") or not os.getenv("GLINTS_PASSWORD"):
            print("Skipping test: GLINTS_EMAIL or GLINTS_PASSWORD not set.")
            return

        titles = ["AI Engineer"]
        locations = ["Jakarta"] # Location is hardcoded in scraper for now, but passing it anyway
        remote_only = False
        
        jobs = self.scraper.scrape(titles, locations, remote_only)
        
        print(f"Found {len(jobs)} jobs.")
        for job in jobs[:3]:
            print(job)
            
        self.assertTrue(len(jobs) > 0, "Should find at least one job")
        self.assertIn("title", jobs[0])
        self.assertIn("company", jobs[0])
        self.assertIn("url", jobs[0])

if __name__ == '__main__':
    unittest.main()
