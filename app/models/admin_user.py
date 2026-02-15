"""
管理员用户表模型
"""
from sqlalchemy import Column, String, TIMESTAMP, text, Index
from sqlalchemy.dialects.mysql import TINYINT, INTEGER

from app.database.mysql import Base


class AdminUser(Base):
    __tablename__ = 'admin_users'
    __table_args__ = (
        Index('idx_role_id', 'role_id'),
    )

    id = Column(INTEGER(unsigned=True), primary_key=True, autoincrement=True, comment='管理员ID')
    username = Column(String(50), unique=True, nullable=False, comment='登录账号')
    password = Column(String(255), nullable=False, comment='密码哈希（bcrypt）')
    nickname = Column(String(50), nullable=True, comment='显示昵称')
    role_id = Column(INTEGER(unsigned=True), nullable=False, comment='角色ID')
    status = Column(TINYINT(unsigned=True), nullable=False, default=1, comment='0=禁用,1=启用')
    last_login_at = Column(TIMESTAMP, nullable=True, comment='最后登录时间')
    last_login_ip = Column(String(45), nullable=True, comment='最后登录IP')
    created_at = Column(TIMESTAMP, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = Column(TIMESTAMP, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
