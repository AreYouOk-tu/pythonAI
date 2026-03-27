"""
员工相关 API 路由
================
这个文件定义了所有与"员工"相关的 API 接口
相当于前端的一个 API 模块文件

FastAPI 中，每个函数对应一个 API 接口：
- @router.get("/xxx")    → HTTP GET 请求（查询数据）
- @router.post("/xxx")   → HTTP POST 请求（提交/创建数据）
- @router.put("/xxx")    → HTTP PUT 请求（更新数据）
- @router.delete("/xxx") → HTTP DELETE 请求（删除数据）
"""

from fastapi import APIRouter, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.database import get_db
from app.models.employee import EmployeeTypeOption, EmployeeTypeListResponse, ApiResponse
from app.services import employee as employee_service

# ==============================
# 创建路由器
# ==============================
# prefix="/api/employee" → 这个模块所有接口的路径前缀
# 比如这里定义 "/types"，实际访问路径就是 "/api/employee/types"
# tags=["员工管理"] → Swagger 文档里的分组标签，方便查看
router = APIRouter(prefix="/api/employee", tags=["员工管理"])


# ==============================
# 接口一：获取员工类型列表（下拉筛选用）
# ==============================
@router.get(
    "/types",
    response_model=EmployeeTypeListResponse,  # 指定响应数据格式，FastAPI 会自动校验和生成文档
    summary="获取员工类型下拉列表",
    description="返回所有员工类型选项，用于前端下拉框的数据源",
)
async def get_employee_types(
    # ---- Query 参数（URL 查询参数）----
    # 对应前端请求：axios.get('/api/employee/types', { params: { include_disabled: true } })
    # URL 格式：GET /api/employee/types?include_disabled=true
    include_disabled: Optional[bool] = Query(
        default=False,
        description="是否包含已禁用的选项，默认不包含"
    ),

    # ---- 依赖注入：数据库 Session ----
    # Depends(get_db) 告诉 FastAPI：调用这个接口前，先执行 get_db 函数，把返回值传进来
    # 相当于：db = await get_db()，但由框架自动管理生命周期（用完自动关闭）
    # 类比前端：类似 Vue 的 inject() 或 React 的 useContext()
    db: AsyncSession = Depends(get_db),
):
    """
    获取员工类型下拉列表

    用途：前端下拉筛选框、员工表单"类型"字段的数据来源

    调用示例：
    ```
    GET /api/employee/types                        → 只返回启用的选项（推荐日常使用）
    GET /api/employee/types?include_disabled=true  → 返回全部选项（含已禁用）
    ```

    返回格式示例：
    ```json
    {
      "code": 0,
      "message": "success",
      "data": [
        { "value": "formal",   "label": "正式员工",   "description": "...", "disabled": false },
        { "value": "intern",   "label": "实习生",     "description": "...", "disabled": false },
        { "value": "probation","label": "试用期员工", "description": "...", "disabled": false }
      ]
    }
    ```
    """

    # 调用 service 层查询数据库
    # 把数据库操作放在 service 层，路由层只负责请求/响应
    db_types = await employee_service.get_employee_types(
        db=db,
        include_disabled=include_disabled
    )

    # 把数据库模型（EmployeeType）转换成 API 响应模型（EmployeeTypeOption）
    # 两种模型分开是因为：
    #   数据库模型：有 id、created_at 等数据库字段，不需要暴露给前端
    #   响应模型：只包含前端需要的字段（value、label、description、disabled）
    options = [
        EmployeeTypeOption(
            value=t.value,
            label=t.label,
            description=t.description,
            disabled=t.disabled,
        )
        for t in db_types  # 列表推导式，相当于 JS 的 .map()
    ]

    return EmployeeTypeListResponse(code=0, message="success", data=options)


# ==============================
# 接口二：根据 value 获取单个员工类型
# ==============================
@router.get(
    "/types/{type_value}",
    response_model=ApiResponse,
    summary="根据 value 获取单个员工类型",
    description="传入员工类型的 value（如 formal），返回该类型的详细信息",
)
async def get_employee_type_by_value(
    # ---- 路径参数（Path 参数）----
    # URL 中 /types/formal 里的 "formal" 会被提取出来赋值给 type_value
    # 相当于 Express.js 的 req.params.type_value
    type_value: str,
    db: AsyncSession = Depends(get_db),
):
    """
    根据 value 值查询单个员工类型

    调用示例：
    ```
    GET /api/employee/types/formal           → 正式员工
    GET /api/employee/types/intern           → 实习生
    GET /api/employee/types/probation        → 试用期员工
    GET /api/employee/types/third_party      → 第三方人员
    GET /api/employee/types/rehired_retiree  → 返聘员工
    ```
    """

    found = await employee_service.get_employee_type_by_value(db=db, value=type_value)

    if found is None:
        # 找不到时返回业务错误
        # HTTP 状态码仍是 200，但业务 code 是 404，这是国内常见 API 规范
        return ApiResponse(
            code=404,
            message=f"未找到类型 '{type_value}'，可用值：formal / intern / third_party / rehired_retiree / probation",
            data=None
        )

    return ApiResponse(
        code=0,
        message="success",
        data={
            "value": found.value,
            "label": found.label,
            "description": found.description,
            "disabled": found.disabled,
        }
    )
