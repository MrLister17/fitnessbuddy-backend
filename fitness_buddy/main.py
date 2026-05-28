import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import all routers
from .routers.root import router as root_router
from .routers.progress import router as progress_router
from .routers.health_tip import router as health_tip_router
from .routers.workout import router as workout_router
from .routers.evaluate import router as evaluate_router
from .routers.weekly_plan import router as weekly_plan_router

app = FastAPI(title="Fitness Buddy API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routers
app.include_router(root_router)
app.include_router(progress_router)
app.include_router(health_tip_router)
app.include_router(workout_router)
app.include_router(evaluate_router)
app.include_router(weekly_plan_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
