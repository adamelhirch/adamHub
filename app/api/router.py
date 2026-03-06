from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.calendar import router as calendar_router
from app.api.events import router as events_router
from app.api.finances import router as finances_router
from app.api.goals import router as goals_router
from app.api.groceries import router as groceries_router
from app.api.habits import router as habits_router
from app.api.linear_hub import router as linear_router
from app.api.meal_plans import router as meal_plans_router
from app.api.notes import router as notes_router
from app.api.pantry import router as pantry_router
from app.api.recipes import router as recipes_router
from app.api.skill import router as skill_router
from app.api.subscriptions import router as subscriptions_router
from app.api.tasks import router as tasks_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(tasks_router)
api_router.include_router(finances_router)
api_router.include_router(groceries_router)
api_router.include_router(recipes_router)
api_router.include_router(meal_plans_router)
api_router.include_router(calendar_router)
api_router.include_router(habits_router)
api_router.include_router(goals_router)
api_router.include_router(events_router)
api_router.include_router(subscriptions_router)
api_router.include_router(pantry_router)
api_router.include_router(notes_router)
api_router.include_router(linear_router)
api_router.include_router(skill_router)
