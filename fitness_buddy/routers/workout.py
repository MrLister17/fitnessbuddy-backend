import datetime
from fastapi import APIRouter, HTTPException
from huggingface_hub import InferenceClient
from ..firebase_utils import (
    fetch_user_context, 
    fetch_all_activities, 
    fetch_chat_history
)
from ..rag_utils import retrieve_facts
from ..prompts import SYSTEM_PROMPT_WORKOUT
from firebase_admin import db

router = APIRouter()

HF_TOKEN = __import__('os').environ.get("HF_TOKEN")
client = InferenceClient(model="meta-llama/Llama-4-Scout-17B-16E-Instruct", token=HF_TOKEN)


@router.post("/generate_workout")
async def generate_workout(request: dict):
    try:
        user_id = request.get("user_id")
        user_query = request.get("user_query")

        user_data = fetch_user_context(user_id)
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")

        retrieved_facts, facts_label = retrieve_facts(user_query)

        available_menu = fetch_all_activities()
        menu_text = "\n".join([
            f"ID:{ex['id']}|Name:{ex['name']}|Type:{ex['type']}|Int:{ex['intensity']}|MET:{ex['metValue']}|Desc:{ex['description']}"
            for ex in available_menu
        ])

        formatted_history = fetch_chat_history(user_id)

        system_prompt = SYSTEM_PROMPT_WORKOUT.format(
            mins_per_session=user_data['mins_per_session'],
            menu_text=menu_text,
            facts_label=facts_label,
            retrieved_facts=retrieved_facts,
            name=user_data['name'],
            age=user_data['age'],
            bmi=user_data['bmi'],
            status=user_data['status'],
            fitness_level=user_data['fitness_level'],
            weekly_mvpa_goal=user_data['weekly_mvpa_goal'],
            medical_constraints=user_data['medical_constraints'] or 'None noted',
            lifestyle=user_data['lifestyle'] or 'None noted',
            recommendation=user_data['recommendation'] or 'N/A'
        )

        messages = [{"role": "system", "content": system_prompt}] + formatted_history + [{"role": "user", "content": user_query}]
        response = client.chat_completion(messages=messages, max_tokens=600, temperature=0.1)
        ai_answer = response.choices[0].message.content

        today_session_key = f"session_{datetime.date.today().strftime('%Y%m%d')}_{user_id[:8]}"
        timestamp = int(datetime.datetime.now().timestamp())
        msg_base  = f"msg_{timestamp}"

        db.reference(f'chat_sessions/{user_id}/{today_session_key}').update({
            "sessionStart": timestamp,
            "sessionEnd":   timestamp,
            "summary":      user_query[:80]
        })
        db.reference(f'chat_messages/{today_session_key}').update({
            f"{msg_base}_u": {"role": "user",    "text": user_query, "time": timestamp},
            f"{msg_base}_a": {"role": "chatbot", "text": ai_answer,          "time": timestamp + 1},
        })

        db.reference('Lester').push({
            "user":     user_data['name'],
            "query":    user_query,
            "response": ai_answer,
            "time":     str(datetime.datetime.now())
        })

        return {"status": "success", "ai_response": ai_answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
