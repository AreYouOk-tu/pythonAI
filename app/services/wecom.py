"""
企业微信消息推送服务
===================
通过企业微信群机器人的 Webhook 发送消息

配置步骤：
  1. 在企业微信群里，点击右上角「...」→「添加群机器人」
  2. 创建机器人后复制 Webhook 地址
  3. 把地址填入 .env 文件的 WECOM_WEBHOOK_URL

支持的消息类型：
  - 文本消息（markdown 格式）
"""

import httpx
import os
from dotenv import load_dotenv

load_dotenv()


async def send_wecom_markdown(content: str) -> bool:
    """
    向企业微信群机器人发送 Markdown 格式消息

    参数：
        content → Markdown 格式的消息内容

    返回：
        True = 发送成功，False = 发送失败

    企业微信 Markdown 支持的语法：
        **加粗**、> 引用、[链接](url)
        # 标题（只支持一到三级）
        `代码`
    """

    # 从环境变量读取 Webhook 地址
    webhook_url = os.getenv("WECOM_WEBHOOK_URL", "")

    if not webhook_url:
        print("[推送] 未配置 WECOM_WEBHOOK_URL，跳过推送")
        return False

    # 企业微信机器人的请求体格式（固定结构）
    payload = {
        "msgtype": "markdown",   # 消息类型：markdown
        "markdown": {
            "content": content   # Markdown 内容
        }
    }

    try:
        # httpx.AsyncClient → 异步 HTTP 客户端（相当于 axios）
        # timeout=10 → 10秒超时，避免网络慢时一直等待
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(webhook_url, json=payload)
            result = response.json()

            # 企业微信返回 {"errcode": 0, "errmsg": "ok"} 表示成功
            if result.get("errcode") == 0:
                print("[推送] 企业微信消息发送成功")
                return True
            else:
                print(f"[推送] 企业微信发送失败: {result}")
                return False

    except Exception as e:
        print(f"[推送] 企业微信发送异常: {e}")
        return False
