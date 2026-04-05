"""
AI 智能改图路由
==============
提供图片分析和编辑接口。

接口列表：
- POST /api/fix-image/edit          AI 编辑图片（混合方案：Claude Vision + Pillow + 通义万相）
- POST /api/fix-image/analyze       分析图片，返回图层 JSON
- POST /api/fix-image/analyze-mock  Mock 模式，返回测试数据（开发用）
"""

import base64
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from typing import Optional

from app.config import settings
from app.models.employee import ApiResponse
from app.services.fix_image import analyze_image, get_mock_analysis
from app.services.image_edit import edit_image

router = APIRouter(prefix="/api/fix-image", tags=["AI 智能改图"])


class AnalyzeBase64Request(BaseModel):
    """Base64 图片分析请求"""
    image: str = Field(..., description="图片 base64 编码（可包含 data:image/xxx;base64, 前缀）")


class EditImageRequest(BaseModel):
    """图片编辑请求"""
    image: str = Field(..., description="图片 base64 编码（可包含 data:image/xxx;base64, 前缀）")
    prompt: str = Field(..., description="用户的修改描述", min_length=1)
    logo_image: Optional[str] = Field(default=None, description="Logo 图片 base64（可选，用于叠加 logo）")


@router.post("/edit", summary="AI 编辑图片")
async def edit_image_endpoint(req: EditImageRequest):
    """
    混合方案 AI 改图：
    1. Claude Vision 分析用户意图
    2. 文字替换 → Pillow 精确渲染（匹配字体/字号/颜色）
    3. 内容替换 → 通义万相 inpainting 局部重绘
    4. 返回修改后的高清图片
    """
    if not settings.DASHSCOPE_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="未配置 DASHSCOPE_API_KEY，请在 .env 文件中设置"
        )

    try:
        result = await edit_image(req.image, req.prompt, req.logo_image)
        return ApiResponse(
            code=0,
            message="图片编辑完成",
            data=result
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图片编辑失败: {str(e)}")


@router.post("/analyze", summary="分析图片（Claude Vision）")
async def analyze_image_endpoint(req: AnalyzeBase64Request):
    """
    调用 Claude 3.5 Sonnet Vision 分析图片，返回结构化图层数据。

    前端上传图片后，将图片转为 base64 发送到此接口。
    返回的图层数据可直接用于 Fabric.js 渲染。
    """
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="未配置 ANTHROPIC_API_KEY，请在 .env 文件中设置"
        )

    try:
        # 解析 base64，去掉可能的 data URL 前缀
        image_data = req.image
        media_type = "image/png"

        if image_data.startswith("data:"):
            # 格式: data:image/png;base64,xxxxx
            header, image_data = image_data.split(",", 1)
            media_type = header.split(":")[1].split(";")[0]

        result = await analyze_image(image_data, media_type)

        return ApiResponse(
            code=0,
            message="图片分析完成",
            data=result
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图片分析失败: {str(e)}")


@router.post("/analyze-mock", summary="分析图片（Mock 模式）")
async def analyze_image_mock_endpoint(req: AnalyzeBase64Request):
    """
    返回 Mock 图层数据，用于开发调试，不需要 API Key。

    Mock 数据包含：背景图片、主标题、副标题、内容图片、底部说明 5 个图层。
    """
    # 尝试从 base64 获取图片尺寸
    import io
    from PIL import Image

    try:
        image_data = req.image
        if image_data.startswith("data:"):
            _, image_data = image_data.split(",", 1)

        image_bytes = base64.b64decode(image_data)
        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size
    except Exception:
        width, height = 800, 600

    result = get_mock_analysis(width, height)

    return ApiResponse(
        code=0,
        message="Mock 分析完成",
        data=result
    )


@router.post("/analyze-upload", summary="上传文件分析图片")
async def analyze_upload_endpoint(
    file: UploadFile = File(..., description="上传的图片文件"),
    mock: bool = Form(default=False, description="是否使用 Mock 模式"),
):
    """
    通过文件上传方式分析图片（替代 base64 方式）。
    适用��大文件上传场景。
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="请上传图片文件")

    contents = await file.read()
    image_base64 = base64.b64encode(contents).decode("utf-8")
    media_type = file.content_type

    if mock:
        import io
        from PIL import Image
        try:
            img = Image.open(io.BytesIO(contents))
            width, height = img.size
        except Exception:
            width, height = 800, 600

        result = get_mock_analysis(width, height)
    else:
        if not settings.ANTHROPIC_API_KEY:
            raise HTTPException(
                status_code=500,
                detail="未配置 ANTHROPIC_API_KEY，请在 .env 文件中设置"
            )
        result = await analyze_image(image_base64, media_type)

    return ApiResponse(
        code=0,
        message="图片分析完成",
        data=result
    )
