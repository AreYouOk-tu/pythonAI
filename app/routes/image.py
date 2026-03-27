"""
文生图路由
==========
提供文生图相关的 HTTP 接口
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.services.image_gen import create_image, get_image_history

router = APIRouter(prefix="/api/ai/image", tags=["文生图"])


class ImageGenRequest(BaseModel):
    """文生图请求参数"""
    prompt: str = Field(..., description="图像描述（支持中文）", min_length=2)
    style: Optional[str] = Field(
        default=None,
        description="风格：写实 / 动漫 / 水彩 / 油画 / 素描 / 3D，不填则自动"
    )


class ImageGenResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Optional[dict] = None


@router.post(
    "/generate",
    response_model=ImageGenResponse,
    summary="文生图",
    description="输入中文描述，由 Claude 优化提示词后调用通义万相生成图片，并持久化到 OSS",
)
async def generate_image(
    request: ImageGenRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    文生图接口

    前端调用示例：
    ```javascript
    const res = await axios.post('/api/ai/image/generate', {
      prompt: '一只在雪地里奔跑的柴犬，背景是富士山',
      style: '写实',
    })
    console.log(res.data.data.image_url)
    ```
    """
    if not settings.DASHSCOPE_API_KEY or settings.DASHSCOPE_API_KEY == "your_dashscope_api_key_here":
        raise HTTPException(status_code=500, detail="未配置 DASHSCOPE_API_KEY，请在 .env 文件中设置")

    if not settings.OSS_BUCKET_NAME or settings.OSS_BUCKET_NAME == "your_bucket_name":
        raise HTTPException(status_code=500, detail="未配置 OSS 存储，请在 .env 文件中设置")

    try:
        record = await create_image(db, request.prompt, request.style)
        return ImageGenResponse(
            data={
                "id": record.id,
                "image_url": record.image_url,
                "optimized_prompt": record.optimized_prompt,
                "style": record.style,
            }
        )
    except TimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成失败：{str(e)}")


@router.get(
    "/history",
    response_model=ImageGenResponse,
    summary="文生图历史记录",
    description="查询最近生成的图片历史",
)
async def image_history(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    records = await get_image_history(db, limit)
    return ImageGenResponse(
        data={
            "total": len(records),
            "list": [
                {
                    "id": r.id,
                    "user_prompt": r.user_prompt,
                    "optimized_prompt": r.optimized_prompt,
                    "style": r.style,
                    "status": r.status,
                    "image_url": r.image_url,
                    "error_msg": r.error_msg,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in records
            ],
        }
    )
