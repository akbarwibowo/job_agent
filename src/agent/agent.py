import logging
from playwright.sync_api import sync_playwright
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from typing import Dict, Any

from src.prompts.field_mapper_prompt import FIELD_MAPPER_SYSTEM_PROMPT, FIELD_MAPPER_USER_PROMPT

class ApplicationAgent:
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0) # Use a smarter model for reasoning
        
        self.field_mapper_prompt = ChatPromptTemplate.from_messages([
            ("system", FIELD_MAPPER_SYSTEM_PROMPT),
            ("user", FIELD_MAPPER_USER_PROMPT)
        ])
        
        self.parser = JsonOutputParser()
        self.chain = self.field_mapper_prompt | self.llm | self.parser

    def apply(self, job_url: str, user_profile: Dict[str, Any]):
        """
        Navigates to the job URL and attempts to fill the application form.
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False) # Headless False so user can see/intervene
            page = browser.new_page()
            
            logging.info(f"Navigating to {job_url}")
            page.goto(job_url)
            
            # Wait for user to login if needed or navigate to the actual form
            # This is the "Human-in-the-loop" part where we might need to pause
            # For now, we'll assume the user is watching and we can try to detect inputs
            
            # Simple heuristic to find inputs
            inputs = page.query_selector_all("input, textarea, select")
            form_fields = []
            for inp in inputs:
                name = inp.get_attribute("name") or inp.get_attribute("id") or inp.get_attribute("placeholder")
                if name:
                    form_fields.append(name)
            
            if not form_fields:
                logging.warning("No form fields found. User might need to navigate manually.")
                # In a real agent, we might wait or ask user
                return

            # Decide what to fill
            mapping = self.chain.invoke({
                "user_profile": user_profile,
                "form_fields": form_fields
            })
            
            logging.info(f"Field Mapping: {mapping}")
            
            # Fill fields
            for field_id, value in mapping.items():
                if value != "ASK_USER":
                    try:
                        # Try to fill by name, id, or placeholder
                        page.fill(f"[name='{field_id}']", value) or \
                        page.fill(f"#{field_id}", value) or \
                        page.fill(f"[placeholder='{field_id}']", value)
                    except Exception as e:
                        logging.error(f"Failed to fill {field_id}: {e}")
            
            logging.info("Form filled. Waiting for user to review and submit.")
            page.pause() # Pause execution to let user review/submit
            
            browser.close()
