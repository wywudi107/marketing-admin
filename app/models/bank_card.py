"""
电销人员银行卡模型
"""
from sqlalchemy import Column, String, TIMESTAMP, text, Index
from sqlalchemy.dialects.mysql import BIGINT

from app.database.mysql import Base


class BankCard(Base):
    __tablename__ = 'bank_cards'
    __table_args__ = (
        Index('idx_admin_id', 'admin_id'),
    )

    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    admin_id = Column(BIGINT(unsigned=True), unique=True, nullable=False, comment='管理员ID')
    card_holder_name = Column(String(100), nullable=False, comment='持卡人姓名')
    card_number = Column(String(50), nullable=False, comment='银行卡号')
    bank_name = Column(String(50), nullable=False, comment='银行名称')
    created_at = Column(TIMESTAMP, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = Column(TIMESTAMP, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
