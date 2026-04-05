"""
AI 大模型调用路由
================
这个文件演示如何通过 API 接口调用 Claude 大模型
前端可以直接调用这些接口，无需在前端暴露 API Key
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from app.config import settings
from app.models.employee import ApiResponse

# 创建路由器
router = APIRouter(prefix="/api/ai", tags=["AI 大模型"])


# ---- 请求体数据模型 ----
# POST 请求的请求体（body）需要用 Pydantic 模型定义
# 相当于前端 axios.post('/api/ai/chat', { message: '你好', ... })

class ChatRequest(BaseModel):
    """聊天请求参数"""

    # 用户发送的消息
    message: str = Field(..., description="用户消息", min_length=1)

    # 可选的系统提示词（告诉 AI 扮演什么角色）
    system_prompt: Optional[str] = Field(
        default=None,
        description="系统提示词，用于设定 AI 的角色和行为"
    )

    # 最大返回 token 数（可覆盖全局配置）
    max_tokens: Optional[int] = Field(
        default=None,
        description="最大返回 token 数，不填则使用全局配置"
    )


class ChatResponse(BaseModel):
    """聊天响应格式"""
    code: int = 0
    message: str = "success"
    data: Optional[dict] = None


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="发送消息给 Claude 大模型",
    description="向 Claude 发送一条消息，返回 AI 的回复",
)
async def chat_with_claude(request: ChatRequest):
    """
    调用 Claude 大模型进行对话

    前端调用示例：
    ```javascript
    const response = await axios.post('/api/ai/chat', {
      message: '请帮我分析这个季度的员工离职趋势',
      system_prompt: '你是一个专业的 HR 数据分析师',
    })
    console.log(response.data.data.reply)
    ```
    """

    # 检查是否配置了 API Key
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="未配置 ANTHROPIC_API_KEY，请在 .env 文件中设置"
        )

    try:
        # 导入 Anthropic SDK
        import anthropic

        # 创建客户端（使用配置中的 API Key）
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        # 构建消息列表
        # Claude API 使用 messages 数组，每条消息有 role（角色）和 content（内容）
        # role 只能是 "user" 或 "assistant"
        messages = [
            {"role": "user", "content": request.message}
        ]

        # 调用 Claude API
        # 这是同步调用，等待 AI 生成完整回复后再返回
        response = client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=request.max_tokens or settings.MAX_TOKENS,
            # system 是系统提示词，告诉 AI 它的角色
            system=request.system_prompt or "你是一个专业的企业人力资源助手，请用中文回复。",
            messages=messages,
        )

        # 提取 AI 的回复文本
        # response.content 是一个列表，每个元素可能是文本或工具调用
        # 这里只取第一个文本内容
        reply_text = response.content[0].text

        return ChatResponse(
            code=0,
            message="success",
            data={
                "reply": reply_text,
                # 返回 token 使用量，方便监控 API 消耗
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                }
            }
        )

    except anthropic.AuthenticationError:
        # API Key 无效
        raise HTTPException(status_code=401, detail="API Key 无效，请检查 .env 文件中的 ANTHROPIC_API_KEY")

    except anthropic.RateLimitError:
        # 请求频率超限
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")

    except Exception as e:
        # 其他未知错误
        raise HTTPException(status_code=500, detail=f"调用大模型失败：{str(e)}")


@router.post(
    "/analyze-employee-data",
    response_model=ChatResponse,
    summary="AI 分析员工数据",
    description="将员工数据传给 AI，让其进行智能分析并给出建议",
)
async def analyze_employee_data(
    data: dict = None
):
    """
    让 AI 分析员工相关数据

    这是一个更具体的业务场景示例：
    将员工统计数据传给 AI，AI 返回分析报告

    前端调用示例：
    ```javascript
    const response = await axios.post('/api/ai/analyze-employee-data', {
      department: '技术部',
      total: 100,
      formal: 70,
      third_party: 20,
      intern: 10,
      turnover_rate: 0.15
    })
    ```
    """

    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="未配置 ANTHROPIC_API_KEY")

    if not data:
        raise HTTPException(status_code=400, detail="请传入需要分析的员工数据")

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        # 将前端传来的数据整理成自然语言描述，让 AI 更好地理解
        data_description = "\n".join([f"- {k}: {v}" for k, v in data.items()])
        prompt = f"""
请分析以下员工数据，并给出专业的 HR 建议：

{data_description}

请从以下几个维度进行分析：
1. 人员结构是否合理
2. 潜在的风险点
3. 改善建议

请用简洁清晰的中文回复。
"""

        response = client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=settings.MAX_TOKENS,
            system="你是一个专业的企业人力资源顾问，擅长数据分析和人才管理策略。",
            messages=[{"role": "user", "content": prompt}],
        )

        return ChatResponse(
            code=0,
            message="success",
            data={
                "analysis": response.content[0].text,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                }
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 分析失败：{str(e)}")


@router.get(
    "/status",
    summary="检查 AI 服务状态",
    description="检查 API Key 是否配置，AI 服务是否可用",
)
async def check_ai_status():
    """
    检查 AI 服务配置状态

    前端可以在页面加载时调用这个接口，
    判断是否显示 AI 功能入口
    """
    has_key = bool(settings.ANTHROPIC_API_KEY)

    return ApiResponse(
        code=0,
        message="success",
        data={
            "configured": has_key,
            "model": settings.CLAUDE_MODEL if has_key else None,
            "tip": "AI 服务可用" if has_key else "请在 .env 文件中配置 ANTHROPIC_API_KEY"
        }
    )


@router.post(
    "/push-tech-news",
    summary="手动触发科技新闻推送",
    description="立即执行一次科技新闻生成并推送到企业微信，用于测试定时任务效果",
)
async def manual_push_tech_news():
    """
    手动触发科技新闻推送（测试用）

    正常情况下每天 10:30 自动执行，这个接口方便你随时测试：
    - 验证企业微信 Webhook 是否配置正确
    - 查看 Claude 生成的新闻内容效果

    调用示例：
    ```
    POST /api/ai/push-tech-news
    ```
    """
    from app.scheduler import push_tech_news

    # 直接调用定时任务函数（和定时执行的逻辑完全一样）
    await push_tech_news()

    return ApiResponse(
        code=0,
        message="success",
        data={"tip": "已触发推送，请查看企业微信群消息"}
    )

@router.get('/records')
async def getRecords():
    return {"message":"你好"}