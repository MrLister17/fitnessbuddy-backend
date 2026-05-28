import random
from fastapi import APIRouter, HTTPException
from huggingface_hub import InferenceClient
from ..firebase_utils import fetch_user_context
from ..prompts import PROMPT_HEALTH_TIP_TAILORED, PROMPT_HEALTH_TIP_GENERAL

router = APIRouter()

HF_TOKEN = __import__('os').environ.get("HF_TOKEN")
client = InferenceClient(model="meta-llama/Llama-4-Scout-17B-16E-Instruct", token=HF_TOKEN)


@router.get("/get_health_tip/{user_id}")
async def get_health_tip(user_id: str):
    try:
        user_data = fetch_user_context(user_id)
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")

        is_tailored = random.random() < 0.40

        if is_tailored:
            sub_topic = random.choice([
                "diet and nutrition",
                "safe daily movement",
                "stress management",
                "sleep and physical recovery"
            ])
            system_prompt = PROMPT_HEALTH_TIP_TAILORED.format(
                name=user_data['name'],
                sub_topic=sub_topic,
                bmi=user_data['bmi'],
                status=user_data['status'],
                fitness_level=user_data['fitness_level']
            )
        else:
            sub_topic = random.choice([
                "daily hydration",
                "posture and spine health",
                "healthy Filipino food swaps",
                "mental clarity and breathing",
                "improving sleep hygiene"
            ])
            system_prompt = PROMPT_HEALTH_TIP_GENERAL.format(sub_topic=sub_topic)

        response = client.chat_completion(
            messages=[{"role": "system", "content": system_prompt}],
            max_tokens=80,
            temperature=0.8
        )

        return {
            "status": "success",
            "health_tip": response.choices[0].message.content.strip()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
