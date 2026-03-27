"""
员工相关数据库查询服务
=====================
Service 层（服务层）专门负责数据库操作，把 SQL 查询逻辑从路由中抽离出来。

为什么要分层？
- 路由（routes）→ 只负责处理 HTTP 请求和响应，不写业务逻辑
- 服务（services）→ 只负责数据库操作和业务逻辑，不关心 HTTP

这样分层的好处：
  1. 代码职责清晰，容易维护
  2. 同一个查询逻辑可以被多个路由复用
  3. 写单元测试更容易（可以单独测 service，不需要启动 HTTP 服务器）

类比前端：相当于把 API 调用逻辑抽成独立的 service 文件，路由组件只调用 service
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db_models import EmployeeType


# ==============================
# 查询员工类型列表
# ==============================
async def get_employee_types(
    db: AsyncSession,
    include_disabled: bool = False
) -> list[EmployeeType]:
    """
    从数据库查询员工类型列表

    参数：
        db              → 数据库 Session（由 FastAPI 依赖注入传入）
        include_disabled → 是否包含已禁用的选项

    返回：
        EmployeeType 对象列表（对应数据库里的多行数据）

    等价 SQL（include_disabled=False 时）：
        SELECT * FROM employee_types
        WHERE disabled = false
        ORDER BY sort_order ASC, id ASC;
    """

    # select(EmployeeType) → 相当于 SQL 的 SELECT * FROM employee_types
    # 这里用的是 SQLAlchemy 的"查询构建器"（Query Builder）
    # 类比前端：类似 Prisma 的 prisma.employeeType.findMany({ where: {...} })
    stmt = select(EmployeeType).order_by(
        EmployeeType.sort_order.asc(),  # 先按 sort_order 升序排列
        EmployeeType.id.asc()           # sort_order 相同时，按 id 升序
    )

    # 如果不包含禁用项，加上 WHERE disabled = false 条件
    if not include_disabled:
        # .where() 相当于 SQL 的 WHERE 子句
        # EmployeeType.disabled == False 是 SQLAlchemy 的写法（注意是两个等号）
        stmt = stmt.where(EmployeeType.disabled == False)

    # await db.execute(stmt) → 执行 SQL 查询（异步，需要 await）
    # scalars() → 把结果转成 Python 对象列表（而不是原始的数据库行）
    # all() → 获取全部结果（返回一个列表）
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ==============================
# 根据 value 查询单个员工类型
# ==============================
async def get_employee_type_by_value(
    db: AsyncSession,
    value: str
) -> EmployeeType | None:
    """
    根据 value 字段查询单条记录

    参数：
        db    → 数据库 Session
        value → 要查找的标识符（如 "formal"、"intern"）

    返回：
        找到时返回 EmployeeType 对象
        找不到时返回 None

    等价 SQL：
        SELECT * FROM employee_types WHERE value = 'formal' LIMIT 1;
    """

    stmt = select(EmployeeType).where(EmployeeType.value == value)

    result = await db.execute(stmt)

    # scalar_one_or_none() → 查一条记录
    #   找到 → 返回该对象
    #   找不到 → 返回 None（不报错）
    #   找到多条 → 抛出异常（说明数据有问题，value 应该唯一）
    return result.scalar_one_or_none()


# ==============================
# 初始化默认数据（首次使用时调用）
# ==============================
async def init_default_employee_types(db: AsyncSession) -> None:
    """
    向数据库插入默认的员工类型数据

    这个函数在服务启动时调用一次：
    - 如果数据库里已有数据，跳过（不重复插入）
    - 如果是全新的数据库，插入初始数据

    等价 SQL：
        INSERT INTO employee_types (value, label, description, sort_order)
        VALUES ('formal', '正式员工', '...', 1), ...
        ON CONFLICT (value) DO NOTHING;  -- 已存在则跳过
    """

    # 先检查数据库里是否已有数据
    stmt = select(EmployeeType)
    result = await db.execute(stmt)
    existing = result.scalars().first()  # 取第一条，有数据就不是 None

    # 如果已有数据，不重复插入
    if existing:
        return

    # 定义默认数据
    default_types = [
        EmployeeType(value="formal",          label="正式员工",   description="与公司签订劳动合同的全职正式员工",               disabled=False, sort_order=1),
        EmployeeType(value="intern",           label="实习生",     description="在校学生实习或实训人员，通常签订实习协议",       disabled=False, sort_order=2),
        EmployeeType(value="third_party",      label="第三方人员", description="通过劳务派遣或外包公司派驻的员工",               disabled=False, sort_order=3),
        EmployeeType(value="rehired_retiree",  label="返聘员工",   description="已办理退休手续后被公司重新聘用的人员",           disabled=False, sort_order=4),
        EmployeeType(value="probation",        label="试用期员工", description="正在试用期内、尚未转正的员工",                   disabled=False, sort_order=5),
    ]

    # db.add_all() → 把多个对象加入 session（相当于准备好要插入的数据）
    # 注意：add_all 之后数据还没写入数据库，需要 commit 才真正写入
    # commit 在 get_db 的 yield 之后自动执行，所以这里不需要手动 commit
    db.add_all(default_types)
    print("[完成] 已初始化默认员工类型数据")
