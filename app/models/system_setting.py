"""
系统参数设置模型
"""
from sqlalchemy import Column, String, TIMESTAMP, text
from sqlalchemy.dialects.mysql import BIGINT

from app.database.mysql import Base


class SystemSetting(Base):
    __tablename__ = 'system_settings'

    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    setting_key = Column(String(50), unique=True, nullable=False, comment='参数键')
    setting_value = Column(String(255), nullable=False, default='', comment='参数值')
    description = Column(String(100), nullable=True, comment='参数说明')
    updated_at = Column(TIMESTAMP, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
