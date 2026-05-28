from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def read_root():
    return {"status": "Online", "mode": "Render is Active and Working"}
