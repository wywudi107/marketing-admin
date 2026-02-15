"""
管理员角色表模型
"""
from sqlalchemy import Column, String, TIMESTAMP, text, JSON
from sqlalchemy.dialects.mysql import TINYINT, INTEGER

from app.database.mysql import Base


class AdminRole(Base):
    __tablename__ = 'admin_roles'

    id = Column(INTEGER(unsigned=True), primary_key=True, autoincrement=True, comment='角色ID')
    role_name = Column(String(50), nullable=False, comment='角色名称')
    role_key = Column(String(50), unique=True, nullable=False, comment='角色标识')
    permissions = Column(JSON, nullable=False, comment='权限列表（JSON数组）')
    status = Column(TINYINT(unsigned=True), nullable=False, default=1, comment='0=禁用,1=启用')
    remark = Column(String(255), nullable=True, comment='备注')
    created_at = Column(TIMESTAMP, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = Column(TIMESTAMP, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
