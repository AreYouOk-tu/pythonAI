"""
数据库表结构定义（ORM 模型）
===========================
ORM = Object-Relational Mapping，对象关系映射
作用：用 Python 类来描述数据库表结构，不用手写 SQL 建表语句

类比前端理解：
- 一个 Python 类  → 对应数据库里的一张表
- 类的属性        → 对应表的一列（字段）
- 一个类的实例    → 对应表里的一行数据（一条记录）

例如：
    # Python 代码                    →    数据库表
    class EmployeeType(Base):        →    CREATE TABLE employee_types (
        id = Column(Integer)         →        id SERIAL PRIMARY KEY,
        value = Column(String)       →        value VARCHAR NOT NULL,
        label = Column(String)       →        label VARCHAR NOT NULL
                                     →    );
"""

from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Integer, Text, Float
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


# ==============================
# 员工类型表
# ==============================
class EmployeeType(Base):
    """
    员工类型表，对应数据库中的 employee_types 表

    这张表存储下拉选项的数据，比直接写死在代码里更灵活：
    - 可以随时在数据库里增删改选项，不需要改代码重启服务
    - 可以记录每个选项的创建时间、是否禁用等额外信息
    """

    # __tablename__ 指定这个类对应数据库里哪张表
    # 相当于告诉 SQLAlchemy："这个类就是 employee_types 这张表"
    __tablename__ = "employee_types"

    # ---- 字段定义 ----
    # Mapped[int] → 这个字段的 Python 类型是 int
    # mapped_column(...) → 定义数据库列的属性
    # 相当于 TypeScript 的 @Column() 装饰器

    # 主键 ID，自增整数（数据库自动生成，不需要手动填写）
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,  # 主键：唯一标识每一行数据
        autoincrement=True,  # 自增：每次插入新数据自动 +1
        comment="主键ID"
    )

    # value 字段：提交给后端的标识符（如 "formal"、"intern"）
    # 注意：Hologres（阿里云数据仓库）不支持 UNIQUE 约束，已移除
    # 改为在应用层（service 层）保证 value 不重复
    value: Mapped[str] = mapped_column(
        String(50),    # 最多 50 个字符的字符串
        nullable=False,  # 不允许为空（必填）
        comment="选项标识符（英文，如 formal/intern）"
    )

    # label 字段：显示给用户的中文名称（如 "正式员工"）
    label: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="显示名称（中文）"
    )

    # description 字段：选项说明，可以为空（Optional）
    description: Mapped[str | None] = mapped_column(
        Text,          # Text 类型：适合存储较长的文本
        nullable=True,   # 允许为空
        comment="选项说明"
    )

    # disabled 字段：是否禁用
    disabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,   # 默认不禁用
        nullable=False,
        comment="是否禁用（True=禁用，页面灰显）"
    )

    # sort_order 字段：排序权重，数字越小越靠前
    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="排序权重，越小越靠前"
    )

    # created_at 字段：记录创建时间（数据库自动填写）
    # server_default=func.now() → 插入数据时，数据库自动填入当前时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="创建时间"
    )

    # updated_at 字段：记录最后更新时间（每次修改自动更新）
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),   # 每次更新这条记录时自动刷新时间
        comment="最后更新时间"
    )

    def __repr__(self) -> str:
        """
        repr 定义这个对象打印出来长什么样
        相当于 JS 的 toString() 方法
        调试时 print(employee_type) 会显示这个格式
        """
        return f"<EmployeeType id={self.id} value={self.value} label={self.label}>"


# ==============================
# 部门效能记录表
# ==============================
class EfficiencyRecord(Base):
    """
    部门效能月报表，对应数据库中的 efficiency_records 表
    记录每个部门每个月的人效数据
    """
    __tablename__ = "efficiency_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 部门名称，如 "技术部"、"市场部"
    department: Mapped[str] = mapped_column(String(50), nullable=False, comment="部门名称")

    # 统计月份，格式 "2024-03"
    month: Mapped[str] = mapped_column(String(7), nullable=False, comment="统计月份 YYYY-MM")

    # 在岗人数
    headcount: Mapped[int] = mapped_column(Integer, nullable=False, comment="在岗人数")

    # 任务完成率，0.0 ~ 1.0，如 0.85 表示 85%
    task_completion_rate: Mapped[float] = mapped_column(Float, nullable=False, comment="任务完成率 0~1")

    # 人均产出（万元）
    output_per_person: Mapped[float] = mapped_column(Float, nullable=False, comment="人均产出（万元）")

    # 效能综合评分，满分 100
    score: Mapped[float] = mapped_column(Float, nullable=False, comment="效能综合评分 0~100")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="记录创建时间"
    )


# ==============================
# 文生图历史记录表
# ==============================
class ImageRecord(Base):
    """
    文生图生成记录表，对应数据库中的 image_records 表
    记录每次生成的提示词、图片地址、生成状态等信息
    """
    __tablename__ = "image_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键ID")

    # 用户原始输入的中文描述
    user_prompt: Mapped[str] = mapped_column(Text, nullable=False, comment="用户原始描述（中文）")

    # Claude 优化后的英文提示词（实际送给通义万相的）
    optimized_prompt: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Claude 优化后的英文提示词")

    # 图片风格，如 realistic/anime/watercolor 等
    style: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="图片风格")

    # 生成状态：pending / success / failed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", comment="生成状态")

    # OSS 上的图片永久地址（生成成功后填入）
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True, comment="OSS 图片永久地址")

    # 失败原因（生成失败时填入）
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True, comment="失败原因")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="创建时间"
    )
