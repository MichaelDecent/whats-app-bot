from os import getenv

from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request
from fastapi.responses import PlainTextResponse
from openai import OpenAI
from twilio.twiml.messaging_response import MessagingResponse

# Load environment variables
load_dotenv()

# Initialize app
app = FastAPI()

# Set API keys
client = OpenAI(api_key=getenv("OPENAI_API_KEY"))
twilio_auth_token = getenv("TWILIO_AUTH_TOKEN")


# Root endpoint
@app.get("/")
def read_root():
    return {"message": "WhatsApp Nutritionist Bot is running 🚀"}


# WhatsApp webhook endpoint
@app.post("/whatsapp")
async def whatsapp_webhook(
    request: Request, Body: str = Form(...), From: str = Form(...)
):
    print(f"Incoming message from {From}: {Body}")

    # Create GPT-4o prompt
    gpt_prompt = [
        {
            "role": "system",
            "content": "You are a certified, friendly nutritionist. Give advice based on user's needs, ask follow-up questions when needed.",
        },
        {"role": "user", "content": Body},
    ]

    try:
        # Get response from GPT-4o
        gpt_response = client.chat.completions.create(
            model="gpt-4o", messages=gpt_prompt, temperature=0.7
        )
        nutritionist_reply = gpt_response.choices[0].message.content
    except Exception as e:
        print(f"Error communicating with OpenAI: {e}")
        nutritionist_reply = "Sorry, I'm having trouble fetching advice at the moment. Please try again later."

    # Create a WhatsApp reply
    response = MessagingResponse()
    response.message(nutritionist_reply)

    return PlainTextResponse(str(response))
