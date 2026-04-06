"""
文生图路由（简化版）
==================
不依赖数据库和 OSS，直接返回通义万相生成的图片 URL。
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from app.config import settings
from app.services.image_gen import generate_image_with_wanx

router = APIRouter(prefix="/api/ai/image", tags=["文生图"])


class ImageGenRequest(BaseModel):
    prompt: str = Field(..., description="图像描述（支持中文）", min_length=2)
    style: Optional[str] = Field(default=None, description="风格：写实/动漫/水彩/油画/素描/3D")


@router.post("/generate", summary="文生图")
async def generate_image(req: ImageGenRequest):
    if not settings.DASHSCOPE_API_KEY:
        raise HTTPException(status_code=500, detail="未配置 DASHSCOPE_API_KEY")

    try:
        # 通义万相生成图片
        image_url = await generate_image_with_wanx(req.prompt, req.style)

        return {
            "code": 0,
            "message": "success",
            "data": {
                "image_url": image_url,
                "style": req.style,
            },
        }
    except TimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成失败：{str(e)}")
