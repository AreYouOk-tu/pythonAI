"""
文生图服务层
============
负责：
1. 调用 Claude 优化用户提示词（中文 → 高质量英文提示词）
2. 调用通义万相 API 生成图片
3. 将图片上传到阿里云 OSS 持久化存储
4. 操作数据库保存生成历史
"""

import uuid
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.config import settings
from app.models.db_models import ImageRecord


# ==============================
# 第一步：Claude 优化提示词
# ==============================
async def optimize_prompt(user_prompt: str, style: str | None) -> str:
    """
    用 Claude 将用户的中文描述优化成高质量的英文图像提示词
    通义万相对英文提示词效果更好，Claude 负责翻译和润色
    """
    import anthropic

    style_hint = f"，风格要求：{style}" if style else ""
    system = (
        "你是一个专业的 AI 绘画提示词工程师。"
        "用户会给你一段中文图像描述，你需要将其转化为适合文生图模型使用的高质量英文提示词。"
        "核心要求：\n"
        "1. 用户描述中出现的物体、动作、人物特征必须全部保留，不能遗漏\n"
        "2. 对关键动作（如「拿着书」「holding a book」）需要放在靠前位置并加强描述\n"
        "3. 补充画面质量词：8K, ultra detailed, masterpiece, sharp focus\n"
        "4. 包含构图/光线/风格等视觉要素\n"
        "5. 只输出英文提示词，不要解释，不要多余文字"
    )
    prompt = f"请将以下描述转化为高质量英文图像提示词{style_hint}：\n{user_prompt}"

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=300,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


# ==============================
# 第二步：调用通义万相生成图片
# ==============================
async def generate_image_with_wanx(prompt: str, style: str | None) -> str:
    """
    调用通义万相 wanx2.1-t2i-plus 模型生成图片，返回图片的临时 URL
    wanx2.1-t2i-plus 比 wanx-v1 画质更高、细节还原更准确
    """

    headers = {
        "Authorization": f"Bearer {settings.DASHSCOPE_API_KEY}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable",
    }

    body = {
        "model": "wanx2.1-t2i-plus",
        "input": {"prompt": prompt},
        "parameters": {
            "size": "1024*1024",
            "n": 1,
        },
    }

    async with httpx.AsyncClient(timeout=30) as client:
        # 提交生成任务
        resp = await client.post(
            "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis",
            headers=headers,
            json=body,
        )
        resp.raise_for_status()
        task_id = resp.json()["output"]["task_id"]

        # 轮询任务状态（最多等 120 秒）
        for _ in range(24):
            import asyncio
            await asyncio.sleep(5)

            poll_resp = await client.get(
                f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}",
                headers={"Authorization": f"Bearer {settings.DASHSCOPE_API_KEY}"},
            )
            poll_resp.raise_for_status()
            result = poll_resp.json()

            task_status = result["output"]["task_status"]
            if task_status == "SUCCEEDED":
                return result["output"]["results"][0]["url"]
            elif task_status == "FAILED":
                raise RuntimeError(f"通义万相生成失败：{result['output'].get('message', '未知错误')}")
            # PENDING / RUNNING 继续等待

    raise TimeoutError("通义万相生成超时，请稍后重试")


# ==============================
# 第三步：上传图片到阿里云 OSS
# ==============================
async def upload_to_oss(image_url: str, record_id: int) -> str:
    """
    将通义万相返回的临时图片 URL 下载后上传到 OSS，返回永久访问地址

    为什么要这一步：通义万相返回的图片 URL 有时效性（通常 24 小时），
    上传到 OSS 后才能永久保存。
    """
    import oss2

    # 初始化 OSS 客户端
    auth = oss2.Auth(settings.OSS_ACCESS_KEY_ID, settings.OSS_ACCESS_KEY_SECRET)
    bucket = oss2.Bucket(auth, settings.OSS_ENDPOINT, settings.OSS_BUCKET_NAME)

    # 下载图片内容
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(image_url)
        resp.raise_for_status()
        image_bytes = resp.content

    # 生成唯一文件名，避免冲突
    file_key = f"{settings.OSS_IMAGE_PREFIX}{record_id}-{uuid.uuid4().hex}.png"

    # 上传到 OSS（oss2 是同步库，在线程池里运行）
    import asyncio
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: bucket.put_object(file_key, image_bytes)
    )

    return f"{settings.OSS_PUBLIC_URL_BASE}{file_key}"


# ==============================
# 主入口：完整生成流程
# ==============================
async def create_image(
    db: AsyncSession,
    user_prompt: str,
    style: str | None = None,
) -> ImageRecord:
    """
    文生图完整流程：
    1. 创建数据库记录（pending 状态）
    2. Claude 优化提示词
    3. 通义万相生成图片
    4. 上传到 OSS
    5. 更新数据库记录为 success
    """

    # 1. 先创建一条 pending 记录，确保任何情况都有日志可查
    record = ImageRecord(
        user_prompt=user_prompt,
        style=style,
        status="pending",
    )
    db.add(record)
    await db.flush()   # flush 让数据库分配 ID，但还没 commit

    try:
        # 2. Claude 优化提示词
        optimized = await optimize_prompt(user_prompt, style)
        record.optimized_prompt = optimized

        # 3. 通义万相生成图片（返回临时 URL）
        temp_url = await generate_image_with_wanx(optimized, style)

        # 4. 上传到 OSS，获取永久地址
        oss_url = await upload_to_oss(temp_url, record.id)

        # 5. 更新记录为成功
        record.image_url = oss_url
        record.status = "success"

    except Exception as e:
        record.status = "failed"
        record.error_msg = str(e)
        raise

    return record


# ==============================
# 查询历史记录
# ==============================
async def get_image_history(db: AsyncSession, limit: int = 20) -> list[ImageRecord]:
    """查询最近的文生图历史记录，按创建时间倒序"""
    stmt = (
        select(ImageRecord)
        .order_by(desc(ImageRecord.created_at))
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
