"""
本地大模型调试工具
=================
这个文件是一个独立的调试脚本，专门用来在本地直接测试 Claude 大模型。
不需要启动 FastAPI 服务，直接 python debug_llm.py 运行即可。

使用步骤：
  1. 确保 .env 文件中配置了 ANTHROPIC_API_KEY
  2. 运行命令：python debug_llm.py
  3. 根据菜单提示选择要测试的功能

适用场景：
  - 调试 prompt（提示词）效果
  - 测试不同参数对输出的影响
  - 快速验证 API Key 是否有效
  - 开发新的 AI 功能前先在这里原型测试
"""

import os
import sys
from dotenv import load_dotenv

# ==============================
# 加载 .env 文件中的配置
# ==============================
# 这行必须在 import anthropic 之前，否则读不到 API Key
load_dotenv()


# ==============================
# 工具函数：打印分隔线（美化输出用）
# ==============================
def print_divider(title: str = ""):
    """在终端打印一条带标题的分隔线，让输出更易读"""
    line = "=" * 60
    if title:
        print(f"\n{line}")
        print(f"  {title}")
        print(line)
    else:
        print(line)


# ==============================
# 功能一：单轮对话
# ==============================
def test_single_chat():
    """
    最基础的单轮对话测试
    发送一条消息，打印 AI 的回复
    适合快速验证 API 是否正常工作
    """
    print_divider("单轮对话测试")

    # 从终端读取用户输入
    # input() 相当于 JS 的 prompt()，会暂停程序等用户输入
    user_message = input("\n请输入你想问的问题（直接回车用默认问题）：").strip()

    # 如果用户直接按回车，使用默认问题
    if not user_message:
        user_message = "你好！请用一句话介绍一下你自己。"
        print(f"使用默认问题：{user_message}")

    print("\n正在调用 Claude API，请稍候...\n")

    try:
        import anthropic

        # 创建客户端
        # api_key 从环境变量读取，不要把真实 Key 硬写在代码里
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        # 调用 API 发送消息
        # model: 使用的模型版本
        # max_tokens: 最多生成多少 token（1个中文字约 1.5 token）
        # system: 系统提示词，告诉 AI 它的角色（相当于给 AI 一个角色设定）
        # messages: 对话历史，格式是 [{"role": "user"/"assistant", "content": "消息内容"}]
        response = client.messages.create(
            model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6"),
            max_tokens=1024,
            system="你是一个专业的 HR 助手，请用简洁清晰的中文回答。",
            messages=[
                {"role": "user", "content": user_message}
            ]
        )

        # 提取回复文本
        # response.content 是一个列表（AI 可能返回多个内容块）
        # 这里取第一个文本块的内容
        reply = response.content[0].text

        print("【AI 回复】")
        print(reply)

        # 打印 token 使用量，方便了解 API 消耗
        print(f"\n【Token 使用量】")
        print(f"  输入: {response.usage.input_tokens} tokens")
        print(f"  输出: {response.usage.output_tokens} tokens")

    except anthropic.AuthenticationError:
        # API Key 无效时的错误
        print("❌ 错误：API Key 无效，请检查 .env 文件中的 ANTHROPIC_API_KEY")
    except anthropic.RateLimitError:
        print("❌ 错误：请求频率超限，请稍后再试")
    except Exception as e:
        print(f"❌ 错误：{e}")


# ==============================
# 功能二：多轮对话（带上下文记忆）
# ==============================
def test_multi_turn_chat():
    """
    多轮对话测试
    模拟连续对话，AI 会记住上文内容
    输入 'quit' 或 'exit' 退出对话
    """
    print_divider("多轮对话测试（输入 quit 退出）")
    print("提示：AI 会记住本次对话的上下文\n")

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        # 对话历史列表，用来存储所有对话记录
        # 每条消息格式：{"role": "user" 或 "assistant", "content": "消息内容"}
        # 每次调用 API 时把完整历史传过去，AI 就能"记住"之前说过的话
        conversation_history = []

        # 系统提示词（角色设定）
        system_prompt = "你是一个专业的企业 HR 顾问，帮助分析人员管理问题。请用简洁的中文回复。"

        print(f"当前角色设定：{system_prompt}\n")

        # 无限循环，直到用户输入 quit/exit
        while True:
            # 获取用户输入
            user_input = input("你：").strip()

            # 退出命令检查
            if user_input.lower() in ["quit", "exit", "退出", "q"]:
                print("对话结束。")
                break

            # 空输入跳过
            if not user_input:
                continue

            # 把用户消息加入对话历史
            conversation_history.append({
                "role": "user",
                "content": user_input
            })

            print("AI 正在思考...", end="", flush=True)

            try:
                # 把完整的对话历史发给 API
                # 这样 AI 就能看到之前所有对话，实现"记忆"功能
                response = client.messages.create(
                    model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6"),
                    max_tokens=1024,
                    system=system_prompt,
                    messages=conversation_history  # 传入完整历史
                )

                # 提取 AI 回复
                assistant_reply = response.content[0].text

                # 把 AI 的回复也加入历史，下次对话时 AI 能看到自己之前说过什么
                conversation_history.append({
                    "role": "assistant",
                    "content": assistant_reply
                })

                # 清除"思考中..."提示，打印正式回复
                print(f"\rAI：{assistant_reply}\n")

            except Exception as e:
                print(f"\r❌ 调用出错：{e}\n")
                # 出错时把刚才加入的用户消息移除，避免污染历史
                conversation_history.pop()

    except ImportError:
        print("❌ 错误：未安装 anthropic 包，请运行 pip install anthropic")
    except anthropic.AuthenticationError:
        print("❌ 错误：API Key 无效")
    except Exception as e:
        print(f"❌ 错误：{e}")


# ==============================
# 功能三：自定义参数测试
# ==============================
def test_custom_params():
    """
    自定义参数测试
    可以手动调整 system prompt、max_tokens 等参数，
    观察不同参数对输出结果的影响
    """
    print_divider("自定义参数测试")

    # 收集用户自定义配置
    print("\n【配置参数】（直接回车使用括号内的默认值）\n")

    # 系统提示词
    system = input("系统提示词 (默认: 你是一个专业的 HR 助手): ").strip()
    if not system:
        system = "你是一个专业的 HR 助手，请用简洁的中文回复。"

    # 用户消息
    message = input("用户消息 (默认: 帮我分析一下员工离职率高的原因): ").strip()
    if not message:
        message = "帮我分析一下员工离职率高的常见原因，给出3条主要原因。"

    # 最大 token 数
    max_tokens_str = input("最大 token 数 (默认: 512): ").strip()
    try:
        max_tokens = int(max_tokens_str) if max_tokens_str else 512
    except ValueError:
        print("输入无效，使用默认值 512")
        max_tokens = 512

    # 显示最终配置
    print("\n【使用配置】")
    print(f"  模型:      {os.getenv('CLAUDE_MODEL', 'claude-sonnet-4-6')}")
    print(f"  系统提示:  {system}")
    print(f"  用户消息:  {message}")
    print(f"  最大token: {max_tokens}")
    print("\n正在调用 API...\n")

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        response = client.messages.create(
            model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6"),
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": message}]
        )

        print("【AI 回复】")
        print(response.content[0].text)

        print(f"\n【统计信息】")
        print(f"  输入 tokens:  {response.usage.input_tokens}")
        print(f"  输出 tokens:  {response.usage.output_tokens}")
        print(f"  停止原因:     {response.stop_reason}")
        # stop_reason 说明：
        #   end_turn   → AI 正常写完了
        #   max_tokens → 达到 token 上限，回复被截断（需要增大 max_tokens）

    except Exception as e:
        print(f"❌ 错误：{e}")


# ==============================
# 功能四：流式输出（打字机效果）
# ==============================
def test_streaming():
    """
    流式输出测试
    AI 边生成边输出，看起来像打字机效果
    长文本时用户体验更好，不需要等 AI 全部生成完再显示
    """
    print_divider("流式输出测试（打字机效果）")

    user_message = input("\n请输入问题（直接回车用默认）：").strip()
    if not user_message:
        user_message = "请用200字左右介绍一下企业人力资源管理的核心工作。"
        print(f"使用默认问题：{user_message}")

    print("\n【AI 回复（实时输出）】")

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        # 使用流式 API
        # with client.messages.stream(...) as stream 相当于创建一个"数据流"
        # 每生成一个文字片段就会立即发送过来，而不是等全部生成完
        with client.messages.stream(
            model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6"),
            max_tokens=1024,
            system="你是一个专业的 HR 助手，请用清晰的中文回复。",
            messages=[{"role": "user", "content": user_message}]
        ) as stream:
            # text_stream 是一个迭代器，每次 yield 一小段文字
            for text_chunk in stream.text_stream:
                # end="" 防止换行，flush=True 立即打印不缓存
                # 效果：文字一个个出现，像打字机一样
                print(text_chunk, end="", flush=True)

        print("\n\n【流式输出完成】")

        # 获取完整响应信息（包含 token 使用量）
        final_message = stream.get_final_message()
        print(f"  输入 tokens: {final_message.usage.input_tokens}")
        print(f"  输出 tokens: {final_message.usage.output_tokens}")

    except Exception as e:
        print(f"\n❌ 错误：{e}")


# ==============================
# 功能五：检查配置是否正确
# ==============================
def check_config():
    """
    检查环境配置
    验证 API Key 是否正确配置，并显示当前配置信息
    """
    print_divider("检查环境配置")

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

    print(f"\n  API Key:  {'已配置（' + api_key[:8] + '...）' if api_key and api_key != 'your_api_key_here' else '❌ 未配置或使用了默认值'}")
    print(f"  模型:     {model}")
    print(f"  Python:   {sys.version.split()[0]}")

    # 检查是否安装了 anthropic 包
    try:
        import anthropic
        print(f"  anthropic SDK 版本: {anthropic.__version__}")
    except ImportError:
        print("  anthropic SDK: ❌ 未安装，请运行 pip install anthropic")
        return

    # 如果 API Key 有效，发送一条测试消息验证
    if not api_key or api_key == "your_api_key_here":
        print("\n⚠️  请先在 .env 文件中配置有效的 ANTHROPIC_API_KEY")
        print("   文件位置：项目根目录 / .env")
        print("   配置格式：ANTHROPIC_API_KEY=sk-ant-api03-你的key")
        return

    print("\n正在验证 API Key（发送测试消息）...")
    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=50,
            messages=[{"role": "user", "content": "回复'OK'两个字"}]
        )
        print(f"  ✅ API 连接正常，测试回复：{response.content[0].text.strip()}")
    except anthropic.AuthenticationError:
        print("  ❌ API Key 无效，请检查是否填写正确")
    except Exception as e:
        print(f"  ❌ 连接失败：{e}")


# ==============================
# 主菜单
# ==============================
def main():
    """
    程序入口：显示功能菜单，让用户选择要测试的功能
    """
    print_divider("Claude 大模型本地调试工具")
    print("\n  当前配置的模型：", os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6"))

    # 功能菜单列表
    # 元组格式：(菜单序号, 功能名称, 对应函数)
    menu_options = [
        ("1", "检查配置（验证 API Key 是否有效）", check_config),
        ("2", "单轮对话（发一条消息，看 AI 回复）", test_single_chat),
        ("3", "多轮对话（连续对话，AI 记住上下文）", test_multi_turn_chat),
        ("4", "自定义参数（调整 prompt 和 token 上限）", test_custom_params),
        ("5", "流式输出（打字机效果）", test_streaming),
        ("0", "退出", None),
    ]

    while True:
        print_divider("功能菜单")
        for key, name, _ in menu_options:
            print(f"  [{key}] {name}")

        choice = input("\n请选择功能（输入数字）：").strip()

        # 查找用户选择的功能
        selected = next((opt for opt in menu_options if opt[0] == choice), None)

        if selected is None:
            print("无效选项，请重新输入")
            continue

        if selected[0] == "0":
            print("\n再见！")
            break

        # 调用对应的函数
        selected[2]()

        # 每次操作完暂停一下，等用户看完结果再继续
        input("\n按回车键返回主菜单...")


# ==============================
# Python 程序入口
# ==============================
# __name__ == "__main__" 表示这个文件是被直接运行的（不是被 import 引入的）
# 相当于 Node.js 中判断是否是主模块
if __name__ == "__main__":
    main()
