import os
import json
import datetime
import firebase_admin
from firebase_admin import credentials, db
from datetime import timedelta
import pandas as pd

# ==========================================
# FIREBASE INITIALIZATION
# ==========================================
HF_TOKEN = os.environ.get("HF_TOKEN")
fb_config_str = os.environ.get("FIREBASE_CONFIG")

if not firebase_admin._apps:
    cred_dict = json.loads(fb_config_str)
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://fitnessbuddy-ce7cf-default-rtdb.asia-southeast1.firebasedatabase.app/'
    })

# Load NCD database (CSV must be present at runtime)
try:
    df = pd.read_csv("ncd_database.csv")
except Exception as e:
    print(f"[WARNING] Could not load ncd_database.csv: {e}")
    df = pd.DataFrame()


def fetch_user_context(user_id: str):
    """
    Fetches and maps user data from the new flat database schema.
    """
    try:
        user_ref     = db.reference(f'users/{user_id}').get() or {}
        goals_ref    = db.reference(f'user_goals/{user_id}').get() or {}
        chatctx_ref  = db.reference(f'chatbot_context/{user_id}').get() or {}

        raw_bmi     = user_ref.get('bmi', 0.0)
        rounded_bmi = round(float(raw_bmi), 2)

        conversational        = chatctx_ref.get('conversationalMemories', []) if isinstance(chatctx_ref, dict) else []
        medical_constraints_list = []
        lifestyle_list           = []

        for mem in conversational:
            try:
                mtype = mem.get('type')
                text  = mem.get('fact') or mem.get('text') or mem.get('content') or ''
                if not text:
                    continue
                if mtype == "HEALTH_CONSTRAINT":
                    medical_constraints_list.append(text)
                elif mtype == "LIFESTYLE":
                    lifestyle_list.append(text)
            except Exception:
                continue

        medical_constraints = " | ".join(medical_constraints_list).strip()
        lifestyle           = " | ".join(lifestyle_list).strip()

        return {
            "name":             user_ref.get('name', 'User'),
            "age":              user_ref.get('age', 'Not Set'),
            "bmi":              rounded_bmi,
            "condition":        "General NCD",
            "status":           user_ref.get('status', 'Unknown'),
            "fitness_level":    user_ref.get('fitnessLevel', 'Beginner'),
            "activity_styles":  user_ref.get('activityStyles', []),
            "mins_per_session": goals_ref.get('sessionDuration', 30),
            "weekly_mvpa_goal": goals_ref.get('weeklyMvpaGoal', 150),
            "workout_days":     goals_ref.get('workoutDays', []),
            "medical_constraints": medical_constraints,
            "lifestyle":           lifestyle,
            "mvpa_status":      chatctx_ref.get('mvpaStatus', ''),
            "recommendation":   chatctx_ref.get('recommendation', ''),
        }
    except Exception as e:
        print(f"Error fetching user context: {e}")
        return None


def fetch_all_activities():
    try:
        activities_ref = db.reference('exercise_library').get()
        all_exercises  = []
        if activities_ref:
            for workout_type, exercises in activities_ref.items():
                if isinstance(exercises, dict):
                    for ex_id, details in exercises.items():
                        all_exercises.append({
                            "id":          ex_id,
                            "name":        details.get('name', 'Unknown'),
                            "intensity":   details.get('impactLevel', 'Moderate'),
                            "description": details.get('description', ''),
                            "instructions":details.get('instructions', []),
                            "type":        workout_type,
                            "metValue":    details.get('metValue', 3.0),
                            "typicalSessionMin":    details.get('typicalSessionMin', 10),
                        })
        return all_exercises
    except Exception:
        return []


def fetch_chat_history(user_id: str):
    try:
        sessions_ref = db.reference(f'chat_sessions/{user_id}').get() or {}
        formatted_history = []

        for session_id in sessions_ref.keys():
            msgs_ref = db.reference(f'chat_messages/{session_id}').get() or {}
            if not msgs_ref:
                continue
            for msg_key in sorted(msgs_ref.keys()):
                msg = msgs_ref[msg_key]
                role = msg.get('role', '')
                text = msg.get('text', '')
                if not text:
                    continue
                if role == 'user':
                    formatted_history.append({"role": "user", "content": text})
                elif role == 'chatbot':
                    formatted_history.append({"role": "assistant", "content": text})

        return formatted_history[-50:]
    except Exception as e:
        print(f"Error fetching chat history: {e}")
        return []


def fetch_user_progress(user_id: str):
    try:
        user_node    = db.reference(f'users/{user_id}').get()       or {}
        goals_node   = db.reference(f'user_goals/{user_id}').get()  or {}
        chatctx_ref  = db.reference(f'chatbot_context/{user_id}').get() or {}

        last_updated_ms = user_node.get('lastUpdated')
        streak_days     = user_node.get('streakDays', 0)

        if last_updated_ms:
            try:
                last_active_dt   = datetime.datetime.fromtimestamp(int(last_updated_ms) / 1000.0)
                last_active_date = last_active_dt.date()
                today            = datetime.date.today()
                days_since_last  = (today - last_active_date).days
            except Exception:
                days_since_last = 999
        else:
            days_since_last = 999

        mvpa = chatctx_ref.get('mvpaStatus')
        if mvpa == "AHEAD_OF_TARGET":
            return {"status": "crushing_it"}

        today         = datetime.date.today()
        iso_week_str  = today.strftime("%Y-W%W")
        weekly_node   = db.reference(f'weekly_summaries/{user_id}/{iso_week_str}').get() or {}
        weekly_done_mins = weekly_node.get('totalDurationMinutes', 0)
        weekly_goal_mins = goals_node.get('weeklyMvpaGoal', 150)

        if days_since_last >= 4:
            status = "ghosted"
        elif 1 < days_since_last < 4:
            status = "slipping"
        elif weekly_done_mins >= (weekly_goal_mins - 30) and days_since_last <= 1:
            status = "almost_done"
        elif streak_days >= 3 and days_since_last <= 1:
            status = "crushing_it"
        else:
            status = "slipping"

        return {"status": status}
    except Exception as e:
        print(f"Error fetching progress for {user_id}: {e}")
        return {"status": "slipping"}
