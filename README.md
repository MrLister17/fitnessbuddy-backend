# Fitness Buddy Backend API

Modular version of the Fitness Buddy FastAPI backend.

## Project Structure

fitness_buddy/
├── main.py
├── firebase_utils.py
├── rag_utils.py
├── prompts.py
├── models.py
├── requirements.txt
└── routers/
├── root.py
├── progress.py
├── health_tip.py
├── workout.py
├── evaluate.py
└── weekly_plan.py





## Local Run

```bash

cd fitness_buddy

pip install -r requirements.txt

uvicorn main:app --reload



Deployment on Render

Build Command:

pip install -r fitness_buddy/requirements.txt

Start Command:

cd fitness_buddy && uvicorn main:app --host 0.0.0.0 --port $PORT



Environment Variables Needed





HF_TOKEN



FIREBASE_CONFIG
