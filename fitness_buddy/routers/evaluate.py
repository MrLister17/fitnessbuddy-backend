from fastapi import APIRouter, HTTPException
from huggingface_hub import InferenceClient
from ..rag_utils import retrieve_facts
from ..prompts import SYSTEM_PROMPT_EVALUATE

router = APIRouter()

HF_TOKEN = __import__('os').environ.get("HF_TOKEN")
client = InferenceClient(model="meta-llama/Llama-4-Scout-17B-16E-Instruct", token=HF_TOKEN)


@router.post("/evaluate_query")
async def evaluate_query(request: dict):
    try:
        user_query = request.get("user_query")
        condition = request.get("condition", "General NCD")
        bmi = request.get("bmi", 22.0)

        retrieved_facts, facts_label = retrieve_facts(user_query)

        system_prompt = SYSTEM_PROMPT_EVALUATE.format(
            condition=condition,
            bmi=bmi,
            facts_label=facts_label,
            retrieved_facts=retrieved_facts
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_query}
        ]

        response = client.chat_completion(
            messages=messages,
            max_tokens=300,
            temperature=0.01
        )

        ai_answer = response.choices[0].message.content.strip()
        return {"status": "success", "ai_response": ai_answer}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
