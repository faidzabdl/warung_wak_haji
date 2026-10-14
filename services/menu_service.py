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


async def get_menus() -> list[dict]:
    """Return all active menus (is_active=True), including is_available=False.

    is_available=False menus are returned so the buyer UI can show a disabled
    'HABIS' button. Availability is validated at order creation time (RPC).
    """
    client = get_anon_client()
    response = (
        client.table("menus")
        .select("*")
        .eq("is_active", True)
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
    """Return all active menus (is_active=True) for seller management view."""
    client = get_service_client()
    response = (
        client.table("menus")
        .select("*")
        .eq("is_active", True)
        .order("created_at", desc=True)
        .execute()
    )
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
            updates[field] = value

    if not updates:
        raise HTTPException(
            status_code=422,
            detail={"error": {"code": "VALIDATION_ERROR", "message": "No fields to update"}},
        )

    if "price" in updates:
        updates["price"] = float(updates["price"])

    response = (
        client.table("menus")
        .update(updates)
        .eq("id", menu_id)
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "MENU_NOT_FOUND", "message": "Menu not found"}},
        )
    return response.data[0]


async def set_menu_availability(menu_id: str, is_available: bool) -> dict:
    """Toggle menu availability. Raises 404 if the menu does not exist."""
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


async def delete_menu(menu_id: str) -> None:
    """Soft-delete a menu by setting is_active=False.

    Raises 404 if the menu does not exist.
    """
    client = get_service_client()
    response = (
        client.table("menus")
        .update({"is_active": False})
        .eq("id", menu_id)
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "MENU_NOT_FOUND", "message": "Menu not found"}},
        )



# ---------------------------------------------------------------------------
# Image upload
# ---------------------------------------------------------------------------


async def upload_menu_image(file: UploadFile) -> str:
    """Validate and upload a menu image to Supabase Storage.

    Returns the public URL of the uploaded image.
    """
    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "INVALID_FILE_TYPE",
                    "message": f"Unsupported file type '{file.content_type}'. Allowed: JPEG, PNG, WebP.",
                }
            },
        )

    data = await file.read()

    if len(data) > _MAX_FILE_SIZE:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "FILE_TOO_LARGE",
                    "message": f"File exceeds the 5 MB limit ({len(data) / 1_048_576:.1f} MB received).",
                }
            },
        )

    if not _check_magic(file.content_type, data):
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "INVALID_FILE_CONTENT",
                    "message": "File content does not match the declared content type.",
                }
            },
        )

    ext = _CONTENT_TYPE_TO_EXT[file.content_type]
    filename = f"{uuid4()}.{ext}"

    client = get_service_client()
    client.storage.from_("menu-images").upload(
        path=filename,
        file=data,
        file_options={"content-type": file.content_type},
    )

    public_url = client.storage.from_("menu-images").get_public_url(filename)
    return public_url
