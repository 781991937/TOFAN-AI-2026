"""Owner/Admin APIs for inspecting and managing Main Agent conversations."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.memory import (
    AgentConversation, AgentMemoryItem, AgentMessageRecord,
    active_memory_items, deactivate_memory_item, update_memory_item,
)
from app.auth.authorization import require_owner_or_admin
from app.auth.dependencies import get_current_user, get_db
from app.db.models import User

router = APIRouter(prefix="/admin/agent", tags=["admin-agent-memory"])


@router.get("/conversations")
def list_conversations(
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    rows = db.query(AgentConversation).order_by(AgentConversation.updated_at.desc()).limit(100).all()
    return {
        "conversations": [
            {
                "id": row.id,
                "agent_id": row.agent_id,
                "user_id": row.user_id,
                "title": row.title,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
            for row in rows
        ]
    }


@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    conversation = db.get(AgentConversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    messages = (
        db.query(AgentMessageRecord)
        .filter(AgentMessageRecord.conversation_id == conversation_id)
        .order_by(AgentMessageRecord.sequence.asc())
        .all()
    )
    return {
        "conversation": {
            "id": conversation.id,
            "agent_id": conversation.agent_id,
            "user_id": conversation.user_id,
            "title": conversation.title,
            "created_at": conversation.created_at,
            "updated_at": conversation.updated_at,
        },
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "sequence": m.sequence,
                "created_at": m.created_at,
            }
            for m in messages
        ],
    }


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
    _: list = Depends(require_owner_or_admin),
):
    conversation = db.get(AgentConversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    db.query(AgentMessageRecord).filter(
        AgentMessageRecord.conversation_id == conversation_id
    ).delete(synchronize_session=False)
    db.delete(conversation)
    db.commit()

    return {"deleted": True, "conversation_id": conversation_id, "actor_user_id": actor.id}


@router.get("/conversations/{conversation_id}/memory")
def list_memory_items(
    conversation_id: str,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    conversation = db.get(AgentConversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {
        "memory_items": [
            {
                "id": item.id,
                "memory_type": item.memory_type,
                "content": item.content,
                "confidence": item.confidence,
                "source_message_sequence": item.source_message_sequence,
                "active": item.active,
                "created_at": item.created_at,
                "updated_at": item.updated_at,
            }
            for item in active_memory_items(db, conversation_id, conversation.agent_id)
        ]
    }


@router.patch("/memory/{item_id}")
def edit_memory_item(
    item_id: str,
    content: str,
    confidence: float | None = None,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
    _: list = Depends(require_owner_or_admin),
):
    item = update_memory_item(db, item_id, actor.id, content, confidence)
    if not item:
        raise HTTPException(status_code=404, detail="Memory item not found.")
    db.commit()
    return {"updated": True, "memory_item_id": item.id}


@router.delete("/memory/{item_id}")
def remove_memory_item(
    item_id: str,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
    _: list = Depends(require_owner_or_admin),
):
    if not deactivate_memory_item(db, item_id, actor.id):
        raise HTTPException(status_code=404, detail="Memory item not found.")
    db.commit()
    return {"deleted": True, "memory_item_id": item_id}
