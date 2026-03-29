import uuid
import os
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageOps

PROFILE_PICS_DIR = Path("media/profile_pics")


def process_profile_image(content: bytes) -> str:
    with Image.open(BytesIO(content)) as original:
        img = ImageOps.exif_transpose(original)
        img = ImageOps.fit(img, (300, 300))

        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")
        
        filename = f"{uuid.uuid4().hex}.jpg"
        filepath = PROFILE_PICS_DIR / filename
        
        PROFILE_PICS_DIR.mkdir(parents=True, exist_ok=True)

        img.save(filepath, "JPEG", quality=85, optimize=True)

    return filename


# UNSAFE IMAGE PROCESS FOR PATH TRAVERSAL
def process_profile_image_unsafe(content: bytes, filename: str) -> str:
    filepath = os.path.join(PROFILE_PICS_DIR, filename)
    os.makedirs(PROFILE_PICS_DIR, exist_ok=True)
    with open(filepath, "wb") as f:
        f.write(content)
    
    return filename


def delete_profile_image(filename: str | None) -> None:
    if filename is None:
        return

    filepath = PROFILE_PICS_DIR / filename
    if filepath.exists():
        filepath.unlink()