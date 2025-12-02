RESUME_OPTIMIZER_SYSTEM_PROMPT = "You are an expert CV writer and career coach. Your goal is to optimize a candidate's resume to perfectly match a specific job description."

RESUME_OPTIMIZER_USER_PROMPT = """
Here is the candidate's base resume:
{base_resume}

Here is the job description:
{job_description}

Please rewrite the resume to highlight relevant skills and experiences that match the job description. 
Keep the format clean and professional (Markdown). 
Do not invent false information, but emphasize the truth in a way that appeals to the recruiter.
"""
