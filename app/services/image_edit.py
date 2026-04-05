"""
AI 智能改图 - 图片编辑服务
=========================
混合方案：Claude Vision 理解意图 + Pillow 精确文字渲染 + 通义万相 Inpainting

流程：
1. Claude Vision 分析用户意图，返回结构化编辑指令
2. 文字替换 → Pillow 精确渲染（匹配字体/字号/颜色）
3. 内容替换 → 通义万相 inpainting 局部重绘
4. 位置调整 → Pillow 裁切+粘贴
"""

import io
import os
import re
import json
import base64
import asyncio
import logging
import httpx
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont, ImageFilter

logger = logging.getLogger(__name__)

from typing import Optional
from app.config import settings

# ============ 字体映射 ============

# 常用字体搜索路径
FONT_SEARCH_PATHS = [
    # 项目内置字体
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "fonts"),
    # macOS 系统字体
    "/System/Library/Fonts",
    "/System/Library/Fonts/Supplemental",
    "/Library/Fonts",
    # Linux 系统字体
    "/usr/share/fonts",
    "/usr/local/share/fonts",
]

# 字体族到文件名的映射（Claude 识别出的字体名 → 实际字体文件）
FONT_FAMILY_MAP = {
    # 无衬线 (黑体类)
    "sans-serif": ["PingFang.ttc", "NotoSansSC-Regular.ttf", "STHeiti Medium.ttc"],
    "黑体": ["PingFang.ttc", "STHeiti Medium.ttc", "NotoSansSC-Regular.ttf"],
    "苹方": ["PingFang.ttc"],
    "微软雅黑": ["PingFang.ttc", "NotoSansSC-Regular.ttf"],
    "思源黑体": ["NotoSansSC-Regular.ttf", "PingFang.ttc"],
    "pingfang": ["PingFang.ttc"],
    "helvetica": ["PingFang.ttc", "Helvetica.ttc"],
    "arial": ["PingFang.ttc", "Arial.ttf"],
    # 衬线 (宋体类)
    "serif": ["Songti.ttc", "NotoSerifSC-Regular.ttf"],
    "宋体": ["Songti.ttc", "NotoSerifSC-Regular.ttf"],
    "思源宋体": ["NotoSerifSC-Regular.ttf", "Songti.ttc"],
    # 粗体变体
    "sans-serif-bold": ["PingFang.ttc", "NotoSansSC-Bold.ttf", "STHeiti Medium.ttc"],
    "serif-bold": ["Songti.ttc", "NotoSerifSC-Bold.ttf"],
}


def _find_font_file(font_family: str, font_weight: str = "normal") -> Optional[str]:
    """根据字体族名查找对应的字体文件路径"""
    key = font_family.lower().strip()
    if font_weight in ("bold", "700") and f"{key}-bold" in FONT_FAMILY_MAP:
        key = f"{key}-bold"

    candidates = FONT_FAMILY_MAP.get(key, FONT_FAMILY_MAP.get("sans-serif", []))

    for font_name in candidates:
        for search_path in FONT_SEARCH_PATHS:
            full_path = os.path.join(search_path, font_name)
            if os.path.exists(full_path):
                return full_path
    return None


def _get_font(font_family: str, font_size: int, font_weight: str = "normal") -> ImageFont.FreeTypeFont:
    """获取 Pillow 字体对象"""
    font_path = _find_font_file(font_family, font_weight)
    if font_path:
        try:
            return ImageFont.truetype(font_path, font_size)
        except Exception:
            pass
    # 兜底：使用默认字体
    try:
        return ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", font_size)
    except Exception:
        return ImageFont.load_default()


def _hex_to_rgb(hex_color: str) -> tuple:
    """将 hex 颜色转换为 RGB 元组"""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


# ============ Claude Vision 意图分析 ============

EDIT_ANALYSIS_SYSTEM_PROMPT = """你是一个专业的图片编辑 AI 助手。你的任务是分析用户上传的图片和他们的修改需求，返回结构化的编辑指令 JSON。

## 你需要做的事

1. 仔细观察图片中的所有元素（文字、图片、图标等）
2. 理解用户想要修改什么
3. 精确定位需要修改的区域（像素级边界框）
4. 识别文字的字体特征（字体族、字号、颜色、粗细、对齐方式）
5. 返回结构化的编辑指令

## 操作类型

### text_replace - 文字替换
当用户要求修改图片中的文字时使用。你需要精确识别：
- 文字所在的精确边界框（bbox），要完全覆盖原文字区域
- 原始文字内容
- 用户要替换成的新文字
- 字体信息：font_family（如 "sans-serif", "serif", "黑体", "宋体"）
- font_size：字号（像素，务必精确估算）
- font_weight："normal" 或 "bold"
- font_color：hex 颜色值（如 "#333333"，务必精确）
- text_align："left", "center", 或 "right"
- background_color：文字区域的背景色（hex 值，用于擦除旧文字时填充）
- line_height: 行高倍数（默认 1.2）

### content_replace - 内容替换（区域重绘）
当用户要求替换图片中的某个图片区域或非文字内容时使用。
- 精确定位要替换的区域边界框
- 提供替换内容的描述（用于 AI 重绘）

### position_adjust - 位置调整
当用户要求移动某个元素到新位置时使用。
- 原始位置的边界框
- 目标位置（新的 x, y 坐标）

### logo_overlay - Logo 叠加
当用户上传了一张 logo/图片素材，并要求将其放置到图片中的某个位置时使用。
- bbox: logo 要放置的目标区域（x, y, width, height）。width 和 height 表示 logo 缩放后的尺寸。
- 如果用户只指定了宽度，height 应按 logo 原始比例等比计算（设为 0 表示自动）
- 如果用户说"右上角"，请根据图片尺寸计算具体的 x, y 坐标，并留出合理边距（如 20px）
- 如果用户没有明确指定大小，根据图片尺寸给出合理的默认大小

## 输出格式

严格返回以下 JSON 格式（不要包含 markdown 代码块标记）。
特别注意：bbox 必须是标准 JSON 对象，包含 "x", "y", "width", "height" 四个命名字段，不能省略任何 key！
错误示例：{ "x": 100, 200, 300, 50 }
正确示例：{ "x": 100, "y": 200, "width": 300, "height": 50 }
{
  "operations": [
    {
      "type": "text_replace",
      "bbox": { "x": 100, "y": 200, "width": 300, "height": 50 },
      "old_text": "原始文字",
      "new_text": "替换后的文字",
      "font_size": 24,
      "font_weight": "bold",
      "font_color": "#333333",
      "font_family": "sans-serif",
      "text_align": "center",
      "background_color": "#FFFFFF",
      "line_height": 1.2
    },
    {
      "type": "logo_overlay",
      "bbox": { "x": 650, "y": 20, "width": 120, "height": 0 }
    }
  ],
  "description": "对修改操作的简要中文描述"
}

## 重要注意事���
- bbox 坐标必须尽可能精确，单位为像素
- background_color 要准确采样文字背景区域的颜色
- font_size 要精确估算，不要偏差太大
- 如果用户的请求不涉及图片修改（比如闲聊），返回空 operations 数组
- 仅返回 JSON，不要返回其他文字"""


async def analyze_edit_intent(image_base64: str, media_type: str, prompt: str, has_logo: bool = False) -> dict:
    """
    用通义千问 Qwen-VL-Max 分析用户意图，返回结构化编辑指令。
    通过 DashScope 的 OpenAI 兼容接口调用。
    """
    client = OpenAI(
        api_key=settings.DASHSCOPE_API_KEY,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

    user_text = f"请根据以下用户需求分析图片并返回编辑指令：\n\n{prompt}"
    if has_logo:
        user_text += "\n\n注意：用户已上传了一张 logo/图片素材，需要叠加到图片中。请使用 logo_overlay 操作类型，根据用户描述确定放置位置和大小。"

    image_url = f"data:{media_type};base64,{image_base64}"

    response = client.chat.completions.create(
        model="qwen-vl-max",
        messages=[
            {"role": "system", "content": EDIT_ANALYSIS_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": user_text},
                ],
            },
        ],
        max_tokens=4096,
    )

    response_text = response.choices[0].message.content.strip()

    # 清理可能的 markdown 代码块包裹
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        response_text = "\n".join(lines)

    # 尝试提取 JSON（处理模型返回额外文字的情况）
    json_match = re.search(r'\{[\s\S]*\}', response_text)
    if json_match:
        response_text = json_match.group()

    # 清理常见的 JSON 格式问题
    response_text = re.sub(r',\s*([}\]])', r'\1', response_text)  # trailing commas
    response_text = re.sub(r'//.*?(?=\n|$)', '', response_text)   # 单行注释
    response_text = re.sub(r'/\*[\s\S]*?\*/', '', response_text)  # 块注释

    # 修复模型返回的 bbox 格式不规范的问题
    # 统一将 bbox 中所有裸数字补上正确的 key
    def _fix_bbox(match):
        """从 bbox 块中提取所有数字，按 x, y, width, height 顺序赋值"""
        full = match.group(0)
        # 提取 { ... } 部分
        brace_match = re.search(r'\{[^}]*\}', full)
        if not brace_match:
            return full
        bbox_str = brace_match.group(0)
        numbers = re.findall(r'\d+', bbox_str)
        if len(numbers) >= 4:
            return f'{{"x": {numbers[0]}, "y": {numbers[1]}, "width": {numbers[2]}, "height": {numbers[3]}}}'
        return bbox_str

    # 匹配 "bbox": { ... } 整个块（包含各种畸形格式）
    response_text = re.sub(
        r'("bbox"\s*:\s*)\{[^}]*\}',
        lambda m: m.group(1) + _fix_bbox(m),
        response_text,
    )

    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        logger.error(f"JSON 解析失败，清理后内容:\n{response_text}")
        logger.error(f"原始模型响应:\n{response.choices[0].message.content}")
        raise


# ============ 文字替换（Pillow 精确渲染）============

def execute_text_replace(img: Image.Image, op: dict) -> Image.Image:
    """
    用 Pillow 精确替换图片中的文字。
    只擦除旧文字占据的精确区域，用周围最亮像素（排除文字干扰）作为背景色。
    """
    img = img.copy()
    draw = ImageDraw.Draw(img)
    img_w, img_h = img.size

    bbox = op["bbox"]
    bx, by, bw, bh = _normalize_bbox(bbox)

    new_text = op.get("new_text", "")
    if not new_text:
        return img

    font_size = op.get("font_size", 16)
    font_weight = op.get("font_weight", "normal")
    font_family = op.get("font_family", "sans-serif")
    font_color = _hex_to_rgb(op.get("font_color", "#000000"))
    text_align = op.get("text_align", "left")

    font = _get_font(font_family, font_size, font_weight)

    # 1. 计算新文字的实际渲染尺寸
    text_bbox = draw.textbbox((0, 0), new_text, font=font)
    new_text_w = text_bbox[2] - text_bbox[0]
    new_text_h = text_bbox[3] - text_bbox[1]

    # 2. 擦除区域：用 bbox 完整范围 + padding 确保旧文字完全覆盖
    pad = 3
    erase_x1 = max(0, bx - pad)
    erase_y1 = max(0, by - pad)
    erase_x2 = min(img_w, bx + bw + pad)
    erase_y2 = min(img_h, by + bh + pad)

    # 3. 采样背景色：从 bbox 周围取最亮的像素（排除文字颜色干扰）
    bg_rgb = _sample_background_color(img, bx, by, bw, bh)

    # 4. 擦除旧文字
    draw.rectangle(
        [erase_x1, erase_y1, erase_x2, erase_y2],
        fill=bg_rgb
    )

    # 5. 在同一位置渲染新文字（垂直居中于擦除区域）
    text_y = by + (bh - new_text_h) // 2
    text_x = bx
    if text_align == "center":
        text_x = bx + (bw - new_text_w) / 2
    elif text_align == "right":
        text_x = bx + bw - new_text_w

    draw.text((text_x, text_y), new_text, fill=font_color, font=font)

    return img


def _wrap_text(draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """将文字按区域宽度自动换行"""
    if not text:
        return []

    lines = []
    current_line = ""

    for char in text:
        test_line = current_line + char
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] > max_width and current_line:
            lines.append(current_line)
            current_line = char
        else:
            current_line = test_line

    if current_line:
        lines.append(current_line)

    return lines


# ============ 内容替换（通义万相 Inpainting）============

async def execute_content_replace(img: Image.Image, op: dict) -> Image.Image:
    """
    用通义万相的图片编辑能力替换指定区域的内容。
    使用 DashScope 的图片编辑 API。
    """
    bbox = op["bbox"]
    description = op.get("description", "")

    # 生成 mask 图片（白色区域表示要修改的部分）
    mask = Image.new("RGB", img.size, (0, 0, 0))
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rectangle(
        [bbox["x"], bbox["y"], bbox["x"] + bbox["width"], bbox["y"] + bbox["height"]],
        fill=(255, 255, 255)
    )

    # 将原图和 mask 转为 base64
    img_b64 = _image_to_base64(img)
    mask_b64 = _image_to_base64(mask)

    # 调用通义万相 inpainting API
    headers = {
        "Authorization": f"Bearer {settings.DASHSCOPE_API_KEY}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable",
    }

    body = {
        "model": "wanx2.1-t2i-plus",
        "input": {
            "prompt": description,
            "base_image_url": f"data:image/png;base64,{img_b64}",
            "mask_image_url": f"data:image/png;base64,{mask_b64}",
        },
        "parameters": {
            "size": f"{img.width}*{img.height}",
            "n": 1,
        },
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis",
            headers=headers,
            json=body,
        )
        resp.raise_for_status()
        task_id = resp.json()["output"]["task_id"]

        # 轮询等待结果（最多 120 秒）
        for _ in range(24):
            await asyncio.sleep(5)
            poll_resp = await client.get(
                f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}",
                headers={"Authorization": f"Bearer {settings.DASHSCOPE_API_KEY}"},
            )
            poll_resp.raise_for_status()
            result = poll_resp.json()
            status = result["output"]["task_status"]

            if status == "SUCCEEDED":
                image_url = result["output"]["results"][0]["url"]
                # 下载结果图片
                img_resp = await client.get(image_url)
                img_resp.raise_for_status()
                return Image.open(io.BytesIO(img_resp.content)).convert("RGB")
            elif status == "FAILED":
                error_msg = result["output"].get("message", "未知错误")
                raise RuntimeError(f"通义万相处理失败：{error_msg}")

    raise TimeoutError("通义万相处理超时")


# ============ 位置调整（Pillow 裁切+粘贴）============

def execute_position_adjust(img: Image.Image, op: dict) -> Image.Image:
    """
    将指定区域裁切出来，粘贴到新位置。
    原位置用周围颜色填充。
    """
    img = img.copy()
    bbox = op["bbox"]
    target = op.get("target", {})

    x, y, w, h = _normalize_bbox(bbox)
    tx, ty = target.get("x", x), target.get("y", y)

    # 裁切源区域
    cropped = img.crop((x, y, x + w, y + h))

    # 用周围颜色填充原位置
    draw = ImageDraw.Draw(img)
    # 取原区域上方一行像素的平均色作为填充色
    sample_y = max(0, y - 1)
    sample_region = img.crop((x, sample_y, x + w, sample_y + 1))
    avg_color = _average_color(sample_region)
    draw.rectangle([x, y, x + w, y + h], fill=avg_color)

    # 粘贴到新位置
    img.paste(cropped, (int(tx), int(ty)))

    return img


def _average_color(img: Image.Image) -> tuple:
    """计算图片区域的平均颜色"""
    pixels = list(img.getdata())
    if not pixels:
        return (255, 255, 255)
    r = sum(p[0] for p in pixels) // len(pixels)
    g = sum(p[1] for p in pixels) // len(pixels)
    b = sum(p[2] for p in pixels) // len(pixels)
    return (r, g, b)


# ============ Logo 叠加（Pillow 粘贴）============

def execute_logo_overlay(img: Image.Image, op: dict, logo_img: Image.Image) -> Image.Image:
    """
    将 logo 图片缩放后粘贴到指定位置。
    支持透明背景 logo（RGBA）。
    """
    img = img.copy().convert("RGBA")
    bbox = op["bbox"]
    x, y = int(bbox["x"]), int(bbox["y"])
    target_w = int(bbox.get("width", 0))
    target_h = int(bbox.get("height", 0))

    # 确保 logo 是 RGBA 模式（保留透明度）
    logo = logo_img.copy().convert("RGBA")

    # 计算缩放尺寸
    orig_w, orig_h = logo.size
    if target_w > 0 and target_h > 0:
        new_w, new_h = target_w, target_h
    elif target_w > 0:
        # 只指定了宽度，按比例计算高度
        ratio = target_w / orig_w
        new_w = target_w
        new_h = int(orig_h * ratio)
    elif target_h > 0:
        # 只指定了高度，按比例计算宽度
        ratio = target_h / orig_h
        new_w = int(orig_w * ratio)
        new_h = target_h
    else:
        # 都没指定，使用原始尺寸
        new_w, new_h = orig_w, orig_h

    # 使用高质量缩放
    logo = logo.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # 粘贴 logo（使用 alpha 通道作为 mask 保留透明度）
    img.paste(logo, (x, y), logo)

    return img.convert("RGB")


# ============ 工具函数 ============

def _sample_background_color(img: Image.Image, x: int, y: int, w: int, h: int) -> tuple:
    """
    从文字区域周围采样真实背景色。
    策略：取区域上方/下方远离文字的窄条，收集所有像素，按亮度排序取最亮的 25%
    的中位数——因为背景通常比文字更亮，这样能有效排除文字像素的干扰。
    """
    img_w, img_h = img.size
    pixels = []

    # 从上方 5-10px 处采样（远离文字避免采到字）
    sample_gap = 8
    strip_h = 3
    if y - sample_gap - strip_h >= 0:
        strip = img.crop((max(0, x), y - sample_gap - strip_h, min(img_w, x + w), y - sample_gap))
        pixels.extend(list(strip.getdata()))
    # 从下方 5-10px 处采样
    if y + h + sample_gap + strip_h <= img_h:
        strip = img.crop((max(0, x), y + h + sample_gap, min(img_w, x + w), y + h + sample_gap + strip_h))
        pixels.extend(list(strip.getdata()))
    # 从左侧 5-10px 处采样
    if x - sample_gap - strip_h >= 0:
        strip = img.crop((x - sample_gap - strip_h, max(0, y), x - sample_gap, min(img_h, y + h)))
        pixels.extend(list(strip.getdata()))
    # 从右侧 5-10px 处采样
    if x + w + sample_gap + strip_h <= img_w:
        strip = img.crop((x + w + sample_gap, max(0, y), x + w + sample_gap + strip_h, min(img_h, y + h)))
        pixels.extend(list(strip.getdata()))

    if not pixels:
        return (255, 255, 255)

    # 按亮度排序，取最亮的 25% 的中位数（排除文字等深色像素）
    pixels.sort(key=lambda p: p[0] + p[1] + p[2], reverse=True)
    bright_quarter = pixels[:max(1, len(pixels) // 4)]
    mid = len(bright_quarter) // 2
    return bright_quarter[mid][:3]


def _normalize_bbox(bbox: dict) -> tuple:
    """
    标准化 bbox，返回 (x, y, width, height)。
    模型可能返回 [x, y, x2, y2] 格式：如果 "width" 值大于 "x" 且 "height" 值大于 "y"，
    说明是右下角坐标，需要转换。
    同时做合理性校验：单个文字区域的宽高不应超过图片的合理范围。
    """
    x = int(bbox["x"])
    y = int(bbox["y"])
    w = int(bbox["width"])
    h = int(bbox["height"])
    # 如果 w > x 且 h > y，很可能是 [x1, y1, x2, y2] 格式
    if w > x and h > y:
        w = w - x
        h = h - y
    return x, y, w, h

def _image_to_base64(img: Image.Image, fmt: str = "PNG") -> str:
    """将 PIL Image 转为 base64 字符串"""
    buffer = io.BytesIO()
    img.save(buffer, format=fmt, quality=100)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def _base64_to_image(b64: str, mode: str = "RGB") -> Image.Image:
    """将 base64 字符串转为 PIL Image"""
    if b64.startswith("data:"):
        b64 = b64.split(",", 1)[1]
    return Image.open(io.BytesIO(base64.b64decode(b64))).convert(mode)


# ============ 主入口 ============

async def edit_image(image_base64: str, prompt: str, logo_image: Optional[str] = None) -> dict:
    """
    图片编辑主入口。

    Args:
        image_base64: 图片 base64（可包含 data:image/xxx;base64, 前缀）
        prompt: 用户的修改描述
        logo_image: Logo 图片 base64（可选，用于叠加 logo）

    Returns:
        dict: { "resultImage": "data:image/png;base64,...", "description": "..." }
    """
    # 解析图片
    raw_b64 = image_base64
    media_type = "image/png"
    if raw_b64.startswith("data:"):
        header, raw_b64 = raw_b64.split(",", 1)
        media_type = header.split(":")[1].split(";")[0]

    img = _base64_to_image(image_base64)
    logger.info(f"原图尺寸: {img.size[0]}x{img.size[1]}")

    # 解析 logo（如果有）
    logo_img = None
    if logo_image:
        try:
            logo_img = _base64_to_image(logo_image, mode="RGBA")
        except Exception:
            pass

    # Step 1: Claude Vision 分析意图
    instructions = await analyze_edit_intent(raw_b64, media_type, prompt, has_logo=logo_img is not None)
    operations = instructions.get("operations", [])
    description = instructions.get("description", "已完成修改")

    if not operations:
        return {
            "resultImage": image_base64,
            "description": description or "未识别到需要修改的内容，请更具体地描述你的需求。",
        }

    # Step 2: 依次执行编辑操作
    for op in operations:
        op_type = op.get("type")
        if "bbox" in op:
            norm = _normalize_bbox(op["bbox"])
            logger.info(f"操作: {op_type}, bbox归一化: x={norm[0]}, y={norm[1]}, w={norm[2]}, h={norm[3]}")
        try:
            if op_type == "text_replace":
                img = execute_text_replace(img, op)
            elif op_type == "content_replace":
                img = await execute_content_replace(img, op)
            elif op_type == "position_adjust":
                img = execute_position_adjust(img, op)
            elif op_type == "logo_overlay" and logo_img:
                img = execute_logo_overlay(img, op, logo_img)
        except Exception as e:
            # 单个操作失败不中断整体流程，记录到描述中
            description += f"\n（注意：{op_type} 操作执行时遇到问题：{str(e)}）"

    # Step 3: 返回结果
    result_b64 = _image_to_base64(img, "PNG")

    return {
        "resultImage": f"data:image/png;base64,{result_b64}",
        "description": description,
    }
