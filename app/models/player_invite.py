"""
玩家邀请码关联表模型
"""
from sqlalchemy import Column, String, TIMESTAMP, text, Index
from sqlalchemy.dialects.mysql import BIGINT

from app.database.mysql import Base


class PlayerInvite(Base):
    __tablename__ = 'player_invites'
    __table_args__ = (
        Index('idx_player_id', 'player_id'),
        Index('idx_invite_code', 'invite_code'),
    )

    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    player_id = Column(String(50), unique=True, nullable=False, comment='玩家ID')
    invite_code = Column(String(50), nullable=False, comment='邀请码')
    register_time = Column(TIMESTAMP, nullable=True, comment='注册时间')
    created_at = Column(TIMESTAMP, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
