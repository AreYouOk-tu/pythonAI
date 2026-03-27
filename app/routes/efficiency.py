"""
效能数据 API 接口
================
演示：如何从数据库取数据，然后以 JSON 格式返回给前端

完整数据流：
  前端请求
    → FastAPI 路由（本文件）接收请求
    → 调用 service 层执行 SQL
    → 数据库返回数据
    → 转成 JSON 响应给前端

类比前端：这里相当于你写 axios 请求，只不过方向反过来了，
你是"提供数据的一方"，而不是"消费数据的一方"
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.services.efficiency import get_efficiency_list


router = APIRouter(prefix="/api/efficiency", tags=["效能数据"])


# ---- 定义返回给前端的数据结构 ----
# 类比前端：相当于 TypeScript 的 interface，定义前端收到的 JSON 长什么样
class EfficiencyItem(BaseModel):
    id: int
    department: str            # 部门名称
    month: str                 # 统计月份，如 "2024-03"
    headcount: int             # 在岗人数
    task_completion_rate: float  # 任务完成率，如 0.92 表示 92%
    output_per_person: float   # 人均产出（万元）
    score: float               # 效能综合评分

    # 告诉 Pydantic：可以直接从 SQLAlchemy 对象（ORM 模型）转换
    # 没有这行，下面的 EfficiencyItem.model_validate(record) 会报错
    model_config = {"from_attributes": True}


class EfficiencyResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: list[EfficiencyItem]
    total: int  # 总条数，前端分页时需要


# ---- 接口定义 ----
@router.get(
    "/list",
    response_model=EfficiencyResponse,
    summary="获取部门效能列表",
    description="从数据库查询效能月报数据，支持按月份筛选",
)
async def get_efficiency(
    # Query 参数：前端可以这样调用：GET /api/efficiency/list?month=2024-03
    # Optional[str] 表示这个参数可以不传，不传时 month=None，查全部数据
    month: Optional[str] = Query(default=None, description="按月份筛选，格式 YYYY-MM，如 2024-03"),

    # Depends(get_db) → FastAPI 自动帮你创建数据库连接，用完自动关闭
    # 相当于：db = 连接数据库()，但由框架管理，不用手动关闭
    db: AsyncSession = Depends(get_db),
):
    """
    获取效能数据列表

    前端调用示例：
    ```javascript
    // 获取所有月份数据
    const res = await axios.get('/api/efficiency/list')

    // 获取指定月份数据
    const res = await axios.get('/api/efficiency/list', {
      params: { month: '2024-03' }
    })

    console.log(res.data.data)   // 效能列表数组
    console.log(res.data.total)  // 总条数
    ```
    """

    # 第一步：调用 service 层，执行数据库查询
    # 这一行执行后，records 是一个 Python 列表，每个元素对应数据库的一行
    records = await get_efficiency_list(db=db, month=month)

    # 第二步：把数据库对象转成 Pydantic 模型（用于序列化成 JSON）
    # model_validate(record) → 从 ORM 对象提取字段，转成 EfficiencyItem
    # 类比前端：相当于 records.map(r => ({ id: r.id, department: r.department, ... }))
    items = [EfficiencyItem.model_validate(r) for r in records]

    # 第三步：包装成统一格式返回
    # FastAPI 会自动把这个对象序列化成 JSON 字符串发给前端
    return EfficiencyResponse(
        code=0,
        message="success",
        data=items,
        total=len(items),
    )
