import os
import psycopg
import psycopg2.extras
from typing import Annotated
from typing_extensions import TypedDict
from dotenv import load_dotenv
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage

# FIX 2: Added the missing database import
from app import database
from app.tools import get_health_status, log_food, update_profile, reset_profile, get_historical_summary, log_workout, generate_workout_plan

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")
class State(TypedDict):
    messages: Annotated[list, add_messages]

tools = [get_health_status, log_food, update_profile, reset_profile, get_historical_summary, log_workout, generate_workout_plan]
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
llm_with_tools = llm.bind_tools(tools)


def get_db_context():
    """Fetches real-time DB state to inject into the prompt."""
    conn = database.get_connection()
    # FIX 3: Properly return an empty string alongside None
    if not conn: return None, "" 
 
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    cursor.execute("SELECT weight, daily_calorie_target FROM users WHERE id = 1")
    user = cursor.fetchone()
    
    history_text = "No recent food history."
    if user and user['daily_calorie_target']:
        cursor.execute("""
            SELECT date, SUM(calories_in) as total 
            FROM daily_logs WHERE user_id=1 
            GROUP BY date ORDER BY date DESC LIMIT 3
        """)
        history = cursor.fetchall()
        if history:
            history_text = ", ".join([f"{h['date']}: {h['total']}kcal" for h in history])
            
    cursor.close()
    database.release_connection(conn)
    return user, history_text

def chatbot(state: State):
    user, history_text = get_db_context()
    target = user['daily_calorie_target'] if user else None

    # STATE A: FORCED ONBOARDING
    if not target:
        system_prompt = SystemMessage(content=(
            "You are Metabolic-Health Coach. The user currently has NO profile in the database.\n"
            "CRITICAL RULES:\n"
            "1. Do NOT answer general fitness questions yet.\n"
            "2. Ask the user for their current weight, height, age, target weight, and time span within that they want to achieve and if they want to gain/lose.\n"
            "3. Once they provide this, CALCULATE a daily calorie target using standard formulas.\n"
            "4. YOU MUST immediately call the `update_profile` tool to save these numbers to the database.\n"
            "5. Tell them they are ready to start tracking."
        ))
    
    # STATE B: ACTIVE TRACKING
    else:
        system_prompt = SystemMessage(content=(
            f"You are the Metabolic-Health & Fitness Coach. The user's active goal is {target} kcal/day.\n"
            f"Last 3 Days Eaten: {history_text}\n\n"
            "RULES:\n"
            "1. NUTRITION: Use `log_food` ONLY if the user explicitly says they ate something.\n"
            "2. FITNESS TRACKING: Use `log_workout` ONLY if they explicitly state they completed an exercise.\n"
            "3. FITNESS COACHING: Use `generate_workout_plan` if they ask for gym recommendations or routines.\n"
            "4. Keep responses conversational, highly encouraging, and strictly formatted. Do not lecture."
        ))

    raw_messages = state["messages"]

    if len(raw_messages) > 10:
        historical_block = raw_messages[:-4]
        recent_block = raw_messages[-4:]

        history_summary_text = "\n".join([
            f"{msg.type.upper()}: {msg.content}" 
            for msg in historical_block 
            if msg.content and msg.type in ["human", "ai"]
        ])

        memory_prompt = SystemMessage(content=(
            f"--- OLDER CONVERSATION MEMORY ---\n{history_summary_text}\n"
            "---------------------------------\n"
            "Use the above memory if needed, but prioritize the immediate recent messages below."
        ))

        messages_to_pass = [system_prompt, memory_prompt] + recent_block
        print(f"✂️ Context Pruned: Compressed {len(raw_messages)} messages to save tokens.")
    else:
        messages_to_pass = [system_prompt] + raw_messages

    response = llm_with_tools.invoke(messages_to_pass)
    return {"messages": [response]}

graph_builder = StateGraph(State)
graph_builder.add_node("chatbot", chatbot)
graph_builder.add_node("tools", ToolNode(tools=tools))
graph_builder.add_edge(START, "chatbot")
graph_builder.add_conditional_edges("chatbot", tools_condition)
graph_builder.add_edge("tools", "chatbot")

# FIX 1: Cleaned up the Try/Except block logic
try:
    if not DB_URL:
        raise ValueError("DATABASE_URL environment variable is missing.")
        
    checkpoint_pool = ConnectionPool(conninfo=DB_URL)
    with psycopg.connect(DB_URL, autocommit=True) as conn:
        temp_memory = PostgresSaver(conn)
        temp_memory.setup()
        print("✅ LangGraph Memory Tables Initialized (Autocommit).")
        
    memory = PostgresSaver(checkpoint_pool)
    app_graph = graph_builder.compile(checkpointer=memory)
    
except Exception as e:
    print(f"⚠️ Postgres Memory disabled (Running in Test Mode): {e}")
    # Fallback compilation so Pytest can evaluate routing logic without a live database!
    app_graph = graph_builder.compile()