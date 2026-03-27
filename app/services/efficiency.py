"""
效能数据查询服务
================
负责所有和 efficiency_records 表相关的数据库操作
路由层只负责 HTTP，数据库操作全部放这里
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models.db_models import EfficiencyRecord


async def get_efficiency_list(
    db: AsyncSession,
    month: str = None,      # 可选筛选：按月份过滤，如 "2024-03"
    limit: int = 20         # 最多返回多少条，防止一次返回太多数据
) -> list[EfficiencyRecord]:
    """
    查询效能记录列表

    等价 SQL（无月份筛选时）：
        SELECT * FROM efficiency_records
        ORDER BY month DESC, score DESC
        LIMIT 20;
    """

    # select(EfficiencyRecord) → SELECT * FROM efficiency_records
    stmt = select(EfficiencyRecord)

    # 如果传了 month 参数，加上 WHERE 条件
    # 等价 SQL：WHERE month = '2024-03'
    if month:
        stmt = stmt.where(EfficiencyRecord.month == month)

    # 排序：先按月份倒序（最新的在前），再按评分倒序（评分高的在前）
    # 等价 SQL：ORDER BY month DESC, score DESC
    stmt = stmt.order_by(desc(EfficiencyRecord.month), desc(EfficiencyRecord.score))

    # LIMIT：限制返回条数，避免数据库压力过大
    # 等价 SQL：LIMIT 20
    stmt = stmt.limit(limit)

    # await db.execute(stmt) → 真正执行 SQL，异步等待数据库返回结果
    # scalars().all() → 把结果转成 Python 对象列表
    result = await db.execute(stmt)
    # 先把结果转成列表保存到变量，再打印和返回（只能消费一次，不能调用两次）
    records = list(result.scalars().all())
    print(f"从数据库拿到的数据条数：{len(records)}")
    return records


async def init_default_efficiency_data(db: AsyncSession) -> None:
    """
    插入示例数据（首次启动时，如果表是空的才插入）
    方便你启动后直接调接口看到数据
    """
    stmt = select(EfficiencyRecord)
    result = await db.execute(stmt)
    if result.scalars().first():
        return  # 已有数据，跳过

    sample_data = [
        EfficiencyRecord(department="技术部",  month="2024-03", headcount=45, task_completion_rate=0.92, output_per_person=18.5, score=91.0),
        EfficiencyRecord(department="市场部",  month="2024-02", headcount=20, task_completion_rate=0.85, output_per_person=22.3, score=87.5),
        EfficiencyRecord(department="产品部",  month="2024-04", headcount=12, task_completion_rate=0.88, output_per_person=15.0, score=85.0),
        EfficiencyRecord(department="人力资源", month="2024-02", headcount=8,  task_completion_rate=0.95, output_per_person=10.2, score=89.0),
        EfficiencyRecord(department="技术部",  month="2024-01", headcount=43, task_completion_rate=0.89, output_per_person=17.8, score=88.5),
        EfficiencyRecord(department="市场部",  month="2024-05", headcount=19, task_completion_rate=0.80, output_per_person=20.1, score=83.0),
    ]

    db.add_all(sample_data)
    print("[完成] 已插入效能示例数据")
