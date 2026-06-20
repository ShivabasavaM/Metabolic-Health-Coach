import pytest
from langchain_core.messages import HumanMessage
from app.brain import llm_with_tools

# The Golden Dataset: 50 Diverse Test Cases
EVALUATION_DATASET = [
    # --- 🍔 NUTRITION: EXPLICIT LOGGING (1-10) ---
    ("I ate a 500 calorie burger for lunch", "log_food", {"food_name": "burger", "calories": 500}),
    ("Log an apple, 95 cals", "log_food", {"food_name": "apple", "calories": 95}),
    ("Just drank a protein shake (150 kcal)", "log_food", {"food_name": "protein shake", "calories": 150}),
    ("Chicken breast and rice, 600 calories", "log_food", {"food_name": "chicken breast and rice", "calories": 600}),
    ("Oatmeal for breakfast, 250 cals", "log_food", {"food_name": "oatmeal", "calories": 250}),
    ("Snacked on almonds, roughly 200 calories", "log_food", {"food_name": "almonds", "calories": 200}),
    ("Midnight snack: ice cream 400 cal", "log_food", {"food_name": "ice cream", "calories": 400}),
    ("Logged a 800 calorie burrito", "log_food", {"food_name": "burrito", "calories": 800}),
    ("Ate a 200 calorie fruit bowl", "log_food", {"food_name": "fruit bowl", "calories": 200}),
    ("Sushi for dinner, 750 kcal", "log_food", {"food_name": "sushi", "calories": 750}),

    # --- 🏋️ FITNESS: WORKOUT LOGGING (11-20) ---
    ("I just finished 4 sets of 12 reps on the bench press. Took me 45 mins.", "log_workout", {"exercise_type": "bench press", "sets": 4, "reps": 12, "duration_minutes": 45}),
    ("Ran 5k on the treadmill in 25 minutes", "log_workout", {"exercise_type": "running", "sets": 1, "reps": 0, "duration_minutes": 25}),    ("Cycled for 45 mins", "log_workout", {"exercise_type": "cycling", "sets": 1, "reps": 0, "duration_minutes": 45}),
    ("Hit 3 sets of 10 reps for bicep curls, 15 min", "log_workout", {"exercise_type": "bicep curls", "sets": 3, "reps": 10, "duration_minutes": 15}),
    ("Squats: 4 sets, 8 reps, 20 minutes", "log_workout", {"exercise_type": "squats", "sets": 4, "reps": 8, "duration_minutes": 20}),
    ("Jump rope for 10 minutes", "log_workout", {"exercise_type": "jump rope", "sets": 1, "reps": 0, "duration_minutes": 10}),
    ("Bench press 5x5 took me 20m", "log_workout", {"exercise_type": "bench press", "sets": 5, "reps": 5, "duration_minutes": 20}), # Tests shorthand "5x5" extraction
    ("Did 3 sets of 15 pushups, took 5 mins", "log_workout", {"exercise_type": "pushups", "sets": 3, "reps": 15, "duration_minutes": 5}),
    ("Rowing machine for 30 minutes", "log_workout", {"exercise_type": "rowing machine", "sets": 1, "reps": 0, "duration_minutes": 30}),
    ("Pull-ups, 4 sets to failure (10 reps each), 15 mins", "log_workout", {"exercise_type": "pull-ups", "sets": 4, "reps": 10, "duration_minutes": 15}),

    # --- 📋 FITNESS: COACHING & PLANS (21-25) ---
    ("Give me a good beginner leg day routine", "generate_workout_plan", {"target_muscle_group": "legs", "fitness_level": "beginner"}),
    ("I need an advanced chest workout", "generate_workout_plan", {"target_muscle_group": "chest", "fitness_level": "advanced"}),
    ("What's a good intermediate full body plan?", "generate_workout_plan", {"target_muscle_group": "full body", "fitness_level": "intermediate"}),
    ("I've never lifted before, give me a cardio workout", "generate_workout_plan", {"target_muscle_group": "cardio", "fitness_level": "beginner"}),
    ("Advanced back day plan please", "generate_workout_plan", {"target_muscle_group": "back", "fitness_level": "advanced"}),

    # --- ⚙️ SYSTEM: PROFILE MANAGEMENT (26-30) ---
    ("Update my weight to 85kg and goal to 2500 calories", "update_profile", {"weight": 85.0, "target_calories": 2500}),
    ("I weigh 70.5kg now and want to hit 2000 cals daily", "update_profile", {"weight": 70.5, "target_calories": 2000}),
    ("Forget everything, I want to start over", "reset_profile", {}),
    ("Wipe my data completely", "reset_profile", {}),
    ("Change my target to 3000 calories and weight to 90kg", "update_profile", {"weight": 90.0, "target_calories": 3000}),

    # --- 📊 SYSTEM: ANALYTICS & STATUS (31-35) ---
    ("What are my current stats and sleep?", "get_health_status", {}),
    ("Show me my current health status", "get_health_status", {}),
    ("What is my average calorie intake for the last 7 days?", "get_historical_summary", {"days": 7}),
    ("Show my 30-day calorie average", "get_historical_summary", {"days": 30}),
    ("Fetch my calorie data for the last 3 days", "get_historical_summary", {"days": 3}),

    # --- 🚫 EDGE CASES: INTENT MISMATCH (NO TOOL EXPECTED) (36-40) ---
    ("I am thinking about going to the gym.", None, {}), # Intent not actionable yet
    ("I saw a recipe for a 500 calorie burger, looks good.", None, {}), # Didn't actually eat it
    ("My friend lifted 300 lbs today for 5 reps.", None, {}), # Not the user
    ("What should I eat for dinner?", None, {}), # Asking for advice, not logging
    ("Do you think 1000 calories a day is healthy?", None, {}), # Subjective question

    # --- 💬 CONVERSATIONAL & OUT-OF-BOUNDS (NO TOOL EXPECTED) (41-50) ---
    ("Thanks for the help coach!", None, {}),
    ("What is the capital of France?", None, {}),
    ("Hey coach, how are you?", None, {}),
    ("Can you write a python script for me?", None, {}),
    ("Good morning!", None, {}),
    ("I feel tired today.", None, {}), 
    ("Why is the sky blue?", None, {}),
    ("Can you book a flight to Paris?", None, {}),
    ("Tell me a joke.", None, {}),
    ("Who won the World Cup?", None, {})
]

@pytest.mark.parametrize("user_input, expected_tool, expected_args", EVALUATION_DATASET)
def test_agent_tool_routing(user_input, expected_tool, expected_args):
    """
    Evaluates if Gemini correctly maps natural language to the exact backend tool schema.
    """
    response = llm_with_tools.invoke([HumanMessage(content=user_input)])
    
    if expected_tool is None:
        assert not hasattr(response, 'tool_calls') or len(response.tool_calls) == 0, \
            f"Failed: Agent hallucinated a tool call for input '{user_input}'"
    else:
        assert hasattr(response, 'tool_calls') and len(response.tool_calls) == 1, \
            f"Failed: Agent did not trigger a tool for '{user_input}'"
        
        tool_call = response.tool_calls[0]
        
        assert tool_call["name"] == expected_tool, \
            f"Routing Error: Expected {expected_tool}, but agent routed to {tool_call['name']}"

        for key, expected_val in expected_args.items():
            actual_val = tool_call["args"].get(key)
            if isinstance(actual_val, str) and isinstance(expected_val, str):
                assert actual_val.lower() == expected_val.lower(), \
                    f"Extraction Error on '{key}': Expected {expected_val}, got {actual_val}"
            else:
                assert actual_val == expected_val, \
                    f"Extraction Error on '{key}': Expected {expected_val}, got {actual_val}"