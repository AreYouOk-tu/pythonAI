"""
定时任务调度器
=============
使用 APScheduler 库实现定时任务
每天 10:30 自动执行：用 Claude 生成科技新闻摘要 → 推送到企业微信

APScheduler 相当于后端的 setInterval/setTimeout，但功能更强大：
  - 支持 cron 表达式（类似 Linux crontab）
  - 服务重启后任务不丢失（可配置持久化）
  - 支持异步任务
"""

import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.services.wecom import send_wecom_markdown


# ==============================
# 核心任务：生成并推送科技新闻
# ==============================
async def push_tech_news():
    """
    每天定时执行的任务：
    1. 调用 Claude API 生成6条生物医药新闻摘要
    2. 格式化成 Markdown
    3. 推送到企业微信群
    """
    print("[定时任务] 开始执行每日生物制药行业新闻推送...")

    # 检查 API Key
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key or api_key == "your_api_key_here":
        print("[定时任务] 未配置 ANTHROPIC_API_KEY，跳过执行")
        return

    try:
        import anthropic
        from datetime import datetime

        client = anthropic.Anthropic(api_key=api_key)

        # 获取今天的日期，让 Claude 知道当前时间背景
        today = datetime.now().strftime("%Y年%m月%d日")

        # 构建 Prompt，让 Claude 生成制药行业新闻摘要
        # 注意：Claude 的知识有截止日期，这里是让它基于已有知识生成热点总结
        prompt = f"""今天是 {today}，请为我生成 5 条最新的制药行业热点资讯摘要。

要求：
1. 涵盖新药研发、临床试验、政策法规、医药并购、生物技术等制药领域
2. 每条新闻包含：标题 + 2~3句话的简要说明
3. 语言简洁专业，适合在企业内部早报分享
4. 每条新闻标题前加一个贴合内容的 emoji（如 💊新药、🔬研发、📋政策、💰并购、🧪临床、🌍国际等）
5. 每条新闻末尾注明信息来源（如 FDA 官网、Nature、Reuters、Bloomberg、NMPA、公司官方公告等）
6. 按照以下格式输出（严格遵守，方便程序处理）：

【1】<font color="#003087">💊 标题内容</font>
简要说明内容（2~3句话）
<font color="#87CEEB">来源：XXX</font>

【2】<font color="#003087">🔬 标题内容</font>
简要说明内容（2~3句话）
<font color="#87CEEB">来源：XXX</font>

（以此类推，共5条）"""

        # 调用 Claude API
        response = client.messages.create(
            model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6"),
            max_tokens=2048,
            system="你是一名生物制药行业领域分析专家，专注跟踪全球最新生物医药动态，熟悉新药研发、临床试验、药监政策、生物制药公司最新最好用的工具等领域。请基于你的知识提供专业、准确的生物制药资讯摘要。",
            messages=[{"role": "user", "content": prompt}]
        )

        news_content = response.content[0].text

        # ---- 格式化成企业微信 Markdown ----
        # 企业微信 Markdown 有自己的语法规则
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        # 拼接最终要发送的消息
        # 企业微信支持的 Markdown：# 标题、**加粗**、> 引用等
        markdown_message = f"""# ⚡️ 生物制药早报 | {now}

> 📋 今日精选 **5 条**行业动态，助你掌握前沿资讯

{news_content}"""

        # ---- 推送到企业微信 ----
        success = await send_wecom_markdown(markdown_message)

        if success:
            print(f"[定时任务] 生物制药新闻推送完成，token 消耗: 输入{response.usage.input_tokens} 输出{response.usage.output_tokens}")
        else:
            print("[定时任务] 推送失败，请检查 WECOM_WEBHOOK_URL 配置")

    except Exception as e:
        print(f"[定时任务] 执行失败: {e}")


# ==============================
# 创建并配置调度器
# ==============================
def create_scheduler() -> AsyncIOScheduler:
    """
    创建定时任务调度器并注册所有定时任务

    返回配置好的 scheduler 实例，由 main.py 在启动时调用 start()

    CronTrigger 参数说明（和 Linux crontab 一样）：
        hour=10, minute=30 → 每天 10:30 执行
        day_of_week="mon-fri" → 只在周一到周五执行（如需每天执行去掉这行）
    """
    # AsyncIOScheduler → 异步版本的调度器，和 FastAPI 的异步框架兼容
    scheduler = AsyncIOScheduler(
        # 设置时区为上海（北京时间），确保定时准确
        timezone="Asia/Shanghai"
    )

    # 注册定时任务
    # add_job 相当于 crontab 里的一行配置
    scheduler.add_job(
        func=push_tech_news,        # 要执行的函数
        trigger=CronTrigger(
            hour=11,                # 10 点
            minute=13,              # 30 分
            timezone="Asia/Shanghai"
        ),
        id="daily_tech_news",       # 任务 ID（唯一标识，方便调试和管理）
        name="生物制药推送",
        replace_existing=True,      # 如果同 ID 任务已存在，替换它（避免重复注册）
    )

    print("[调度器] 定时任务已注册: 每天 10:40 推送生物制药早报")
    return scheduler
