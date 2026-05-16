import os
import telebot
from fastapi import FastAPI, Request, Response
from contextlib import asynccontextmanager

# Import your stateful LangGraph agent orchestrator
from app.brain import app_graph 

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# Note: threaded=False is critical when running inside an async ASGI server like Uvicorn
bot = telebot.TeleBot(TOKEN, threaded=False)  

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle manager that automatically registers the webhook URL with Telegram 
    when the Render container spins up, and tears it down on shutdown.
    """
    # Render automatically provisions this environment variable for web services
    base_url = os.getenv("RENDER_EXTERNAL_URL")
    
    if base_url:
        webhook_url = f"{base_url}/webhook"
        bot.remove_webhook()
        success = bot.set_webhook(url=webhook_url)
        if success:
            print(f"🚀 Webhook successfully registered at: {webhook_url}")
        else:
            print("❌ Failed to register webhook with Telegram.")
    else:
        print("⚠️ RENDER_EXTERNAL_URL not found. Webhook registration skipped (Local mode).")
        
    yield
    
    # Graceful shutdown cleanup
    print("Shutting down... removing webhook from Telegram.")
    bot.remove_webhook()

# Initialize FastAPI with our lifecycle hook
app = FastAPI(lifespan=lifespan)

@bot.message_handler(func=lambda message: True)
def handle_agent_logic(message):
    """
    Core handler that routes incoming text messages from your Telegram bot
    directly through your LangGraph conversational agent pipeline.
    """
    try:
        user_query = message.text
        chat_id = message.chat.id
        
        # 🔗 Invoke your LangGraph state machine using the user's Chat ID as the thread_id
        response = app_graph.invoke(
            {"messages": [user_query]}, 
            config={"configurable": {"thread_id": chat_id}}
        )
        
        # Extract the content of the final AI message from the graph state
        final_reply = response["messages"][-1].content
        
        # Reply directly back to the user on Telegram
        bot.reply_to(message, final_reply)
        
    except Exception as e:
        print(f"❌ AI Brain Orchestration Error: {e}")
        bot.reply_to(message, "Sorry, my brain encountered a small glitch. Try again!")

@app.post("/webhook")
async def telegram_webhook(request: Request):
    """
    Inbound endpoint targeted by Telegram whenever a user sends a message.
    This inbound payload wakes Render up automatically from a cold sleep.
    """
    if request.headers.get("content-type") == "application/json":
        json_string = await request.json()
        update = telebot.types.Update.de_json(json_string)
        
        # Pass the parsed update structure into pyTelegramBotAPI internal router
        bot.process_new_updates([update])
        return Response(status_code=200)
    else:
        return Response(status_code=403)

@app.get("/health")
def health_check():
    """Liveness probe used by Render to monitor application health."""
    return {"status": "healthy"}