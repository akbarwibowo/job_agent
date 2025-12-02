import os
import logging
from pymongo import MongoClient
from dotenv import load_dotenv
from typing import List, Dict, Any

load_dotenv()

class MongoDB:
    def __init__(self):
        self.uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
        self.db_name = os.getenv("MONGO_DB_NAME", "job_agent_db")
        try:
            self.client = MongoClient(self.uri)
            self.db = self.client[self.db_name]
            self.jobs_collection = self.db["jobs"]
            self.resumes_collection = self.db["resumes"]
            logging.info(f"Connected to MongoDB: {self.db_name}")
        except Exception as e:
            logging.error(f"Failed to connect to MongoDB: {e}")
            raise e

    def save_job(self, job_data: Dict[str, Any]):
        """Saves a single job to the database. Avoids duplicates based on URL."""
        try:
            # Use URL as unique identifier if possible
            query = {"url": job_data.get("url")}
            update = {"$set": job_data}
            self.jobs_collection.update_one(query, update, upsert=True)
            logging.info(f"Saved job: {job_data.get('title', 'Unknown')}")
        except Exception as e:
            logging.error(f"Error saving job: {e}")

    def save_jobs(self, jobs: List[Dict[str, Any]]):
        """Saves a list of jobs."""
        for job in jobs:
            self.save_job(job)

    def get_jobs(self, filter_query: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Retrieves jobs based on a filter."""
        if filter_query is None:
            filter_query = {}
        return list(self.jobs_collection.find(filter_query, {"_id": 0}))

    def save_resume(self, resume_data: Dict[str, Any]):
        """Saves a generated resume."""
        try:
            self.resumes_collection.insert_one(resume_data)
            logging.info("Saved resume.")
        except Exception as e:
            logging.error(f"Error saving resume: {e}")

    def get_resume(self, job_id: str) -> Dict[str, Any]:
        """Retrieves a resume for a specific job."""
        return self.resumes_collection.find_one({"job_id": job_id}, {"_id": 0})
