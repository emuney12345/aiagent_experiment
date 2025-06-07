from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
import os
import json

# Load .env variables
load_dotenv()

# FastAPI app
app = FastAPI()

# Toggle for mock mode
USE_MOCK = os.getenv("USE_MOCK_LLM", "false").lower() == "true"

# Load either real or fake LLM
if USE_MOCK:
    from langchain.llms.fake import FakeListLLM
    llm = FakeListLLM(responses=[
        json.dumps({
            "action": "respond",
            "reason": "User is asking a direct question about a deadline."
        })
    ])
else:
    from langchain_community.chat_models import ChatOpenAI
    llm = ChatOpenAI(temperature=0, openai_api_key=os.getenv("OPENAI_API_KEY"))

# Define input schema
class EmailRequest(BaseModel):
    sender: str
    recipient: str
    subject: str
    body: str

# Profile + triage rules
profile = {
    "name": "John",
    "full_name": "John Doe",
    "user_profile_background": "Senior software engineer"
}

triage_rules = {
    "ignore": "Marketing newsletters, spam emails, mailing lists",
    "notify": "Team member out sick, build system notifications",
    "respond": "Direct questions from team members, meeting requests"
}

agent_instructions = "Use these rules when appropriate."

@app.post("/generate")
def generate_response(email: EmailRequest):
    try:
        # Prompt construction
        system_prompt = f"""
        You are an AI email triage assistant for {profile['full_name']} ({profile['name']}).
        Background: {profile['user_profile_background']}

        Triage rules:
        - Ignore: {triage_rules['ignore']}
        - Notify: {triage_rules['notify']}
        - Respond: {triage_rules['respond']}

        {agent_instructions}
        """

        user_prompt = f"""
        From: {email.sender}
        To: {email.recipient}
        Subject: {email.subject}

        {email.body}

        What should I do with this email?
        """

        # AI Call (real or mock)
        if USE_MOCK:
            raw = llm.invoke("Mock input")
            parsed = json.loads(raw)
        else:
            raw = llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ])
            parsed = {"response": raw}  # fallback structure for now

        return parsed

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
