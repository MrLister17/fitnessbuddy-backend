import datetime
from datetime import timedelta
from fastapi import APIRouter, HTTPException
from huggingface_hub import InferenceClient
from ..firebase_utils import fetch_user_context, fetch_all_activities
from ..prompts import SYSTEM_PROMPT_WEEKLY_PLAN
from firebase_admin import db

router = APIRouter()

HF_TOKEN = __import__('os').environ.get("HF_TOKEN")
client = InferenceClient(model="meta-llama/Llama-4-Scout-17B-16E-Instruct", token=HF_TOKEN)


@router.post("/generate_weekly_plan")
async def generate_weekly_plan(request: dict):
    try:
        user_id = request.get("user_id")
        user_data = fetch_user_context(user_id)
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")

        full_menu = fetch_all_activities()

        styles = user_data.get('activity_styles', [])
        clean_styles = [s.strip() for s in styles]

        if clean_styles:
            menu = [ex for ex in full_menu if ex['type'] in clean_styles]
        else:
            menu = full_menu

        exercise_lookup = {ex['id']: ex['type'] for ex in menu}

        menu_text = "\n".join([
            f"ID:{ex['id']} | Type:{ex['type']} | Duration:{ex['typicalSessionMin']}m | Intensity:{ex['intensity']} | Description:{ex['description']}"
            for ex in menu
        ])

        start_date = datetime.date.today()
        end_date = start_date + timedelta(days=13)
        workout_days = [day.strip().capitalize() for day in user_data.get('workout_days', [])]

        date_logic_string = ""
        for i in range(14):
            current = start_date + datetime.timedelta(days=i)
            day_name = current.strftime("%A")
            if day_name in workout_days:
                date_logic_string += f"- {current} ({day_name}): MUST be a Workout Day\n"
            else:
                date_logic_string += f"- {current} ({day_name}): MUST be a Rest Day\n"

        target_mins = user_data.get('mins_per_session', 30)

        system_prompt = SYSTEM_PROMPT_WEEKLY_PLAN.format(
            start_date=start_date,
            end_date=end_date,
            menu_text=menu_text,
            bmi=user_data['bmi'],
            status=user_data['status'],
            fitness_level=user_data['fitness_level'],
            medical_constraints=user_data['medical_constraints'] or 'None',
            date_logic_string=date_logic_string,
            target_mins=target_mins
        )

        response = client.chat_completion(
            messages=[{"role": "system", "content": system_prompt}],
            max_tokens=1000,
            temperature=0.1
        )
        ai_answer = response.choices[0].message.content.strip()

        lines = [l.strip() for l in ai_answer.splitlines() if '|' in l]
        for line in lines:
            try:
                date_part, ids_part = line.split('|', 1)
                date_str = date_part.strip()

                if "Rest Day" in ids_part:
                    db.reference(f'calendar_schedules/{user_id}/{date_str}').set({
                        "daySummary": "REST",
                        "tasks": {}
                    })
                    continue

                exercise_ids = [eid.strip() for eid in ids_part.split(',') if eid.strip()]

                tasks = {}
                for i, eid in enumerate(exercise_ids, start=1):
                    category = exercise_lookup.get(eid, "General")
                    tasks[f"task_{str(i).zfill(3)}"] = {
                        "category": category,
                        "exerciseId": eid,
                        "priority": i,
                        "status": "PENDING",
                        "title": eid.replace('-', ' ').title()
                    }

                db.reference(f'calendar_schedules/{user_id}/{date_str}').set({
                    "daySummary": "SCHEDULED",
                    "tasks": tasks
                })
            except Exception as parse_err:
                print(f"[WeeklyPlan] Could not parse line '{line}': {parse_err}")
                continue

        return {"status": "success", "ai_response": ai_answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
