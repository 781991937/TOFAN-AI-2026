"""Owner/Admin APIs for inspecting and governing agent memory."""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents.memory import (
    AgentConversation,
    AgentMemoryItem,
    AgentMemoryPermission,
    AgentMessageRecord,
    active_memory_items,
    deactivate_memory_item,
    update_memory_item,
)
from app.agents.models import Agent
from app.auth.authorization import require_owner_or_admin
from app.auth.dependencies import get_current_user, get_db
from app.db.models import AuditLog, User

router = APIRouter(prefix="/admin/agent", tags=["admin-agent-memory"])


class MemoryPermissionRequest(BaseModel):
    agent_id: str = Field(min_length=1)
    can_read: bool = False
    can_write: bool = False
    can_delete: bool = False


def _audit(db: Session, actor_id: str, action: str, resource_id: str, details: dict) -> None:
    db.add(AuditLog(
        user_id=actor_id,
        action=action,
        resource_type="agent_memory",
        resource_id=resource_id,
        details=json.dumps(details, ensure_ascii=False),
    ))


@router.get("/conversations")
def list_conversations(db: Session = Depends(get_db), _: list = Depends(require_owner_or_admin)):
    rows = db.query(AgentConversation).order_by(AgentConversation.updated_at.desc()).limit(100).all()
    return {"conversations": [
        {"id": row.id, "agent_id": row.agent_id, "user_id": row.user_id, "title": row.title,
         "created_at": row.created_at, "updated_at": row.updated_at}
        for row in rows
    ]}


@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: str, db: Session = Depends(get_db), _: list = Depends(require_owner_or_admin)
):
    conversation = db.get(AgentConversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    messages = db.query(AgentMessageRecord).filter(
        AgentMessageRecord.conversation_id == conversation_id
    ).order_by(AgentMessageRecord.sequence.asc()).all()
    return {
        "conversation": {
            "id": conversation.id, "agent_id": conversation.agent_id, "user_id": conversation.user_id,
            "title": conversation.title, "created_at": conversation.created_at, "updated_at": conversation.updated_at,
        },
        "messages": [
            {"id": m.id, "role": m.role, "content": m.content, "sequence": m.sequence, "created_at": m.created_at}
            for m in messages
        ],
    }


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: str, db: Session = Depends(get_db), actor: User = Depends(get_current_user),
    _: list = Depends(require_owner_or_admin)
):
    conversation = db.get(AgentConversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    db.query(AgentMessageRecord).filter(
        AgentMessageRecord.conversation_id == conversation_id
    ).delete(synchronize_session=False)
    db.query(AgentMemoryItem).filter(
        AgentMemoryItem.conversation_id == conversation_id
    ).update({"active": False}, synchronize_session=False)
    db.delete(conversation)
    _audit(db, actor.id, "agent.conversation.deleted", conversation_id, {})
    db.commit()
    return {"deleted": True, "conversation_id": conversation_id, "actor_user_id": actor.id}


@router.get("/conversations/{conversation_id}/memory")
def list_memory_items(
    conversation_id: str, db: Session = Depends(get_db), _: list = Depends(require_owner_or_admin)
):
    conversation = db.get(AgentConversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {"memory_items": [
        {
            "id": item.id, "memory_type": item.memory_type, "memory_scope": item.memory_scope,
            "owner_agent_id": item.owner_agent_id, "content": item.content, "confidence": item.confidence,
            "source_message_sequence": item.source_message_sequence, "active": item.active,
            "created_at": item.created_at, "updated_at": item.updated_at,
        }
        for item in active_memory_items(db, conversation_id, conversation.agent_id)
    ]}


@router.patch("/memory/{item_id}")
def edit_memory_item(
    item_id: str, content: str, confidence: float | None = None,
    db: Session = Depends(get_db), actor: User = Depends(get_current_user),
    _: list = Depends(require_owner_or_admin),
):
    item = db.get(AgentMemoryItem, item_id)
    if not item or not item.active:
        raise HTTPException(status_code=404, detail="Memory item not found.")
    item.content = content.strip()
    if confidence is not None:
        item.confidence = min(max(confidence, 0.0), 1.0)
    _audit(db, actor.id, "agent.memory.updated", item.id, {"confidence": item.confidence})
    db.commit()
    return {"updated": True, "memory_item_id": item.id}


@router.delete("/memory/{item_id}")
def remove_memory_item(
    item_id: str, db: Session = Depends(get_db), actor: User = Depends(get_current_user),
    _: list = Depends(require_owner_or_admin)
):
    item = db.get(AgentMemoryItem, item_id)
    if not item or not item.active:
        raise HTTPException(status_code=404, detail="Memory item not found.")
    item.active = False
    _audit(db, actor.id, "agent.memory.deactivated", item.id, {})
    db.commit()
    return {"deleted": True, "memory_item_id": item_id}


@router.get("/memory/{item_id}/permissions")
def list_memory_permissions(
    item_id: str, db: Session = Depends(get_db), _: list = Depends(require_owner_or_admin)
):
    item = db.get(AgentMemoryItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Memory item not found.")
    rows = db.query(AgentMemoryPermission).filter(
        AgentMemoryPermission.memory_item_id == item_id
    ).all()
    return {"permissions": [
        {"id": row.id, "agent_id": row.agent_id, "can_read": row.can_read,
         "can_write": row.can_write, "can_delete": row.can_delete}
        for row in rows
    ]}


@router.put("/memory/{item_id}/permissions")
def set_memory_permission(
    item_id: str, payload: MemoryPermissionRequest,
    db: Session = Depends(get_db), actor: User = Depends(get_current_user),
    _: list = Depends(require_owner_or_admin)
):
    item = db.get(AgentMemoryItem, item_id)
    agent = db.get(Agent, payload.agent_id)
    if not item or not item.active:
        raise HTTPException(status_code=404, detail="Memory item not found.")
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found.")
    if item.memory_scope not in {"user", "system"}:
        raise HTTPException(
            status_code=400,
            detail="Only user/system memory can be shared between agents.",
        )

    permission = db.query(AgentMemoryPermission).filter(
        AgentMemoryPermission.memory_item_id == item_id,
        AgentMemoryPermission.agent_id == payload.agent_id,
    ).first()
    if permission is None:
        permission = AgentMemoryPermission(
            memory_item_id=item_id, agent_id=payload.agent_id,
            can_read=payload.can_read, can_write=payload.can_write,
            can_delete=payload.can_delete,
        )
        db.add(permission)
    else:
        permission.can_read = payload.can_read
        permission.can_write = payload.can_write
        permission.can_delete = payload.can_delete

    _audit(db, actor.id, "agent.memory.permission.changed", item_id, {
        "agent_id": agent.id,
        "can_read": payload.can_read,
        "can_write": payload.can_write,
        "can_delete": payload.can_delete,
    })
    db.commit()
    return {"updated": True, "memory_item_id": item_id, "agent_id": agent.id}


@router.delete("/memory/{item_id}/permissions/{agent_id}")
def revoke_memory_permission(
    item_id: str, agent_id: str, db: Session = Depends(get_db),
    actor: User = Depends(get_current_user), _: list = Depends(require_owner_or_admin)
):
    permission = db.query(AgentMemoryPermission).filter(
        AgentMemoryPermission.memory_item_id == item_id,
        AgentMemoryPermission.agent_id == agent_id,
    ).first()
    if not permission:
        raise HTTPException(status_code=404, detail="Memory permission not found.")
    db.delete(permission)
    _audit(db, actor.id, "agent.memory.permission.revoked", item_id, {"agent_id": agent_id})
    db.commit()
    return {"revoked": True, "memory_item_id": item_id, "agent_id": agent_id}
