from os import getenv

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from openai import OpenAI
import requests

# Load environment variables
load_dotenv()

# Initialize app
app = FastAPI()

# Set API keys
client = OpenAI(api_key=getenv("OPENAI_API_KEY"))
whatsapp_token = getenv("WHATSAPP_ACCESS_TOKEN")
phone_number_id = getenv("WHATSAPP_PHONE_NUMBER_ID")
verify_token = getenv("WHATSAPP_VERIFY_TOKEN")


# Root endpoint
@app.get("/")
def read_root():
    return {"message": "WhatsApp Nutritionist Bot is running 🚀"}


# Webhook verification
@app.get("/whatsapp")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if mode == "subscribe" and token == verify_token:
        return PlainTextResponse(challenge)
    return PlainTextResponse("Verification failed", status_code=403)


# WhatsApp webhook endpoint
@app.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    data = await request.json()
    print(f"Incoming webhook: {data}")
    try:
        message = data["entry"][0]["changes"][0]["value"]["messages"][0]
        Body = message["text"]["body"]
        From = message["from"]
    except Exception as e:
        print(f"Invalid message format: {e}")
        return {"status": "ignored"}

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

    # Send reply via WhatsApp Cloud API
    url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": From,
        "type": "text",
        "text": {"body": nutritionist_reply},
    }
    headers = {"Authorization": f"Bearer {whatsapp_token}"}

    try:
        api_response = requests.post(url, headers=headers, json=payload)
        api_response.raise_for_status()
    except Exception as e:
        print(f"Error sending message to WhatsApp: {e}")
        return {"status": "error"}

    return {"status": "sent"}
