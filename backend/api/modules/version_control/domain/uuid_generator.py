"""
Logical UUID Generator and Normalizer.
提供需求空间实体的稳定身份 `logical_uuid` 生成与回填算法。
"""
from typing import Any
import uuid


def generate_logical_uuid() -> str:
    """
    生成一个新的 UUID4 字符串用作实体的稳定逻辑身份。
    跨分支复制或提交还原时，此 UUID 将始终保持传递。
    """
    return str(uuid.uuid4())


def ensure_logical_uuid(entity: Any) -> str:
    """
    确保实体具备有效的 logical_uuid，若缺失或为空则自动生成并赋值。

    :param entity: 包含 logical_uuid 属性的 SQLAlchemy 实体对象
    :return: 实体的 logical_uuid 字符串
    """
    current_uuid = getattr(entity, "logical_uuid", None)
    if not current_uuid:
        new_uuid = generate_logical_uuid()
        setattr(entity, "logical_uuid", new_uuid)
        return new_uuid
    return str(current_uuid)
