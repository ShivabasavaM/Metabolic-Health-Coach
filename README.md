# 🧬 Metabolic Health Coach

An agentic AI microservice built with **LangGraph** and **Gemini 2.5 Flash**, deployed on **Google Cloud Run**. This unified orchestrator translates natural language into strict, bounded database mutations for nutrition and fitness tracking, while dynamically interacting with the Fitbit API.

## 1. Problem Statement
Health tracking is fundamentally fragmented. Users must juggle separate applications for calorie counting, workout logging, and biometric data (sleep/wearables). Furthermore, standard LLM integrations fail as health trackers because they:
1. Suffer from context-window bloat over long conversation histories.
2. Hallucinate inputs and easily corrupt databases with invalid data (e.g., logging a "600-minute workout").
3. Struggle with multi-step reasoning requiring parallel execution.

## 2. Solution Overview
We built a dual-engine AI orchestrator that acts as a unified Telegram interface. By wrapping Google's Gemini 2.5 Flash in a deterministically routed LangGraph state machine, the agent maps natural language to strict backend APIs. It handles parallel tool calling (e.g., fetching 3-day history *and* current health profile simultaneously) and strictly validates all data payloads via Pydantic before executing PostgreSQL transactions.

## 3. Architecture & Design Decisions
* **State Machine Over Chains:** Migrated from standard LangChain conversational chains to **LangGraph**. This allows for cyclical reasoning, explicit state management, and strict checkpointing using `PostgresSaver`.
* **Token-Optimized Context Pruning:** Instead of executing a secondary LLM call to summarize conversation history (which adds ~2.5s of latency), we implemented a sliding-window metadata stripper. We retain the immediate 4 messages fully, but strip heavy JSON tool-call metadata from older messages, extracting only raw human/AI text.
* **Lazy Initialization:** External integrations (Fitbit Client) are initialized lazily *inside* tool execution scopes rather than at import-time. This decouples the evaluation test suite from live database dependencies, preventing pipeline crashes.
* **Serverless Deployment:** Transitioned from persistent long-polling servers (which suffer from timeouts and high costs) to an event-driven webhook architecture on **Google Cloud Run**, achieving scale-to-zero efficiency.

## 4. Tech Stack
* **Orchestration:** `LangGraph` — Chosen for cyclical graphs and native parallel tool execution capabilities.
* **LLM Engine:** `Gemini 2.5 Flash` — Chosen for sub-second latency and high accuracy in strict JSON schema extraction.
* **Database & Memory:** `PostgreSQL` & `psycopg_pool` — Handles both relational user data and persistent conversational state.
* **API Framework:** `FastAPI` + `Uvicorn` — High-throughput asynchronous framework required for handling rapid Telegram webhooks.
* **Guardrails:** `Pydantic (v2)` — Chosen for programmatic parameter bounding (e.g., bounding exercise sets to `>0` and `<50`) before SQL execution.
* **CI/CD:** `GitHub Actions` & `Pytest` — Automated 50-case evaluation harness mapped directly to GCP IAM.

## 5. Results & Metrics
* **Routing Accuracy:** Achieved **100% precision (50/50 cases)** on a diverse evaluation harness testing both implicit inference (e.g., classifying "ran 5k" as cardio with 0 sets) and parallel tool execution. 
* **Data Integrity:** Achieved a **0% database corruption rate** by intercepting hallucinated payloads via Pydantic schema validation.
* **Payload Optimization:** Context pruning reduced historical payload token weight by **~82%** (e.g., pruning an average 3,500-token payload down to ~600 tokens), drastically reducing inference costs.
* **Pipeline Velocity:** Fully automated CI/CD pipeline averages **< 2.5 minutes** from Git push to live Cloud Run revision deployment.

## 6. Key Features
* 🗣️ **Conversational Logging:** NLP-driven data entry for both complex meals and gym routines (e.g., *"Bench press 5x5 took me 20m"*).
* 🔀 **Parallel Tool Calling:** Ability to execute multi-tool queries in a single generative pass.
* 🛡️ **Mathematical Guardrails:** Strict data boundaries enforced at the schema level.
* ⌚ **Wearable Integration:** Real-time biometric syncing (Sleep, Calories Burned) via OAuth2 Fitbit integration.

## 7. Installation & Setup

```bash
# 1. Clone the repository
git clone [https://github.com/yourusername/metabolic-health-coach.git](https://github.com/yourusername/metabolic-health-coach.git)
cd metabolic-health-coach

# 2. Set up virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set environment variables (.env)
DATABASE_URL=postgresql://user:password@localhost:5432/healthdb
GEMINI_API_KEY=your_gemini_key
TELEGRAM_BOT_TOKEN=your_telegram_token
FITBIT_CLIENT_ID=your_client_id
FITBIT_CLIENT_SECRET=your_client_secret

# 5. Run the evaluation harness locally
python -m pytest tests/test_routing.py -v 
```

## 8. Usage Examples

**Nutrition Engine:**
> **User:** "I ate a 500 calorie burger for lunch." <br>
> **Agent:** `[Executes log_food(food_name="burger", calories=500)]` "Got it! Logged your 500 kcal burger. You have 1500 kcal left for the day."

**Fitness Engine:**
> **User:** "Ran 5k on the treadmill in 25 minutes." <br>
> **Agent:** `[Executes log_workout(exercise_type="treadmill", sets=1, reps=0, duration_minutes=25)]` "Great job on the cardio! 25 minutes on the treadmill logged."

**Parallel Reasoning:**
> **User:** "Did I hit my average target over the last 3 days?" <br>
> **Agent:** `[Executes get_historical_summary(days=3) AND get_health_status()]` "Your target is 2000 kcal, and your 3-day average is 1950 kcal. You are perfectly on track!"

## 9. Performance & Reliability
* **Stateless Resiliency:** The webhook design allows Cloud Run to spin up concurrent container instances under load. Because LangGraph state is strictly checkpointed to PostgreSQL, any instance can seamlessly pick up a conversation thread without losing context.
* **Defensive Fallbacks:** Database connection pools are wrapped in `try-except` blocks. If the production database goes offline, the system gracefully falls back to an ephemeral memory checkpointer, allowing automated testing to complete without a live DB.

## 10. Design Trade-offs
1. **Context Pruning vs. LLM Summarization:** We opted for Python-native string slicing to prune history rather than having the LLM generate a rolling summary. *Trade-off:* We lose minor semantic nuances from past messages. *Advantage:* Saves ~2 seconds of latency per request and completely eliminates the token cost of a secondary summarization call.
2. **Dual PostgreSQL Drivers:** The current build utilizes both `psycopg2` (legacy queries) and `psycopg3` (LangGraph integration). *Trade-off:* Adds ~4MB of dependency weight and minor technical debt. *Advantage:* Allowed for rapid iteration and shipping of the LangGraph orchestrator without requiring a complete rewrite of the existing database schema.

## 11. Limitations & Future Work
* **Multi-Tenancy:** The application currently runs with a hardcoded `user_id = 1`. Future iterations will require implementing row-level security (RLS) in PostgreSQL and mapping Telegram `chat_id`s to user profiles.
* **Database Refactor (Phase C):** Complete migration of all `psycopg2` queries to `psycopg3` for unified connection pooling.
* **Observability:** Integrate LangSmith into the production environment to trace token consumption and visualize agent decision trees during live deployments.

## 12. References
* [LangGraph Documentation](https://python.langchain.com/docs/langgraph)
* [Google Cloud Run Webhooks](https://cloud.google.com/run/docs/triggering/https-request)
* [Pydantic Validation](https://docs.pydantic.dev/latest/)
* [Fitbit Web API](https://dev.fitbit.com/build/reference/web-api/)
