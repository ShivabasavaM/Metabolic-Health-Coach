import os
import telebot
import warnings
import threading
from fastapi import FastAPI
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

warnings.filterwarnings("ignore", category=UserWarning)

from app import database
from app.brain import app_graph 

load_dotenv()

app = FastAPI()

@app.get("/")
def health_check():
    return {"status": "Metabolic-Health-Coach is Awake 🧬"}

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = telebot.TeleBot(TELEGRAM_TOKEN)

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = str(message.chat.id)
    user_text = message.text
    
    database.mark_user_active() 
    
    print(f"📩 [{user_id}]: {user_text}")
    bot.send_chat_action(chat_id=user_id, action='typing')

    try:
        config = {"configurable": {"thread_id": user_id}}
        result = app_graph.invoke(
            {"messages": [HumanMessage(content=user_text)]}, 
            config=config
        )

        ai_reply = "I processed your request." 
        for msg in reversed(result["messages"]):
            if msg.type == "ai":
                if isinstance(msg.content, str) and msg.content.strip():
                    ai_reply = msg.content
                    break
                elif isinstance(msg.content, list):
                    extracted = " ".join(
                        str(item.get("text", "")) for item in msg.content if isinstance(item, dict) and "text" in item
                    )
                    if extracted.strip():
                        ai_reply = extracted
                        break
        
        bot.reply_to(message, ai_reply)
        print("✅ Reply sent.")
    except Exception as e:
        print(f"❌ Error: {e}")
        bot.reply_to(message, "Sorry, my brain encountered a small glitch. Try again!")

def run_bot():
    print("🤖 Metabolic-Health-Coach Telegram Listener is Awake...")
    bot.infinity_polling()

@app.on_event("startup")
def startup_event():
    threading.Thread(target=run_bot, daemon=True).start()