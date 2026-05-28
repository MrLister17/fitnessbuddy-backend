from pydantic import BaseModel
from typing import List, Optional

class WorkoutRequest(BaseModel):
    user_id: str
    user_query: str
    chat_history: list = []


class EvalRequest(BaseModel):
    user_query: str
    condition: str = "General NCD"
    bmi: float = 22.0
