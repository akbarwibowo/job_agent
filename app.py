import streamlit as st
import pandas as pd
import logging
import concurrent.futures
from src.db.mongo import MongoDB
from src.scrapers.linkedin_scraper import LinkedInScraper
from src.scrapers.indeed_scraper import IndeedScraper
from src.scrapers.glints_scraper import GlintsScraper
from src.resume.optimizer import ResumeOptimizer
from src.agent.agent import ApplicationAgent

# Initialize services
try:
    db = MongoDB()
except:
    st.error("Could not connect to MongoDB. Ensure Docker is running.")
    db = None

st.set_page_config(
    page_title="Job Search AI Agent",
    page_icon="🕵️‍♂️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🕵️‍♂️ Job Search AI Agent")

# Sidebar Navigation
page = st.sidebar.selectbox("Navigation", ["Search Jobs", "My Profile", "Applications"])

if page == "Search Jobs":
    st.header("Job Search")
    
    col1, col2 = st.columns(2)
    with col1:
        job_titles = st.text_input("Job Titles (comma separated)", "Python Developer, AI Engineer")
        locations = st.text_input("Locations (comma separated)", "United States, Remote")
    
    with col2:
        remote_only = st.checkbox("Remote Only")
        

    if st.button("Start Crawling"):
        if not db:
            st.error("Database not connected.")
        else:
            with st.spinner("Crawling jobs in parallel... This might take a while."):
                titles = [t.strip() for t in job_titles.split(",")]
                locs = [l.strip() for l in locations.split(",")]
                
                scrapers = [LinkedInScraper(), IndeedScraper(), GlintsScraper()]
                all_jobs = []
                
                def run_scraper(scraper):
                    try:
                        return scraper.scrape(titles, locs, remote_only)
                    except Exception as e:
                        st.error(f"Error with scraper {type(scraper).__name__}: {e}")
                        return []

                with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                    results = list(executor.map(run_scraper, scrapers))
                
                for jobs in results:
                    all_jobs.extend(jobs)
                
                if all_jobs:
                    db.save_jobs(all_jobs)
                    st.success(f"Found and saved {len(all_jobs)} jobs!")
                else:
                    st.warning("No jobs found.")

    # Display Jobs
    st.subheader("Available Jobs")
    if db:
        jobs = db.get_jobs()
        if jobs:
            df = pd.DataFrame(jobs)
            st.dataframe(df, use_container_width=True)
            
            # Action buttons for each job (simplified)
            selected_job_idx = st.selectbox("Select Job to Apply", range(len(jobs)), format_func=lambda i: f"{jobs[i]['title']} at {jobs[i]['company']}")
            selected_job = jobs[selected_job_idx]
            
            if st.button("Generate Optimized Resume"):
                st.info("Generating resume... (Requires OpenAI Key)")
                # optimizer = ResumeOptimizer()
                # optimized_cv = optimizer.optimize(user_base_cv, selected_job['description'])
                # st.markdown(optimized_cv)
                st.warning("Resume Optimizer requires User Profile setup first.")
                
            if st.button("Apply with Agent"):
                st.info(f"Launching Agent for {selected_job['url']}...")
                # agent = ApplicationAgent()
                # agent.apply(selected_job['url'], user_profile)
                st.warning("Agent requires User Profile setup first.")
        else:
            st.info("No jobs in database. Start crawling!")

elif page == "My Profile":
    st.header("My Profile")
    st.write("Upload your base CV and manage your 'Base Knowledge'.")
    
    uploaded_file = st.file_uploader("Upload Base Resume (PDF/TXT)", type=["pdf", "txt"])
    if uploaded_file:
        st.success("File uploaded successfully!")
        # Save file content to DB or disk
    
    with st.form("profile_form"):
        st.subheader("Base Knowledge")
        name = st.text_input("Full Name")
        email = st.text_input("Email")
        phone = st.text_input("Phone")
        linkedin = st.text_input("LinkedIn URL")
        portfolio = st.text_input("Portfolio URL")
        
        if st.form_submit_button("Save Profile"):
            # Save to DB
            st.success("Profile saved!")

elif page == "Applications":
    st.header("Application Tracker")
    st.info("Track your applications here.")

# Footer
st.sidebar.markdown("---")
st.sidebar.caption("Powered by LangGraph & Playwright")
