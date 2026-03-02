"""
每日统计结果表模型
"""
from sqlalchemy import Column, String, Date, TIMESTAMP, text, UniqueConstraint, Index
from sqlalchemy.dialects.mysql import BIGINT, INTEGER

from app.database.mysql import Base


class DailyStats(Base):
    __tablename__ = 'daily_stats'
    __table_args__ = (
        UniqueConstraint('stat_date', 'invite_code', name='uk_date_invite'),
        Index('idx_stat_date', 'stat_date'),
        Index('idx_invite_code', 'invite_code'),
    )

    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    stat_date = Column(Date, nullable=False, comment='统计日期')
    invite_code = Column(String(50), nullable=False, comment='邀请码')
    register_count = Column(INTEGER(unsigned=True), nullable=False, default=0, comment='注册人数')
    first_recharge_count = Column(INTEGER(unsigned=True), nullable=False, default=0, comment='首充人数')
    first_recharge_amount = Column(BIGINT(unsigned=True), nullable=False, default=0, comment='首充金额')
    created_at = Column(TIMESTAMP, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = Column(TIMESTAMP, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
