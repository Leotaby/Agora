"""
models/agent_message.py

Agent-to-agent messaging system.

Messages propagate through the social network based on agent connections.
A message can target a single agent (receiver_id) or all connected agents
("broadcast"). Propagation reach depends on sender influence and receiver
trust/literacy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import uuid


class MessageType(str, Enum):
    TRADE              = "trade"               # "I just bought USD"
    ORDER              = "order"               # institutional order flow
    NEWS               = "news"                # forwarded news item
    RUMOR              = "rumor"               # unverified information
    POLICY_ANNOUNCEMENT = "policy_announcement" # central bank / government
    PERSONAL           = "personal"            # family / neighbor chat


# How much each message type influences beliefs (base weight before literacy filter)
MESSAGE_INFLUENCE_WEIGHT: dict[MessageType, float] = {
    MessageType.POLICY_ANNOUNCEMENT: 0.8,
    MessageType.NEWS:                0.5,
    MessageType.ORDER:               0.6,
    MessageType.TRADE:               0.4,
    MessageType.RUMOR:               0.2,
    MessageType.PERSONAL:            0.3,
}


@dataclass
class AgentMessage:
    """A single message sent between agents."""

    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender_id: str = ""
    receiver_id: str = ""          # specific agent_id or "broadcast"
    content: str = ""
    message_type: MessageType = MessageType.PERSONAL
    tick: int = 0
    simulation_date: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Optional structured payload (e.g. price data, policy rate)
    metadata: dict = field(default_factory=dict)

    # Propagation tracking
    hops: int = 0                  # how many relays from original sender
    original_sender_id: str = ""   # tracks origin through relay chain

    def to_dict(self) -> dict:
        return {
            "message_id": self.message_id,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "content": self.content,
            "message_type": self.message_type.value,
            "tick": self.tick,
            "simulation_date": self.simulation_date,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "hops": self.hops,
            "original_sender_id": self.original_sender_id or self.sender_id,
        }
