"""
结算申请模型
"""
from sqlalchemy import Column, String, TIMESTAMP, text, Index, SmallInteger
from sqlalchemy.dialects.mysql import BIGINT, INTEGER

from app.database.mysql import Base


class SettlementApplication(Base):
    __tablename__ = 'settlement_applications'
    __table_args__ = (
        Index('idx_admin_id', 'admin_id'),
        Index('idx_status', 'status'),
    )

    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    admin_id = Column(BIGINT(unsigned=True), nullable=False, comment='申请人ID')
    username = Column(String(50), nullable=False, comment='申请人用户名(邀请码)')
    stat_date = Column(String(10), nullable=False, comment='统计日期')
    first_recharge_count = Column(INTEGER(unsigned=True), nullable=False, default=0, comment='首充人数')
    commission_per_person = Column(INTEGER(unsigned=True), nullable=False, default=0, comment='单人提成')
    total_commission = Column(BIGINT(unsigned=True), nullable=False, default=0, comment='提成总额')
    bank_name = Column(String(50), nullable=False, comment='银行名称')
    card_holder_name = Column(String(100), nullable=False, comment='持卡人')
    card_number = Column(String(50), nullable=False, comment='银行卡号')
    status = Column(SmallInteger, nullable=False, default=0, comment='状态: 0待审核 1已通过 2已拒绝')
    remark = Column(String(255), nullable=True, comment='审核备注')
    created_at = Column(TIMESTAMP, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = Column(TIMESTAMP, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
