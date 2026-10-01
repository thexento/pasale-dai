import json
import sqlite3
from pathlib import Path
from typing import Optional, List
from app.config import settings
from app.memory.schemas import UserMemoryState, ChatMessage, OrderContext
from app.database.repositories import ConversationRepository, CustomerRepository


class MemoryManager:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.conv_repo = ConversationRepository(conn)
        self.customer_repo = CustomerRepository(conn)
        self.memory_dir = settings.MEMORY_DIR
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def _get_memory_path(self, discord_user_id: str) -> Path:
        return self.memory_dir / f"{discord_user_id}.json"

    def load_memory(self, discord_user_id: str, username: str = "") -> UserMemoryState:
        """Loads persistent JSON memory for a Discord customer, or initializes if missing."""
        path = self._get_memory_path(discord_user_id)
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return UserMemoryState(**data)
            except Exception:
                pass

        # Default state
        state = UserMemoryState(user_id=str(discord_user_id), username=username)
        self.save_memory(state)
        return state

    def save_memory(self, state: UserMemoryState) -> None:
        """Persists the memory state to disk."""
        path = self._get_memory_path(state.user_id)
        path.write_text(json.dumps(state.model_dump(), indent=2, ensure_ascii=False), encoding="utf-8")

    def record_turn(
        self,
        discord_user_id: str,
        user_message: str,
        assistant_message: str,
        username: str = ""
    ) -> UserMemoryState:
        """Appends conversation turn to both the SQLite table and the isolated JSON memory."""
        # 1. Update SQLite
        customer = self.customer_repo.get_or_create(discord_user_id, username)
        self.conv_repo.add_message(customer.id, "user", user_message)
        self.conv_repo.add_message(customer.id, "assistant", assistant_message)

        # 2. Update JSON memory
        memory = self.load_memory(discord_user_id, username)
        memory.recent_messages.append(ChatMessage(role="user", content=user_message))
        memory.recent_messages.append(ChatMessage(role="assistant", content=assistant_message))

        # 3. Compress if message count exceeds threshold
        if len(memory.recent_messages) > settings.MEMORY_MESSAGE_LIMIT:
            self._compress_memory(memory)

        self.save_memory(memory)
        return memory

    def _compress_memory(self, memory: UserMemoryState) -> None:
        """Compresses older messages into a rolling compact summary to avoid context window bloat."""
        split_index = len(memory.recent_messages) - 6
        to_summarize = memory.recent_messages[:split_index]
        keep_recent = memory.recent_messages[split_index:]

        dialogue_text = " | ".join([f"{m.role}: {m.content}" for m in to_summarize])
        new_summary_part = f"Previous interaction: {dialogue_text}"

        if memory.summary:
            memory.summary = f"{memory.summary} -- {new_summary_part}"[-800:]
        else:
            memory.summary = new_summary_part[-800:]

        memory.recent_messages = keep_recent

    def update_order_context(
        self,
        discord_user_id: str,
        order_number: Optional[str] = None,
        product_id: Optional[str] = None,
        quantity: Optional[int] = None,
        amount: Optional[float] = None,
        status: Optional[str] = None,
        payment_verified: Optional[bool] = None,
        details_collected: Optional[bool] = None
    ) -> None:
        memory = self.load_memory(discord_user_id)
        ctx = memory.current_order_context
        if order_number is not None:
            ctx.order_number = order_number
        if product_id is not None:
            ctx.product_id = product_id
        if quantity is not None:
            ctx.quantity = quantity
        if amount is not None:
            ctx.amount = amount
        if status is not None:
            ctx.status = status
        if payment_verified is not None:
            ctx.payment_verified = payment_verified
        if details_collected is not None:
            ctx.details_collected = details_collected
        self.save_memory(memory)