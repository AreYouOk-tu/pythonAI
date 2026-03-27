"""
员工数据模型定义
===============
Pydantic 模型相当于 TypeScript 的 interface/type
用于定义数据的结构、类型和验证规则

FastAPI 会自动用这些模型来：
1. 验证请求数据是否合法
2. 生成 API 文档（Swagger UI）
3. 序列化响应数据（自动转成 JSON）
"""

from pydantic import BaseModel, Field
from typing import Optional


class EmployeeTypeOption(BaseModel):
    """
    下拉选项的数据结构
    对应前端 <Select> 组件的 option 数据格式
    """

    # value: 提交给后端的实际值（英文标识符）
    value: str = Field(..., description="选项的唯一标识符，提交给后端使用")

    # label: 显示给用户看的文字
    label: str = Field(..., description="显示在下拉框中的文字")

    # description: 可选的说明文字
    description: Optional[str] = Field(None, description="类型说明")

    # disabled: 是否禁用这个选项
    disabled: bool = Field(False, description="是否禁用该选项")


class EmployeeTypeListResponse(BaseModel):
    """
    员工类型列表接口的响应数据结构
    这是返回给前端的完整 JSON 格式
    """

    # code: 业务状态码（0 = 成功，非 0 = 失败）
    code: int = Field(0, description="业务状态码，0 表示成功")

    # message: 提示信息
    message: str = Field("success", description="提示信息")

    # data: 实际的业务数据
    data: list[EmployeeTypeOption] = Field([], description="员工类型选项列表")


class ApiResponse(BaseModel):
    """
    通用 API 响应格式（可复用的响应结构）
    建议所有接口统一使用此格式，方便前端统一处理
    """

    code: int = Field(0, description="业务状态码，0 表示成功")
    message: str = Field("success", description="提示信息")
    data: Optional[dict | list | str | int] = Field(None, description="业务数据")
