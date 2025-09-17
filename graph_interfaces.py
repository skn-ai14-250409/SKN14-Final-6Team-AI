from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

@dataclass
class ChatState:
    user_id: str
    session_id: Optional[str] = None
    query: Optional[str] = None
    response: Optional[str] = None
    turn_id: int = 0
    attachments: List[str] = field(default_factory=list)
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    user_context: Dict[str, Any] = field(default_factory=dict)
    image: Optional[str] = None
    vision_mode: bool = False
    
    route: Dict[str, Any] = field(default_factory=dict)
    rewrite: Dict[str, Any] = field(default_factory=dict)
    slots: Dict[str, Any] = field(default_factory=dict)
    search: Dict[str, Any] = field(default_factory=dict)
    recipe: Dict[str, Any] = field(default_factory=dict)
    cart: Dict[str, Any] = field(default_factory=dict)
    checkout: Dict[str, Any] = field(default_factory=dict)
    order: Dict[str, Any] = field(default_factory=dict)
    cs: Dict[str, Any] = field(default_factory=dict)
    handoff: Dict[str, Any] = field(default_factory=dict)
    end: Dict[str, Any] = field(default_factory=dict)

    meta: Dict[str, Any] = field(default_factory=dict)
    
    def update(self, data: Dict[str, Any]):
        for key, value in data.items():
            if hasattr(self, key) and value:
                if isinstance(getattr(self, key), dict):
                    getattr(self, key).update(value)
                else:
                    setattr(self, key, value)