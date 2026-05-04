import os
import psycopg2.extras
from langchain_core.tools import tool
from app.fitbit_client import FitbitClient
from app import database

fitbit = FitbitClient()

@tool
def log_food(food_name: str, calories: int):
    """Logs food eaten by the user and automatically deletes data older than 3 days."""
    conn = database.get_connection()
    if not conn: return "Database Error."
    cursor = conn.cursor()
    cursor.execute("INSERT INTO daily_logs (date, user_id, food_name, calories_in) VALUES (CURRENT_DATE, 1, %s, %s)", (food_name, calories))
    cursor.execute("DELETE FROM daily_logs WHERE user_id = 1 AND date < CURRENT_DATE - INTERVAL '3 days'")
    conn.commit()
    cursor.close()
    database.release_connection(conn) # Use release, not close
    return f"Successfully logged {food_name} ({calories} kcal)."


@tool
def reset_profile():
    """Wipes the user's profile and food history completely."""
    conn = database.get_connection()
    if not conn: return "Database Error."
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET weight = NULL, goal = NULL, daily_calorie_target = NULL WHERE id = 1")
    cursor.execute("DELETE FROM daily_logs WHERE user_id = 1") 
    conn.commit()
    cursor.close()
    database.release_connection(conn)
    return "DATABASE WIPED. Tell the user their profile is reset and immediately ask for their new weight and goal to restart onboarding."

@tool
def get_historical_summary(days: int):
    """Fetches the average daily calories the user has eaten over the last X days."""
    conn = database.get_connection()
    if not conn: return "Database Error."
    cursor = conn.cursor()
    cursor.execute(f'''
        SELECT AVG(daily_total) as avg_eaten FROM (
            SELECT SUM(calories_in) as daily_total
            FROM daily_logs
            WHERE user_id = 1 AND date >= CURRENT_DATE - INTERVAL '%s days'
            GROUP BY date
        ) subquery
    ''', (days,))
    row = cursor.fetchone()
    cursor.close()
    database.release_connection(conn)
    
    avg_eaten = round(row['avg_eaten']) if row and row['avg_eaten'] else 0
    return f"Data context: Over the last {days} days, the user ate an average of {avg_eaten} kcal per day."

@tool
def update_profile(weight: float, target_calories: int):
    """Updates the user's weight and daily calorie target."""
    if not (1000 <= target_calories <= 4000):
        return f"ERROR: {target_calories} is an unsafe/unrealistic target. Please recalculate properly between 1000 and 4000 kcal."
        
    conn = database.get_connection()
    if not conn: return "Database Error."
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET weight = %s, daily_calorie_target = %s WHERE id = 1", (weight, target_calories))
    conn.commit()
    cursor.close()
    database.release_connection(conn) 
    return f"Profile updated. Weight: {weight}kg, Goal: {target_calories} kcal."

@tool
def get_health_status():
    """Fetches user's daily calorie goal, logged food, and Fitbit biometrics (Calories & Sleep)."""
    conn = database.get_connection()
    if not conn: return "Database Error."
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) # Need RealDictCursor here
    
    cursor.execute("SELECT daily_calorie_target FROM users WHERE id = 1")
    row = cursor.fetchone()
    target = row['daily_calorie_target'] if row and row['daily_calorie_target'] else 2000
    
    cursor.execute("SELECT COALESCE(SUM(calories_in), 0) as total_eaten FROM daily_logs WHERE user_id = 1 AND date = CURRENT_DATE")
    eaten_row = cursor.fetchone()
    eaten = eaten_row['total_eaten'] if eaten_row else 0
    
    cursor.close()
    database.release_connection(conn)

    burned = fitbit.get_calories_today()
    sleep_mins = fitbit.get_sleep_today()
    sleep_hours = round(sleep_mins / 60, 1)
    
    return f"Goal: {target} kcal. Eaten: {eaten} kcal. Burned (Fitbit): {burned} kcal. Sleep Last Night: {sleep_hours} hours."