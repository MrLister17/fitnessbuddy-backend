# fitness_buddy/firebase_utils.py
import firebase_admin
from firebase_admin import db
from datetime import date


def fetch_user_context(user_id: str):
    """
    Fetches and maps user data from the new flat database schema.
    (Your original implementation - unchanged)
    """
    try:
        user_ref = db.reference(f'users/{user_id}').get() or {}
        goals_ref = db.reference(f'user_goals/{user_id}').get() or {}
        chatctx_ref = db.reference(f'chatbot_context/{user_id}').get() or {}

        raw_bmi = user_ref.get('bmi', 0.0)
        rounded_bmi = round(float(raw_bmi), 2)

        conversational = chatctx_ref.get('conversationalMemories', []) if isinstance(chatctx_ref, dict) else []
        medical_constraints_list = []
        lifestyle_list = []

        for mem in conversational:
            try:
                mtype = mem.get('type')
                text = mem.get('fact') or mem.get('text') or mem.get('content') or ''
                if not text:
                    continue
                if mtype == "HEALTH_CONSTRAINT":
                    medical_constraints_list.append(text)
                elif mtype == "LIFESTYLE":
                    lifestyle_list.append(text)
            except Exception:
                continue

        medical_constraints = " | ".join(medical_constraints_list).strip()
        lifestyle = " | ".join(lifestyle_list).strip()

        return {
            "name": user_ref.get('name', 'User'),
            "age": user_ref.get('age', 'Not Set'),
            "bmi": rounded_bmi,
            "condition": "General NCD",
            "status": user_ref.get('status', 'Unknown'),
            "fitness_level": user_ref.get('fitnessLevel', 'Beginner'),
            "activity_styles": user_ref.get('activityStyles', []),
            "mins_per_session": goals_ref.get('sessionDuration', 30),
            "weekly_mvpa_goal": goals_ref.get('weeklyMvpaGoal', 150),
            "workout_days": goals_ref.get('workoutDays', []),
            "medical_constraints": medical_constraints,
            "lifestyle": lifestyle,
            "mvpa_status": chatctx_ref.get('mvpaStatus', ''),
            "recommendation": chatctx_ref.get('recommendation', ''),
        }
    except Exception as e:
        print(f"Error fetching user context: {e}")
        return None


# ==================== NEW HELPERS FOR ACTIVITY-AWARE TIPS ====================

def fetch_latest_activity(user_id: str):
    """Returns the most recent activity document or None."""
    try:
        ref = db.reference(f'users/{user_id}/activities')
        # Get the single most recent activity by timestamp
        result = ref.order_by_child('timestamp').limit_to_last(1).get()
        if not result:
            return None
        # RTDB returns a dict with one entry
        return list(result.values())[0]
    except Exception as e:
        print(f"Error fetching latest activity for {user_id}: {e}")
        return None


def fetch_weekly_progress(user_id: str):
    """Returns completed minutes this ISO week + days remaining (Mon–Sun)."""
    try:
        today = date.today()
        iso_week_str = today.strftime("%Y-W%W")
        weekly_node = db.reference(f'weekly_summaries/{user_id}/{iso_week_str}').get() or {}
        completed = weekly_node.get('totalMinutes', 0) or 0

        # Days remaining in ISO week (Monday = 0 ... Sunday = 6)
        days_remaining = max(6 - today.weekday(), 0)

        return {
            "completed_minutes": completed,
            "days_remaining": days_remaining
        }
    except Exception as e:
        print(f"Error fetching weekly progress for {user_id}: {e}")
        return {"completed_minutes": 0, "days_remaining": 3}
