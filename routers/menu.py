from fastapi import APIRouter

from schemas.menu import MenuResponse
from services.menu_service import get_active_menus, get_menu_detail

router = APIRouter(tags=["Menu"])


@router.get("/menus", response_model=list[MenuResponse])
async def list_menus():
    """List all active and available menus (public)."""
    return await get_active_menus()


@router.get("/menus/{menu_id}", response_model=MenuResponse)
async def menu_detail(menu_id: str):
    """Get a single active and available menu by ID (public)."""
    return await get_menu_detail(menu_id)
