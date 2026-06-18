import os
from fastapi import APIRouter, HTTPException
from huggingface_hub import InferenceClient
from ..firebase_utils import fetch_user_context, fetch_user_progress, fetch_latest_activity

router = APIRouter()

# Secure fallback so the app builds on Render even if the token is missing temporarily
HF_TOKEN = os.environ.get("HF_TOKEN", "")
if not HF_TOKEN:
    print("WARNING: HF_TOKEN environment variable is missing!")

client = InferenceClient(model="meta-llama/Llama-4-Scout-17B-16E-Instruct", token=HF_TOKEN)

PROMPT_HEALTH_TIP_ACTIVITY_AWARE = """You are Fitness Buddy, a warm, encouraging cardio coach helping busy Filipinos build sustainable daily movement habits to prevent NCDs.

User profile:
- Name: {name}
- Fitness level: {fitness_level}
- Status: {status}
- Weekly MVPA goal: {weekly_mvpa_goal} minutes
- Lifestyle: {lifestyle}
- Medical constraints: {medical_constraints}

Last activity:
{last_activity_block}

Week progress (ISO week, Monday–Sunday):
- Completed: {completed_minutes} / {weekly_mvpa_goal} minutes
- Days left this week: {days_remaining}

Coaching focus: {coaching_mode}

Write exactly 1–2 short, natural, friendly sentences (max 55 words).
Rules:
- Start with a warm, specific acknowledgment of the last activity.
- Give ONE concrete, safe cardio-only suggestion (walking, brisk walking, jogging, cycling, or simple home cardio circuits only).
- Match the coaching focus: progress = build on it; recovery = light active recovery; catch_up = gentle nudge with easy idea because week is ending; welcome = encouraging first step.
- Use simple, supportive language. No medical advice. No bullet points. No jargon.
- End on a positive, motivating note.
"""


def _compute_coaching_mode(last_activity, days_remaining, completed_minutes, target_minutes):
    # Explicitly check if last_activity is empty or None
    if not last_activity or not isinstance(last_activity, dict):
        return "welcome"

    completed_minutes = completed_minutes or 0
    target_minutes = target_minutes or 150
    days_remaining = days_remaining or 3

    behind_goal = completed_minutes < (target_minutes * 0.7)

    if behind_goal and days_remaining <= 2:
        return "catch_up"
    
    if last_activity.get("intensity") == "high" or int(last_activity.get("durationMinutes", 0) or 0) >= 40:
        return "recovery"
        
    return "progress"


@router.get("/get_health_tip/{user_id}")
async def get_health_tip(user_id: str):
    try:
        # 1. Fetch user context safely
        user = fetch_user_context(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        last_activity = fetch_latest_activity(user_id)
        week = fetch_user_progress(user_id) or {}

        # 2. Compute the coaching mode
        coaching_mode = _compute_coaching_mode(
            last_activity=last_activity,
            days_remaining=week.get("days_remaining", 3),
            completed_minutes=week.get("completed_minutes", 0),
            target_minutes=user.get("weekly_mvpa_goal", 150),
        )

        # 3. Format the last activity block safely
        if last_activity and isinstance(last_activity, dict):
            last_block = (
                f"- Type: {last_activity.get('type', 'movement')}\n"
                f"- Duration: {last_activity.get('durationMinutes', 0)} minutes\n"
                f"- Intensity: {last_activity.get('intensity', 'moderate')}\n"
                f"- Date: {str(last_activity.get('timestamp', ''))[:10]}"
            )
        else:
            last_block = "- No recent activity recorded yet."

        # 4. Build system instruction
        system_prompt = PROMPT_HEALTH_TIP_ACTIVITY_AWARE.format(
            name=user.get("name", "there"),
            fitness_level=user.get("fitness_level", "Beginner"),
            status=user.get("status", "General NCD"),
            weekly_mvpa_goal=user.get("weekly_mvpa_goal", 150),
            lifestyle=user.get("lifestyle", ""),
            medical_constraints=user.get("medical_constraints", ""),
            last_activity_block=last_block,
            completed_minutes=week.get("completed_minutes", 0),
            days_remaining=week.get("days_remaining", 3),
            coaching_mode=coaching_mode,
        )

        # 5. Call InferenceClient safely with user context
        response = client.chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Give me my personalized health tip for today."}
            ],
            max_tokens=65,
            temperature=0.7,
        )

        tip = response.choices[0].message.content.strip()
        return {"status": "success", "health_tip": tip}

    except Exception as e:
        # Log the error to Render logs so you can see it
        print(f"Error in get_health_tip: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
