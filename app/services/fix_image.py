"""
AI 智能改图 - 图片分析服务
=========================
调用 Claude Vision API 分析图片，识别并拆分为可编辑的图层。

核心流程：
1. 接收前端上传的图片（base64）
2. 调用 Claude 3.5 Sonnet Vision 分析图片结构
3. 返回结构化的图层 JSON（位置、大小、类型、内容等）
4. 前端用 Fabric.js 渲染为可编辑画布
"""

import json
from app.config import settings


# Claude Vision 分析图片的系统提示词
ANALYSIS_SYSTEM_PROMPT = """你是一个专业的图片分析 AI，擅长将设计图拆分为可编辑的独立图层。

你的任务是分析用户上传的图片，识别其中所有可视元素，并返回结构化的 JSON 数据。

## 识别规则

1. **文字元素** (type: "text")：标题、副标题、正文、按钮文字、标签等
2. **图片元素** (type: "image")：照片、头像、产品图、背景图等
3. **图标元素** (type: "icon")：图标、logo、小图形装饰等

## 输出要求

对每个元素，必须返回：
- `id`: 唯一标识符，格式 "layer-1", "layer-2"...
- `type`: "text" | "image" | "icon"
- `name`: 描述性中文名称（如"标题文字"、"用户头像"）
- `bbox`: 边界框 { x, y, width, height, angle }，单位为像素，相对于图片左上角
  - x: 左边距
  - y: 上边距
  - width: 宽度
  - height: 高度
  - angle: 旋转角度（通常为 0）

对文字元素额外返回：
- `content`: 文字内容
- `fontSize`: 估算的字号（px）
- `fontWeight`: 字重（400=常规, 700=粗体）
- `color`: 颜色值（hex 格式，如 "#333333"）
- `textAlign`: 对齐方式 "left" | "center" | "right"
- `fontFamily`: 估算的字体族（如 "sans-serif", "serif"）

对图片/图标元素额外返回：
- `description`: 对该图片/图标内容的描述

## 注意事项
- 坐标必须尽可能精确
- 从后往前排列（背景层在前，前景层在后）
- 不要遗漏任何可见元素
- 仅返回 JSON，不要返回其他文字"""


ANALYSIS_USER_PROMPT = """请分析这张图片中的所有可视元素，返回结构化的图层 JSON。

严格按照以下 JSON 格式返回（不要包含 markdown 代码块标记）：
{
  "canvasWidth": <图片宽度>,
  "canvasHeight": <图片高度>,
  "layers": [
    {
      "id": "layer-1",
      "type": "text",
      "name": "元素名称",
      "bbox": { "x": 0, "y": 0, "width": 100, "height": 50, "angle": 0 },
      "content": "文字内容",
      "fontSize": 24,
      "fontWeight": 400,
      "color": "#333333",
      "textAlign": "left",
      "fontFamily": "sans-serif"
    }
  ]
}"""


async def analyze_image(image_base64: str, media_type: str = "image/png") -> dict:
    """
    调用 Claude Vision API 分析图片并返回图层数据。

    Args:
        image_base64: 图片的 base64 编码（不含 data:image/xxx;base64, 前缀）
        media_type: 图片 MIME 类型，如 "image/png", "image/jpeg"

    Returns:
        dict: { canvasWidth, canvasHeight, layers: [...] }
    """
    import anthropic
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    message = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=4096,
        system=ANALYSIS_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_base64,
                        },
                    },
                    {
                        "type": "text",
                        "text": ANALYSIS_USER_PROMPT,
                    },
                ],
            }
        ],
    )

    # 解析 Claude 返回的 JSON
    response_text = message.content[0].text.strip()

    # 清理可能的 markdown 代码块包裹
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        # 去掉第一行 ```json 和最后一行 ```
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        response_text = "\n".join(lines)

    result = json.loads(response_text)
    return result


def get_mock_analysis(width: int = 800, height: int = 600) -> dict:
    """
    返回 Mock 图层数据，用于开发调试（无需 API Key）。
    模拟 AI 识别出图片中的具体可编辑元素（文字、图片区域等）。
    """
    return {
        "canvasWidth": width,
        "canvasHeight": height,
        "layers": [
            {
                "id": "layer-1",
                "type": "image",
                "name": "顶部图片",
                "bbox": {"x": round(width * 0.15), "y": round(height * 0.05), "width": round(width * 0.7), "height": round(height * 0.3), "angle": 0},
                "description": "顶部区域图片",
            },
            {
                "id": "layer-2",
                "type": "text",
                "name": "主标题",
                "bbox": {"x": round(width * 0.1), "y": round(height * 0.4), "width": round(width * 0.8), "height": 50, "angle": 0},
                "content": "这是主标题文字",
                "fontSize": 36,
                "fontWeight": 700,
                "color": "#222222",
                "textAlign": "center",
                "fontFamily": "sans-serif",
            },
            {
                "id": "layer-3",
                "type": "text",
                "name": "描述文字",
                "bbox": {"x": round(width * 0.1), "y": round(height * 0.52), "width": round(width * 0.8), "height": 60, "angle": 0},
                "content": "这里是描述文字内容，你可以双击编辑修改它",
                "fontSize": 18,
                "fontWeight": 400,
                "color": "#555555",
                "textAlign": "left",
                "fontFamily": "sans-serif",
            },
            {
                "id": "layer-4",
                "type": "image",
                "name": "左侧小图",
                "bbox": {"x": round(width * 0.05), "y": round(height * 0.7), "width": round(width * 0.25), "height": round(height * 0.2), "angle": 0},
                "description": "左下角图片区域",
            },
            {
                "id": "layer-5",
                "type": "text",
                "name": "底部文字",
                "bbox": {"x": round(width * 0.35), "y": round(height * 0.75), "width": round(width * 0.6), "height": 36, "angle": 0},
                "content": "底部说明 - 可移动可编辑",
                "fontSize": 16,
                "fontWeight": 400,
                "color": "#888888",
                "textAlign": "left",
                "fontFamily": "sans-serif",
            },
        ],
    }
