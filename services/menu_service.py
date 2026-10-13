from uuid import uuid4

from fastapi import HTTPException, UploadFile

from db import get_anon_client, get_service_client
from schemas.menu import MenuCreate, MenuUpdate

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
_MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

_CONTENT_TYPE_TO_EXT = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}

_MAGIC_BYTES: dict[str, bytes] = {
    "image/jpeg": b"\xff\xd8\xff",
    "image/png": b"\x89PNG\r\n\x1a\n",
}


def _check_magic(content_type: str, data: bytes) -> bool:
    """Return True if the file's magic bytes match the declared content-type."""
    if content_type == "image/webp":
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    magic = _MAGIC_BYTES.get(content_type)
    if magic is None:
        return False
    return data[: len(magic)] == magic


# ---------------------------------------------------------------------------
# Public read functions (anon client — RLS filters active+available)
# ---------------------------------------------------------------------------


async def get_active_menus() -> list[dict]:
    """Return all menus visible to the public (is_active=True, is_available=True)."""
    client = get_anon_client()
    response = (
        client.table("menus")
        .select("*")
        .eq("is_active", True)
        .eq("is_available", True)
        .execute()
    )
    return response.data or []


async def get_menu_detail(menu_id: str) -> dict:
    """Return a single active+available menu. Raises 404 if not found."""
    client = get_anon_client()
    response = (
        client.table("menus")
        .select("*")
        .eq("id", menu_id)
        .eq("is_active", True)
        .eq("is_available", True)
        .maybe_single()
        .execute()
    )
    if response.data is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "MENU_NOT_FOUND", "message": "Menu not found"}},
        )
    return response.data


# ---------------------------------------------------------------------------
# Seller management functions (service client — bypasses RLS)
# ---------------------------------------------------------------------------


async def get_all_menus_for_seller() -> list[dict]:
    """Return ALL menus regardless of status, for seller management view."""
    client = get_service_client()
    response = client.table("menus").select("*").order("created_at", desc=True).execute()
    return response.data or []


async def create_menu(data: MenuCreate) -> dict:
    """Insert a new menu row and return it."""
    client = get_service_client()
    payload = data.model_dump()
    # Convert Decimal to float for JSON serialisation
    payload["price"] = float(payload["price"])
    response = client.table("menus").insert(payload).execute()
    return response.data[0]


async def update_menu(menu_id: str, data: MenuUpdate) -> dict:
    """Partial-update a menu. Only fields that are not None are sent to DB.

    Raises 404 if the menu does not exist.
    """
    client = get_service_client()

    # Build update payload from non-None fields only
    updates: dict = {}
    for field, value in data.model_dump().items():
        if value is not None:
            updates[field] = float(value) if field == "price" else value

    if not updates:
        # Nothing to update — fetch and return current state
        response = (
            client.table("menus").select("*").eq("id", menu_id).maybe_single().execute()
        )
        if response.data is None:
            raise HTTPException(
                status_code=404,
                detail={"error": {"code": "MENU_NOT_FOUND", "message": "Menu not found"}},
            )
        return response.data

    response = (
        client.table("menus").update(updates).eq("id", menu_id).execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "MENU_NOT_FOUND", "message": "Menu not found"}},
        )
    return response.data[0]


async def set_availability(menu_id: str, is_available: bool) -> dict:
    """Set is_available on a menu. Returns updated menu."""
    client = get_service_client()
    response = (
        client.table("menus")
        .update({"is_available": is_available})
        .eq("id", menu_id)
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "MENU_NOT_FOUND", "message": "Menu not found"}},
        )
    return response.data[0]


# ---------------------------------------------------------------------------
# Image upload
# ---------------------------------------------------------------------------


async def upload_menu_image(file: UploadFile) -> str:
    """Validate, upload, and return the public URL of a menu image.

    Raises 400 for invalid type or oversized file.
    """
    # 1. Validate content-type header
    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "INVALID_FILE_TYPE",
                    "message": "File must be JPEG, PNG, or WebP",
                }
            },
        )

    # 2. Read file bytes
    data = await file.read()

    # 3. Validate size
    if len(data) > _MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "FILE_TOO_LARGE",
                    "message": "File must not exceed 5 MB",
                }
            },
        )

    # 4. Validate magic bytes
    if not _check_magic(file.content_type, data):
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "INVALID_FILE_TYPE",
                    "message": "File content does not match declared type",
                }
            },
        )

    # 5. Generate new filename
    ext = _CONTENT_TYPE_TO_EXT[file.content_type]
    path = f"{uuid4()}.{ext}"

    # 6. Upload to Supabase Storage
    client = get_service_client()
    client.storage.from_("menu-images").upload(
        path, data, file_options={"content-type": file.content_type}
    )

    # 7. Return the public URL
    url: str = client.storage.from_("menu-images").get_public_url(path)
    return url
