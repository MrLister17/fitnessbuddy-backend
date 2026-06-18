import os
from datetime import date
from fastapi import APIRouter, HTTPException
from huggingface_hub import InferenceClient
from ..firebase_utils import (
    fetch_user_context,
    fetch_latest_activity,
    fetch_weekly_progress,
)
from ..prompts import PROMPT_HEALTH_TIP_ACTIVITY_AWARE

router = APIRouter()

HF_TOKEN = os.environ.get("HF_TOKEN")
client = InferenceClient(
    model="meta-llama/Llama-4-Scout-17B-16E-Instruct",
    token=HF_TOKEN
)


def _compute_coaching_mode(
    last_activity: dict | None,
    days_remaining: int,
    completed_minutes: int,
    target_minutes: int
) -> str:
    if not last_activity:
        return "welcome"

    behind_goal = completed_minutes < (target_minutes * 0.7)

    if behind_goal and days_remaining <= 2:
        return "catch_up"
    if last_activity.get("intensity") == "high" or last_activity.get("durationMinutes", 0) >= 40:
        return "recovery"
    return "progress"


@router.get("/get_health_tip/{user_id}")
async def get_health_tip(user_id: str):
    try:
        user = fetch_user_context(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        last_activity = fetch_latest_activity(user_id)
        week_progress = fetch_weekly_progress(user_id)

        coaching_mode = _compute_coaching_mode(
            last_activity=last_activity,
            days_remaining=week_progress.get("days_remaining", 3),
            completed_minutes=week_progress.get("completed_minutes", 0),
            target_minutes=user.get("weekly_mvpa_goal", 150),
        )

        # Build clean last activity block for the prompt
        if last_activity:
            last_block = (
                f"- Type: {last_activity.get('type', 'movement')}\n"
                f"- Duration: {last_activity.get('durationMinutes', 0)} minutes\n"
                f"- Intensity: {last_activity.get('intensity', 'moderate')}\n"
                f"- Date: {str(last_activity.get('timestamp', ''))[:10]}"
            )
        else:
            last_block = "- No recent activity recorded yet."

        system_prompt = PROMPT_HEALTH_TIP_ACTIVITY_AWARE.format(
            name=user.get("name", "there"),
            fitness_level=user.get("fitness_level", "Beginner"),
            status=user.get("status", "General NCD"),
            weekly_mvpa_goal=user.get("weekly_mvpa_goal", 150),
            lifestyle=user.get("lifestyle", ""),
            medical_constraints=user.get("medical_constraints", ""),
            last_activity_block=last_block,
            completed_minutes=week_progress.get("completed_minutes", 0),
            days_remaining=week_progress.get("days_remaining", 3),
            coaching_mode=coaching_mode,
        )

        response = client.chat_completion(
            messages=[{"role": "system", "content": system_prompt}],
            max_tokens=65,
            temperature=0.7,
        )

        tip = response.choices[0].message.content.strip()
        return {
            "status": "success",
            "health_tip": tip
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
