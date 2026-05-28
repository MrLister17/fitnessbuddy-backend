from fastapi import APIRouter, HTTPException
from huggingface_hub import InferenceClient
from ..firebase_utils import fetch_user_context, fetch_user_progress
from ..prompts import PROMPT_CRUSHING_IT, PROMPT_ALMOST_DONE, PROMPT_GHOSTED, PROMPT_SLIPPING

router = APIRouter()

HF_TOKEN = __import__('os').environ.get("HF_TOKEN")
client = InferenceClient(model="meta-llama/Llama-4-Scout-17B-16E-Instruct", token=HF_TOKEN)


@router.get("/get_progress_reminder/{user_id}")
async def get_progress_reminder(user_id: str):
    try:
        user_data = fetch_user_context(user_id)
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")

        progress_data = fetch_user_progress(user_id)
        state = progress_data['status']

        if state == "crushing_it":
            system_prompt = PROMPT_CRUSHING_IT.format(
                name=user_data['name'],
                fitness_level=user_data['fitness_level'],
                weekly_mvpa_goal=user_data['weekly_mvpa_goal']
            )
        elif state == "almost_done":
            system_prompt = PROMPT_ALMOST_DONE.format(
                name=user_data['name'],
                weekly_mvpa_goal=user_data['weekly_mvpa_goal'],
                mins_per_session=user_data['mins_per_session']
            )
        elif state == "ghosted":
            system_prompt = PROMPT_GHOSTED.format(
                name=user_data['name'],
                mins_per_session=user_data['mins_per_session']
            )
        else:
            system_prompt = PROMPT_SLIPPING.format(name=user_data['name'])

        response = client.chat_completion(
            messages=[{"role": "system", "content": system_prompt}],
            max_tokens=80,
            temperature=0.7
        )

        return {
            "status": "success",
            "state": state,
            "reminder_text": response.choices[0].message.content.strip()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
