"""
首充列表模型
"""
from sqlalchemy import Column, String, TIMESTAMP, text, Index
from sqlalchemy.dialects.mysql import BIGINT, INTEGER

from app.database.mysql import Base


class FirstRecharge(Base):
    __tablename__ = 'first_recharges'
    __table_args__ = (
        Index('idx_player_id', 'player_id'),
        Index('idx_recharge_time', 'recharge_time'),
    )

    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    player_id = Column(String(50), nullable=False, comment='玩家ID')
    order_no = Column(String(50), nullable=False, comment='订单号')
    channel = Column(String(50), nullable=True, comment='渠道')
    nickname = Column(String(100), nullable=True, comment='昵称')
    amount = Column(INTEGER(unsigned=True), nullable=False, default=0, comment='充值金额')
    pay_method = Column(String(50), nullable=True, comment='充值方式')
    recharge_time = Column(TIMESTAMP, nullable=True, comment='充值时间')
    created_at = Column(TIMESTAMP, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
