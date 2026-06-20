import os
import psycopg2.extras
from langchain_core.tools import tool
from app.fitbit_client import FitbitClient
from app import database
from pydantic import BaseModel, Field

fitbit = FitbitClient()

class LogWorkoutSchema(BaseModel):
    exercise_type: str = Field(description="Name of the exercise")
    sets: int = Field(gt=0, le=50, description="Must be between 1 and 50 sets")
    reps: int = Field(ge=0, le=500, description="Must be positive, 0 for cardio")
    duration_minutes: int = Field(gt=0, le=300, description="Must be between 1 and 300 minutes")

class UpdateProfileSchema(BaseModel):
    weight: float = Field(gt=20.0, le=300.0, description="Weight in kg, must be realistic")
    target_calories: int = Field(ge=1000, le=5000, description="Daily calorie target")

@tool
def log_food(food_name: str, calories: int):
    """
    Logs food eaten by the user and automatically deletes data older than 3 days.
    CRITICAL GUARDRAIL: DO NOT use this tool if the user is just talking about recipes, 
    ideas, or hypothetical food. ONLY use this tool if the user explicitly confirms 
    they ATE or DRANK the item.
    """
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
    
    # 🐛 FIX: Added RealDictCursor so row['avg_eaten'] works, and fixed the INTERVAL injection
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    interval_string = f"{days} days"
    
    cursor.execute('''
        SELECT AVG(daily_total) as avg_eaten FROM (
            SELECT SUM(calories_in) as daily_total
            FROM daily_logs
            WHERE user_id = 1 AND date >= CURRENT_DATE - %s::interval
            GROUP BY date
        ) subquery
    ''', (interval_string,))
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

@tool(args_schema=LogWorkoutSchema)
def log_workout(exercise_type: str, sets: int, reps: int, duration_minutes: int) -> str:    
    """
    Logs a completed workout session to the database. 
    Use ONLY when the user explicitly states they finished an exercise.
    
    :param exercise_type: Name of the exercise (e.g., 'Squats', 'Running', 'Bench Press')
    :param sets: Number of sets completed. Use 1 for continuous cardio.
    :param reps: Number of repetitions per set. Use 0 for cardio.
    :param duration_minutes: Total time spent on this exercise in minutes.
    """
    conn = database.get_connection()
    if not conn: return "Database Error."
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO workouts (user_id, exercise_type, sets, reps, duration_minutes)
            VALUES (1, %s, %s, %s, %s)
        """, (exercise_type, sets, reps, duration_minutes))
        conn.commit()
        return f"Successfully logged {sets} sets of {reps} reps of {exercise_type} ({duration_minutes} mins)."
    except Exception as e:
        return f"Failed to log workout: {e}"
    finally:
        cursor.close()
        database.release_connection(conn)

@tool
def generate_workout_plan(target_muscle_group: str, fitness_level: str) -> str:
    """
    Generates a structured gym workout plan. 
    Use this when the user asks for exercise recommendations, a routine, or what to do at the gym.
    
    :param target_muscle_group: e.g., 'chest', 'legs', 'full body', 'cardio'
    :param fitness_level: e.g., 'beginner', 'intermediate', 'advanced'
    """
    return f"System Command: Generate a highly specific, {fitness_level}-level {target_muscle_group} workout. Include exercises, sets, and reps. Be highly encouraging!"