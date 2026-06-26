"""Lily ComfyUI plugin — image generation via local Flux models."""

import json
import logging
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, FileResponse

logger = logging.getLogger("lily-comfyui")

LILY_API = os.environ.get("LILY_API_URL", "http://127.0.0.1:7100")

router = APIRouter(prefix="/api/comfyui", tags=["comfyui"])


def _lily_url():
    return LILY_API


@router.get("/status")
async def comfyui_status():
    """Check ComfyUI status via Lily API."""
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{_lily_url()}/api/comfyui/status", timeout=5.0)
            return resp.json()
    except Exception as e:
        return JSONResponse({"error": f"ComfyUI not reachable: {e}"}, status_code=502)


@router.get("/workflows")
async def list_workflows():
    """List available ComfyUI workflow templates."""
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{_lily_url()}/api/comfyui/workflows", timeout=5.0)
            return resp.json()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)


@router.post("/generate")
async def generate_image(request: Request):
    """Generate an image via ComfyUI through Lily API.

    Body: {prompt, width, height, seed, steps, guidance, denoise,
           input_image, workflow, save_to, timeout}
    """
    import httpx
    body = await request.json()
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{_lily_url()}/api/comfyui/generate",
                json=body,
                timeout=httpx.Timeout(connect=10.0, read=600.0, write=10.0, pool=10.0),
            )
            data = resp.json()
            if resp.status_code == 200 and data.get("ok"):
                images = data.get("images", [])
                if images:
                    img_path = images[0]
                    if "\\" in img_path:
                        img_path = img_path.replace("\\", "/")
                    if not img_path.startswith("/") and ":" in img_path:
                        drive, rest = img_path.split(":", 1)
                        img_path = f"/{drive.lower()}{rest}"
                    data["images_unix"] = [img_path]
            return JSONResponse(data, status_code=resp.status_code)
    except httpx.ConnectError:
        return JSONResponse({"error": "Lily API not running"}, status_code=502)
    except httpx.ReadTimeout:
        return JSONResponse({"error": "Generation timed out"}, status_code=504)
    except Exception as e:
        logger.error(f"ComfyUI generate error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/image/{path:path}")
async def serve_image(path: str):
    """Serve a generated image file."""
    full_path = Path(path)
    if not full_path.exists():
        drive_path = Path(f"/{path}")
        if drive_path.exists():
            full_path = drive_path
    if full_path.exists() and full_path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
        return FileResponse(full_path, media_type=f"image/{full_path.suffix.lstrip('.')}")
    return JSONResponse({"error": "Image not found"}, status_code=404)


def _do_comfyui_generate(**kwargs) -> str:
    """Synchronous wrapper for the tool dispatcher."""
    import httpx
    body = {}
    if "prompt" in kwargs:
        body["prompt"] = kwargs["prompt"]
    if "aspect_ratio" in kwargs:
        body["aspect_ratio"] = kwargs["aspect_ratio"]
    if "width" in kwargs:
        body["width"] = kwargs["width"]
    if "height" in kwargs:
        body["height"] = kwargs["height"]
    if "seed" in kwargs:
        body["seed"] = kwargs["seed"]
    if "steps" in kwargs:
        body["steps"] = kwargs["steps"]
    if "guidance" in kwargs:
        body["guidance"] = kwargs["guidance"]
    if "denoise" in kwargs:
        body["denoise"] = kwargs["denoise"]
    if "input_image" in kwargs:
        body["input_image"] = kwargs["input_image"]
    if "workflow" in kwargs:
        body["workflow"] = kwargs["workflow"]
    if kwargs.get("transparent"):
        body["transparent"] = True
    for pad_key in ("pad_left_px", "pad_top_px", "pad_right_px", "pad_bottom_px",
                     "pad_left_ratio", "pad_top_ratio", "pad_right_ratio", "pad_bottom_ratio"):
        if pad_key in kwargs:
            body[pad_key] = kwargs[pad_key]
    if kwargs.get("force_no_rescale"):
        body["force_no_rescale"] = True
    if kwargs.get("rescale_output"):
        body["rescale_output"] = True
    if kwargs.get("ai_upscale"):
        body["ai_upscale"] = True
    if "save_to" in kwargs:
        body["save_to"] = kwargs["save_to"]
    body["timeout"] = kwargs.get("timeout", 600)

    try:
        resp = httpx.post(
            f"{_lily_url()}/api/comfyui/generate",
            json=body,
            timeout=httpx.Timeout(connect=10.0, read=620.0, write=10.0, pool=10.0),
        )
        data = resp.json()
        if data.get("ok"):
            images = data.get("images", [])
            return json.dumps({
                "ok": True,
                "workflow": data.get("workflow"),
                "images": images,
                "seed": data.get("seed"),
            })
        return json.dumps(data)
    except Exception as e:
        return json.dumps({"error": str(e)})


COMFYUI_TOOL_PROMPT_SECTION = """\
```comfyui_generate
{"prompt": "<description of image to generate or edit instruction>"}
```
Generate, edit, or upscale images using local ComfyUI with Flux models. Args are JSON with these fields:
- "prompt" (required): text prompt describing what to generate or how to edit
- "aspect_ratio": preset ratio for ~1MP output. Available: "1:1" (1024x1024), "4:3" (1152x896), "3:4" (896x1152), "3:2" (1216x832), "2:3" (832x1216), "16:9" (1344x768), "9:16" (768x1344), "21:9" (1536x640), "9:21" (640x1536). Choose based on subject: portrait/full-body → "2:3", landscape → "3:2", phone wallpaper → "9:16", desktop wallpaper → "16:9", panoramic → "21:9". Auto-detects from prompt keywords if omitted.
- "width"/"height": explicit pixel dimensions (snapped to nearest 32px). Overrides aspect_ratio. Use only when you need a specific non-preset size.
- "input_image": path to input image (for img2img, editing, or upscaling)
- "workflow": force a workflow — "text2img", "img2img", "edit", "upscale" (auto-selected if omitted)
- "steps": sampling steps (default 20-24)
- "guidance": guidance scale (default 2.5 for edit, 3.5 for others)
- "denoise": denoise strength for img2img (default 0.65, 1.0 = full regeneration)
- "seed": RNG seed for reproducibility
- "transparent": set true to remove the background and output a PNG with alpha transparency. Uses RMBG-2.0 AI model. Great for avatars, stickers, character art. Automatically adds prompt hints for cleaner edges.
- "pad_left_px"/"pad_top_px"/"pad_right_px"/"pad_bottom_px": outpaint padding in pixels per side (int, snapped to 32px). Use with workflow="outpaint".
- "pad_left_ratio"/"pad_top_ratio"/"pad_right_ratio"/"pad_bottom_ratio": outpaint padding as ratio of image size (float 0.0-1.0, e.g. 0.1 = 10%). _px takes precedence when both set. Default 10% all sides if no padding specified.
- "force_no_rescale": bypass automatic up/downscaling. Use to force oversized or tiny outputs. Default false.
- "rescale_output": after generation, resize output back to original input dimensions using Pillow. Useful for editing large images that get downscaled internally.
- "ai_upscale": when rescale_output is true and output needs enlarging, use the AI upscale workflow instead of Pillow resize. Better quality but slower.
Auto-selects workflow: no input image → text2img, input + edit words → edit (Kontext), input + "upscale" → upscale, input + other → img2img. Use workflow="outpaint" to extend an image beyond its borders. Resolution is ~1MP by default (1024x1024), auto-adjusted for aspect ratio. Small images are auto-upscaled to minimum 256px/side. Images with extreme aspect ratios (>6:1) are rejected."""

COMFYUI_TOOL_SCHEMA = {
    "description": "Generate, edit, or upscale images using local ComfyUI with Flux GGUF models. Auto-selects the best workflow: text2img (no input image), img2img (input image + prompt), edit (input image + edit instructions like 'change hair to blue'), upscale (input image + 'upscale'/'enhance'), outpaint (extend beyond borders). Resolution is ~1MP by default, auto-scaled to model constraints (256px-1440px per side, max 2MP). Use aspect_ratio to set the shape: '2:3' for portrait/full-body, '3:2' for landscape, '16:9' for desktop wallpaper, '9:16' for phone wallpaper, '1:1' for square. Small images are auto-upscaled; large images auto-downscaled. Use rescale_output to get exact original dimensions back.",
    "prompt_section": COMFYUI_TOOL_PROMPT_SECTION,
    "type": "object",
    "properties": {
        "prompt": {
            "type": "string",
            "description": "Text prompt describing what to generate or how to edit the image.",
        },
        "aspect_ratio": {
            "type": "string",
            "enum": ["1:1", "4:3", "3:4", "3:2", "2:3", "16:9", "9:16", "21:9", "9:21"],
            "description": "Preset aspect ratio at ~1MP. 1:1=1024x1024, 4:3=1152x896, 3:4=896x1152, 3:2=1216x832, 2:3=832x1216, 16:9=1344x768, 9:16=768x1344, 21:9=1536x640, 9:21=640x1536. Auto-detects from prompt if omitted.",
        },
        "width": {
            "type": "integer",
            "description": "Explicit output width in pixels (snapped to 32px). Overrides aspect_ratio. Use only for non-preset sizes.",
        },
        "height": {
            "type": "integer",
            "description": "Explicit output height in pixels (snapped to 32px). Overrides aspect_ratio. Use only for non-preset sizes.",
        },
        "input_image": {
            "type": "string",
            "description": "Path to input image for img2img, editing, or upscaling.",
        },
        "workflow": {
            "type": "string",
            "enum": ["text2img", "img2img", "edit", "upscale", "outpaint"],
            "description": "Force a specific workflow. Auto-selected if omitted. Use 'outpaint' to extend an image beyond its borders (requires input_image).",
        },
        "steps": {
            "type": "integer",
            "description": "Number of sampling steps (default 20-24).",
        },
        "guidance": {
            "type": "number",
            "description": "Guidance scale (default 2.5 for edit, 3.5 for others). Lower = more faithful to input.",
        },
        "denoise": {
            "type": "number",
            "description": "Denoise strength for img2img (default 0.65). 1.0 = full regeneration.",
        },
        "seed": {
            "type": "integer",
            "description": "RNG seed for reproducibility.",
        },
        "transparent": {
            "type": "boolean",
            "description": "Remove background for transparent PNG output. Uses RMBG-2.0 AI. Great for avatars, stickers, character art, overlay images.",
        },
        "pad_left_px": {
            "type": "integer",
            "description": "Outpaint padding in pixels on the left side (snapped to 32px). Takes precedence over pad_left_ratio.",
        },
        "pad_top_px": {
            "type": "integer",
            "description": "Outpaint padding in pixels on the top side (snapped to 32px). Takes precedence over pad_top_ratio.",
        },
        "pad_right_px": {
            "type": "integer",
            "description": "Outpaint padding in pixels on the right side (snapped to 32px). Takes precedence over pad_right_ratio.",
        },
        "pad_bottom_px": {
            "type": "integer",
            "description": "Outpaint padding in pixels on the bottom side (snapped to 32px). Takes precedence over pad_bottom_ratio.",
        },
        "pad_left_ratio": {
            "type": "number",
            "description": "Outpaint padding on the left as a ratio of image width (0.0-1.0, e.g. 0.1 = 10%).",
        },
        "pad_top_ratio": {
            "type": "number",
            "description": "Outpaint padding on the top as a ratio of image height (0.0-1.0, e.g. 0.1 = 10%).",
        },
        "pad_right_ratio": {
            "type": "number",
            "description": "Outpaint padding on the right as a ratio of image width (0.0-1.0, e.g. 0.1 = 10%).",
        },
        "pad_bottom_ratio": {
            "type": "number",
            "description": "Outpaint padding on the bottom as a ratio of image height (0.0-1.0, e.g. 0.1 = 10%).",
        },
        "force_no_rescale": {
            "type": "boolean",
            "description": "Bypass automatic up/downscaling constraints. Use only when you explicitly need oversized or tiny output.",
        },
        "rescale_output": {
            "type": "boolean",
            "description": "After generation, resize output back to the original input dimensions. Useful for editing large images or generating small icons.",
        },
        "ai_upscale": {
            "type": "boolean",
            "description": "When rescale_output needs to enlarge the output, use AI upscaling (4x-UltraSharp) instead of Pillow. Better quality, slower.",
        },
        "save_to": {
            "type": "string",
            "description": "Save output to this file path.",
        },
    },
    "required": ["prompt"],
}


def register(host):
    import odysseus

    odysseus.log("info", "Lily ComfyUI plugin loaded")

    host.add_router(router)

    host.add_tool(
        "comfyui_generate",
        schema=COMFYUI_TOOL_SCHEMA,
        fn=_do_comfyui_generate,
    )
