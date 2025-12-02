import os
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from src.prompts.resume_optimizer_prompt import RESUME_OPTIMIZER_SYSTEM_PROMPT, RESUME_OPTIMIZER_USER_PROMPT

class ResumeOptimizer:
    def __init__(self, model_name="gpt-4o-mini"):
        # Allow overriding model via env or init
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables.")
        
        self.llm = ChatOpenAI(model=model_name, temperature=0.7)
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", RESUME_OPTIMIZER_SYSTEM_PROMPT),
            ("user", RESUME_OPTIMIZER_USER_PROMPT)
        ])
        
        self.chain = self.prompt | self.llm | StrOutputParser()

    def optimize(self, base_resume: str, job_description: str) -> str:
        """
        Optimizes the resume for the given job description.
        """
        return self.chain.invoke({
            "base_resume": base_resume,
            "job_description": job_description
        })
