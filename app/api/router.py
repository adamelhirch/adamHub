from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.assistant import router as assistant_router
from app.api.groceries import router as groceries_router
from app.api.recipes import router as recipes_router
from app.api.meal_plans import router as meal_plans_router
from app.api.pantry import router as pantry_router
from app.api.supermarket import router as supermarket_router
from app.api.skill import router as skill_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(assistant_router)
api_router.include_router(groceries_router)
api_router.include_router(recipes_router)
api_router.include_router(meal_plans_router)
api_router.include_router(pantry_router)
api_router.include_router(supermarket_router)
api_router.include_router(skill_router)
