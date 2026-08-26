import os
from pathlib import Path

from google import genai
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "generated"

W, H = 1080, 1800


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name, "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "y", "on"}


def _client() -> genai.Client:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")
    return genai.Client(api_key=key)


def generate_background(quote: str, output_path: Path) -> Path:
    """
    Generate a clean visual background with Gemini, then let Pillow place
    the exact Hindi quote on top. This avoids relying on Gemini for exact
    Hindi typography while still making the visual itself Gemini-generated.
    """
    model = (
        os.getenv("GEMINI_IMAGE_MODEL", "").strip()
        or "gemini-3.1-flash-image"
    )

    prompt = f"""
Create a premium vertical 3:5 Instagram quote-page background inspired by
the emotion and meaning of this Hindi thought:

{quote}

Visual direction:
- elegant Hindi diary / life-quotes aesthetic
- sophisticated, cinematic, calm and emotionally meaningful
- premium editorial photography / artistic illustration feel
- subtle depth, soft natural light, tasteful textures
- leave generous clean negative space through the center/lower-middle for
  an exact Hindi quote to be added later
- composition must work at 1080 x 1800
- visually interesting but not busy
- use a refined warm neutral palette with subtle complementary tones
- no people unless they are clearly useful to the concept
- no text
- no letters
- no typography
- no captions
- no logos
- no watermark
- do not render the Hindi quote inside the image
""".strip()

    response = _client().models.generate_content(
        model=model,
        contents=prompt,
    )

    generated = None
    for part in response.parts:
        if getattr(part, "inline_data", None) is not None:
            generated = part.as_image()
            break

    if generated is None:
        raise RuntimeError(
            f"Gemini image generation returned no image. Model: {model}"
        )

    image = generated.convert("RGB")
    image = ImageOps.fit(
        image,
        (W, H),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, "JPEG", quality=94, optimize=True)
    return output_path


def use_gemini_image() -> bool:
    return _bool_env("USE_GEMINI_IMAGE", False)
