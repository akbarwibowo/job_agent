FIELD_MAPPER_SYSTEM_PROMPT = "You are an intelligent form-filling agent. Your task is to map form field labels to the user's profile data."

FIELD_MAPPER_USER_PROMPT = """
User Profile:
{user_profile}

Form Fields found on page:
{form_fields}

Return a JSON object where keys are the field identifiers (id or name) and values are the data to fill.
If a field cannot be filled from the profile, use "ASK_USER" as the value.
"""
