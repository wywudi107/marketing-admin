"""
管理员操作日志表模型
"""
from sqlalchemy import Column, String, TIMESTAMP, text, Text, Index
from sqlalchemy.dialects.mysql import BIGINT, INTEGER

from app.database.mysql import Base


class AdminOperationLog(Base):
    __tablename__ = 'admin_operation_logs'
    __table_args__ = (
        Index('idx_admin_id', 'admin_id'),
        Index('idx_module_created', 'module', 'created_at'),
    )

    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    admin_id = Column(INTEGER(unsigned=True), nullable=False, comment='操作管理员ID')
    admin_username = Column(String(50), nullable=False, comment='管理员账号')
    module = Column(String(50), nullable=False, comment='操作模块')
    action = Column(String(100), nullable=False, comment='操作动作')
    target_id = Column(String(50), nullable=True, comment='操作对象ID')
    detail = Column(Text, nullable=True, comment='操作详情（JSON）')
    ip = Column(String(45), nullable=True, comment='操作IP')
    created_at = Column(TIMESTAMP, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
