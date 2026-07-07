#!/usr/bin/env python3
"""
🤝 QUIMERA REAL-TIME COLLABORATION SYSTEM
Sistema avançado de colaboração em tempo real para análise de código
"""

import asyncio
import json
import time
import uuid
from typing import Dict, List, Any, Optional, Set, Callable
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
import hashlib
import threading
import queue
from pathlib import Path

class EventType(Enum):
    """Tipos de eventos de colaboração"""
    USER_JOINED = "user_joined"
    USER_LEFT = "user_left"
    CODE_CHANGED = "code_changed"
    ANALYSIS_STARTED = "analysis_started"
    ANALYSIS_COMPLETED = "analysis_completed"
    COMMENT_ADDED = "comment_added"
    ISSUE_FLAGGED = "issue_flagged"
    ISSUE_RESOLVED = "issue_resolved"
    CURSOR_MOVED = "cursor_moved"
    SELECTION_CHANGED = "selection_changed"
    LIVE_EDIT = "live_edit"

@dataclass
class User:
    """Representação de um usuário"""
    id: str
    name: str
    email: str
    avatar_color: str
    role: str  # "developer", "reviewer", "admin"
    joined_at: datetime
    is_active: bool = True
    current_file: Optional[str] = None
    cursor_position: Optional[Dict[str, int]] = None

@dataclass
class CollaborationEvent:
    """Evento de colaboração"""
    id: str
    type: EventType
    user_id: str
    timestamp: datetime
    data: Dict[str, Any]
    session_id: str

@dataclass
class CodeComment:
    """Comentário no código"""
    id: str
    user_id: str
    file_path: str
    line_number: int
    content: str
    timestamp: datetime
    is_resolved: bool = False
    replies: List['CodeComment'] = None

@dataclass
class LiveEdit:
    """Edição em tempo real"""
    id: str
    user_id: str
    file_path: str
    operation: str  # "insert", "delete", "replace"
    position: Dict[str, int]  # {"line": 10, "column": 5}
    content: str
    timestamp: datetime

class SessionManager:
    """Gerenciador de sessões de colaboração"""

    def __init__(self):
        self.sessions: Dict[str, 'CollaborationSession'] = {}
        self.user_sessions: Dict[str, str] = {}  # user_id -> session_id

    def create_session(self, project_path: str, creator_id: str) -> str:
        """Cria uma nova sessão de colaboração"""
        session_id = str(uuid.uuid4())
        session = CollaborationSession(session_id, project_path, creator_id)
        self.sessions[session_id] = session
        return session_id

    def join_session(self, session_id: str, user: User) -> bool:
        """Usuário entra em uma sessão"""
        if session_id not in self.sessions:
            return False

        session = self.sessions[session_id]
        success = session.add_user(user)

        if success:
            self.user_sessions[user.id] = session_id

        return success

    def leave_session(self, user_id: str) -> bool:
        """Usuário sai da sessão"""
        if user_id not in self.user_sessions:
            return False

        session_id = self.user_sessions[user_id]
        session = self.sessions[session_id]
        session.remove_user(user_id)

        del self.user_sessions[user_id]

        # Remove sessão se vazia
        if not session.users:
            del self.sessions[session_id]

        return True

    def get_session(self, session_id: str) -> Optional['CollaborationSession']:
        """Obtém sessão por ID"""
        return self.sessions.get(session_id)

    def get_user_session(self, user_id: str) -> Optional['CollaborationSession']:
        """Obtém sessão do usuário"""
        session_id = self.user_sessions.get(user_id)
        if session_id:
            return self.sessions.get(session_id)
        return None

class CollaborationSession:
    """Sessão de colaboração em tempo real"""

    def __init__(self, session_id: str, project_path: str, creator_id: str):
        self.id = session_id
        self.project_path = project_path
        self.creator_id = creator_id
        self.created_at = datetime.now()

        # Usuários conectados
        self.users: Dict[str, User] = {}

        # Eventos e histórico
        self.events: List[CollaborationEvent] = []
        self.event_queue = queue.Queue()

        # Comentários e edições
        self.comments: Dict[str, List[CodeComment]] = {}  # file_path -> comments
        self.live_edits: List[LiveEdit] = []

        # Estado dos arquivos
        self.file_states: Dict[str, Dict[str, Any]] = {}
        self.file_locks: Dict[str, str] = {}  # file_path -> user_id

        # Callbacks para eventos
        self.event_callbacks: Dict[EventType, List[Callable]] = {}

        # Sistema de sincronização
        self.sync_lock = threading.Lock()
        self.last_sync = datetime.now()

    def add_user(self, user: User) -> bool:
        """Adiciona usuário à sessão"""
        with self.sync_lock:
            if user.id in self.users:
                return False

            self.users[user.id] = user

            # Criar evento de entrada
            event = CollaborationEvent(
                id=str(uuid.uuid4()),
                type=EventType.USER_JOINED,
                user_id=user.id,
                timestamp=datetime.now(),
                data={"user": asdict(user)},
                session_id=self.id
            )

            self.add_event(event)
            return True

    def remove_user(self, user_id: str) -> bool:
        """Remove usuário da sessão"""
        with self.sync_lock:
            if user_id not in self.users:
                return False

            user = self.users[user_id]
            del self.users[user_id]

            # Liberar locks de arquivos
            files_to_unlock = [f for f, u in self.file_locks.items() if u == user_id]
            for file_path in files_to_unlock:
                del self.file_locks[file_path]

            # Criar evento de saída
            event = CollaborationEvent(
                id=str(uuid.uuid4()),
                type=EventType.USER_LEFT,
                user_id=user_id,
                timestamp=datetime.now(),
                data={"user": asdict(user)},
                session_id=self.id
            )

            self.add_event(event)
            return True

    def add_event(self, event: CollaborationEvent):
        """Adiciona evento à sessão"""
        self.events.append(event)
        self.event_queue.put(event)

        # Executar callbacks
        if event.type in self.event_callbacks:
            for callback in self.event_callbacks[event.type]:
                try:
                    callback(event)
                except Exception as e:
                    print(f"Erro ao executar callback: {e}")

    def register_callback(self, event_type: EventType, callback: Callable):
        """Registra callback para tipo de evento"""
        if event_type not in self.event_callbacks:
            self.event_callbacks[event_type] = []
        self.event_callbacks[event_type].append(callback)

    def add_comment(self, user_id: str, file_path: str, line_number: int, content: str) -> str:
        """Adiciona comentário ao código"""
        comment_id = str(uuid.uuid4())
        comment = CodeComment(
            id=comment_id,
            user_id=user_id,
            file_path=file_path,
            line_number=line_number,
            content=content,
            timestamp=datetime.now()
        )

        if file_path not in self.comments:
            self.comments[file_path] = []

        self.comments[file_path].append(comment)

        # Criar evento
        event = CollaborationEvent(
            id=str(uuid.uuid4()),
            type=EventType.COMMENT_ADDED,
            user_id=user_id,
            timestamp=datetime.now(),
            data={
                "comment": asdict(comment)
            },
            session_id=self.id
        )

        self.add_event(event)
        return comment_id

    def resolve_comment(self, comment_id: str, user_id: str) -> bool:
        """Resolve um comentário"""
        for file_comments in self.comments.values():
            for comment in file_comments:
                if comment.id == comment_id:
                    comment.is_resolved = True

                    event = CollaborationEvent(
                        id=str(uuid.uuid4()),
                        type=EventType.ISSUE_RESOLVED,
                        user_id=user_id,
                        timestamp=datetime.now(),
                        data={"comment_id": comment_id},
                        session_id=self.id
                    )

                    self.add_event(event)
                    return True
        return False

    def live_edit(self, user_id: str, file_path: str, operation: str,
                  position: Dict[str, int], content: str) -> str:
        """Registra edição em tempo real"""
        edit_id = str(uuid.uuid4())
        edit = LiveEdit(
            id=edit_id,
            user_id=user_id,
            file_path=file_path,
            operation=operation,
            position=position,
            content=content,
            timestamp=datetime.now()
        )

        self.live_edits.append(edit)

        # Manter apenas últimas 1000 edições
        if len(self.live_edits) > 1000:
            self.live_edits = self.live_edits[-1000:]

        # Criar evento
        event = CollaborationEvent(
            id=str(uuid.uuid4()),
            type=EventType.LIVE_EDIT,
            user_id=user_id,
            timestamp=datetime.now(),
            data={
                "edit": asdict(edit)
            },
            session_id=self.id
        )

        self.add_event(event)
        return edit_id

    def update_cursor(self, user_id: str, file_path: str, position: Dict[str, int]):
        """Atualiza posição do cursor do usuário"""
        if user_id in self.users:
            self.users[user_id].current_file = file_path
            self.users[user_id].cursor_position = position

            event = CollaborationEvent(
                id=str(uuid.uuid4()),
                type=EventType.CURSOR_MOVED,
                user_id=user_id,
                timestamp=datetime.now(),
                data={
                    "file_path": file_path,
                    "position": position
                },
                session_id=self.id
            )

            self.add_event(event)

    def lock_file(self, user_id: str, file_path: str) -> bool:
        """Tenta obter lock exclusivo em arquivo"""
        with self.sync_lock:
            if file_path in self.file_locks:
                return self.file_locks[file_path] == user_id

            self.file_locks[file_path] = user_id
            return True

    def unlock_file(self, user_id: str, file_path: str) -> bool:
        """Libera lock em arquivo"""
        with self.sync_lock:
            if file_path in self.file_locks and self.file_locks[file_path] == user_id:
                del self.file_locks[file_path]
                return True
            return False

    def get_recent_events(self, limit: int = 50) -> List[CollaborationEvent]:
        """Obtém eventos recentes"""
        return self.events[-limit:]

    def get_file_comments(self, file_path: str) -> List[CodeComment]:
        """Obtém comentários de um arquivo"""
        return self.comments.get(file_path, [])

    def get_active_users(self) -> List[User]:
        """Obtém usuários ativos"""
        return [user for user in self.users.values() if user.is_active]

    def get_session_statistics(self) -> Dict[str, Any]:
        """Obtém estatísticas da sessão"""
        total_events = len(self.events)
        event_types = {}
        for event in self.events:
            event_type = event.type.value
            event_types[event_type] = event_types.get(event_type, 0) + 1

        total_comments = sum(len(comments) for comments in self.comments.values())
        resolved_comments = sum(
            len([c for c in comments if c.is_resolved])
            for comments in self.comments.values()
        )

        return {
            "session_id": self.id,
            "created_at": self.created_at.isoformat(),
            "duration_minutes": (datetime.now() - self.created_at).total_seconds() / 60,
            "total_users": len(self.users),
            "active_users": len(self.get_active_users()),
            "total_events": total_events,
            "event_breakdown": event_types,
            "total_comments": total_comments,
            "resolved_comments": resolved_comments,
            "total_live_edits": len(self.live_edits),
            "files_with_comments": len(self.comments),
            "locked_files": len(self.file_locks)
        }

class CollaborationAnalyzer:
    """Analisador de colaboração para métricas e insights"""

    def __init__(self, session: CollaborationSession):
        self.session = session

    def analyze_user_activity(self, user_id: str) -> Dict[str, Any]:
        """Analisa atividade de um usuário"""
        user_events = [e for e in self.session.events if e.user_id == user_id]

        if not user_events:
            return {"error": "Usuário não encontrado ou sem atividade"}

        activity_by_type = {}
        for event in user_events:
            event_type = event.type.value
            activity_by_type[event_type] = activity_by_type.get(event_type, 0) + 1

        user_comments = []
        for file_comments in self.session.comments.values():
            user_comments.extend([c for c in file_comments if c.user_id == user_id])

        user_edits = [e for e in self.session.live_edits if e.user_id == user_id]

        return {
            "user_id": user_id,
            "total_events": len(user_events),
            "activity_breakdown": activity_by_type,
            "comments_made": len(user_comments),
            "resolved_comments": len([c for c in user_comments if c.is_resolved]),
            "live_edits": len(user_edits),
            "most_active_file": self._get_most_active_file(user_events),
            "activity_timeline": self._get_activity_timeline(user_events)
        }

    def analyze_file_activity(self, file_path: str) -> Dict[str, Any]:
        """Analisa atividade em um arquivo específico"""
        file_events = [
            e for e in self.session.events
            if e.data.get('file_path') == file_path or
               (e.data.get('comment', {}).get('file_path') == file_path) or
               (e.data.get('edit', {}).get('file_path') == file_path)
        ]

        file_comments = self.session.comments.get(file_path, [])
        file_edits = [e for e in self.session.live_edits if e.file_path == file_path]

        users_involved = set()
        for event in file_events:
            users_involved.add(event.user_id)

        return {
            "file_path": file_path,
            "total_events": len(file_events),
            "users_involved": len(users_involved),
            "comments": len(file_comments),
            "unresolved_comments": len([c for c in file_comments if not c.is_resolved]),
            "live_edits": len(file_edits),
            "last_activity": max((e.timestamp for e in file_events), default=None),
            "most_active_user": self._get_most_active_user_for_file(file_events)
        }

    def generate_collaboration_insights(self) -> Dict[str, Any]:
        """Gera insights sobre a colaboração"""
        stats = self.session.get_session_statistics()

        # Análise de padrões de colaboração
        user_interactions = self._analyze_user_interactions()
        hot_files = self._identify_hot_files()
        collaboration_patterns = self._analyze_collaboration_patterns()

        return {
            "session_overview": stats,
            "user_interactions": user_interactions,
            "hot_files": hot_files,
            "collaboration_patterns": collaboration_patterns,
            "recommendations": self._generate_recommendations()
        }

    def _get_most_active_file(self, events: List[CollaborationEvent]) -> Optional[str]:
        """Identifica arquivo mais ativo para um usuário"""
        file_counts = {}
        for event in events:
            file_path = (
                event.data.get('file_path') or
                event.data.get('comment', {}).get('file_path') or
                event.data.get('edit', {}).get('file_path')
            )
            if file_path:
                file_counts[file_path] = file_counts.get(file_path, 0) + 1

        if file_counts:
            return max(file_counts, key=file_counts.get)
        return None

    def _get_activity_timeline(self, events: List[CollaborationEvent]) -> List[Dict[str, Any]]:
        """Cria timeline de atividade"""
        timeline = []
        for event in events[-10:]:  # Últimos 10 eventos
            timeline.append({
                "timestamp": event.timestamp.isoformat(),
                "type": event.type.value,
                "data": event.data
            })
        return timeline

    def _get_most_active_user_for_file(self, events: List[CollaborationEvent]) -> Optional[str]:
        """Identifica usuário mais ativo em um arquivo"""
        user_counts = {}
        for event in events:
            user_counts[event.user_id] = user_counts.get(event.user_id, 0) + 1

        if user_counts:
            return max(user_counts, key=user_counts.get)
        return None

    def _analyze_user_interactions(self) -> Dict[str, Any]:
        """Analisa interações entre usuários"""
        interactions = {}

        # Analisar respostas a comentários, edições colaborativas, etc.
        for file_comments in self.session.comments.values():
            for comment in file_comments:
                if comment.replies:
                    for reply in comment.replies:
                        if reply.user_id != comment.user_id:
                            key = f"{comment.user_id}-{reply.user_id}"
                            interactions[key] = interactions.get(key, 0) + 1

        return {
            "total_interactions": sum(interactions.values()),
            "interaction_pairs": interactions
        }

    def _identify_hot_files(self) -> List[Dict[str, Any]]:
        """Identifica arquivos com mais atividade"""
        file_activity = {}

        for event in self.session.events:
            file_path = (
                event.data.get('file_path') or
                event.data.get('comment', {}).get('file_path') or
                event.data.get('edit', {}).get('file_path')
            )
            if file_path:
                if file_path not in file_activity:
                    file_activity[file_path] = {"events": 0, "users": set()}
                file_activity[file_path]["events"] += 1
                file_activity[file_path]["users"].add(event.user_id)

        # Converter para lista ordenada
        hot_files = []
        for file_path, activity in file_activity.items():
            hot_files.append({
                "file_path": file_path,
                "total_events": activity["events"],
                "unique_users": len(activity["users"]),
                "activity_score": activity["events"] * len(activity["users"])
            })

        return sorted(hot_files, key=lambda x: x["activity_score"], reverse=True)[:10]

    def _analyze_collaboration_patterns(self) -> Dict[str, Any]:
        """Analisa padrões de colaboração"""
        patterns = {
            "peak_hours": self._get_peak_activity_hours(),
            "average_session_length": self._calculate_average_session_length(),
            "collaboration_density": self._calculate_collaboration_density()
        }

        return patterns

    def _get_peak_activity_hours(self) -> List[int]:
        """Identifica horários de pico de atividade"""
        hourly_activity = {}
        for event in self.session.events:
            hour = event.timestamp.hour
            hourly_activity[hour] = hourly_activity.get(hour, 0) + 1

        if not hourly_activity:
            return []

        max_activity = max(hourly_activity.values())
        peak_hours = [hour for hour, activity in hourly_activity.items()
                     if activity >= max_activity * 0.8]

        return sorted(peak_hours)

    def _calculate_average_session_length(self) -> float:
        """Calcula duração média de sessão por usuário"""
        user_sessions = {}

        for event in self.session.events:
            user_id = event.user_id
            if user_id not in user_sessions:
                user_sessions[user_id] = {"start": event.timestamp, "end": event.timestamp}
            else:
                user_sessions[user_id]["end"] = event.timestamp

        total_duration = 0
        for user_data in user_sessions.values():
            duration = (user_data["end"] - user_data["start"]).total_seconds() / 3600
            total_duration += duration

        return total_duration / len(user_sessions) if user_sessions else 0

    def _calculate_collaboration_density(self) -> float:
        """Calcula densidade de colaboração (eventos por usuário por hora)"""
        if not self.session.users or not self.session.events:
            return 0

        duration_hours = (datetime.now() - self.session.created_at).total_seconds() / 3600
        if duration_hours == 0:
            return 0

        return len(self.session.events) / (len(self.session.users) * duration_hours)

    def _generate_recommendations(self) -> List[str]:
        """Gera recomendações baseadas na análise"""
        recommendations = []

        stats = self.session.get_session_statistics()

        if stats["resolved_comments"] < stats["total_comments"] * 0.5:
            recommendations.append("💬 Considere revisar e resolver comentários pendentes")

        if stats["active_users"] < stats["total_users"] * 0.7:
            recommendations.append("👥 Alguns usuários parecem inativos - considere re-engajamento")

        if len(self.session.file_locks) > len(self.session.users) * 0.5:
            recommendations.append("🔒 Muitos arquivos travados - considere liberar locks desnecessários")

        if stats["total_live_edits"] > stats["total_comments"] * 3:
            recommendations.append("✏️ Muitas edições sem discussão - considere adicionar mais comentários")

        return recommendations

def demo_collaboration_system():
    """Demonstração do sistema de colaboração"""
    print("🤝 QUIMERA REAL-TIME COLLABORATION SYSTEM")
    print("=" * 50)

    # Criar gerenciador de sessões
    session_manager = SessionManager()

    # Criar usuários de exemplo
    users = [
        User(
            id="user1",
            name="Alice Developer",
            email="alice@example.com",
            avatar_color="#FF6B6B",
            role="developer",
            joined_at=datetime.now()
        ),
        User(
            id="user2",
            name="Bob Reviewer",
            email="bob@example.com",
            avatar_color="#4ECDC4",
            role="reviewer",
            joined_at=datetime.now()
        ),
        User(
            id="user3",
            name="Carol Admin",
            email="carol@example.com",
            avatar_color="#45B7D1",
            role="admin",
            joined_at=datetime.now()
        )
    ]

    # Criar sessão de colaboração
    session_id = session_manager.create_session("/projeto/exemplo", "user1")
    print(f"📝 Sessão criada: {session_id}")

    # Usuários entram na sessão
    for user in users:
        success = session_manager.join_session(session_id, user)
        print(f"👤 {user.name} {'entrou' if success else 'falhou ao entrar'} na sessão")

    session = session_manager.get_session(session_id)

    # Simular atividades de colaboração
    print("\n🔄 Simulando atividades...")

    # Adicionar comentários
    comment_id1 = session.add_comment("user2", "main.py", 15, "Este método está muito complexo")
    comment_id2 = session.add_comment("user1", "utils.py", 8, "Precisamos adicionar validação aqui")

    # Edições em tempo real
    session.live_edit("user1", "main.py", "insert", {"line": 16, "column": 0}, "    // Refactor: simplify")
    session.live_edit("user3", "utils.py", "replace", {"line": 8, "column": 4}, "def validate_input(data):")

    # Atualizar cursores
    session.update_cursor("user1", "main.py", {"line": 16, "column": 20})
    session.update_cursor("user2", "main.py", {"line": 15, "column": 0})

    # Resolver comentário
    session.resolve_comment(comment_id1, "user1")

    # Gerar análise
    analyzer = CollaborationAnalyzer(session)

    print("\n📊 ESTATÍSTICAS DA SESSÃO")
    print("-" * 30)
    stats = session.get_session_statistics()
    for key, value in stats.items():
        if key != "event_breakdown":
            print(f"{key}: {value}")

    print(f"\nTipos de eventos:")
    for event_type, count in stats["event_breakdown"].items():
        print(f"  {event_type}: {count}")

    print("\n👤 ANÁLISE DE USUÁRIOS")
    print("-" * 30)
    for user in users:
        activity = analyzer.analyze_user_activity(user.id)
        print(f"\n{user.name}:")
        print(f"  Total de eventos: {activity.get('total_events', 0)}")
        print(f"  Comentários: {activity.get('comments_made', 0)}")
        print(f"  Edições: {activity.get('live_edits', 0)}")
        if activity.get('most_active_file'):
            print(f"  Arquivo mais ativo: {activity['most_active_file']}")

    print("\n📁 ARQUIVOS MAIS ATIVOS")
    print("-" * 30)
    hot_files = analyzer._identify_hot_files()
    for file_info in hot_files[:5]:
        print(f"{file_info['file_path']}: {file_info['total_events']} eventos, {file_info['unique_users']} usuários")

    print("\n💡 INSIGHTS E RECOMENDAÇÕES")
    print("-" * 30)
    insights = analyzer.generate_collaboration_insights()
    for recommendation in insights["recommendations"]:
        print(f"  {recommendation}")

    print(f"\n🔥 Densidade de colaboração: {insights['collaboration_patterns']['collaboration_density']:.2f} eventos/usuário/hora")

    # Eventos recentes
    print("\n📋 EVENTOS RECENTES")
    print("-" * 30)
    recent_events = session.get_recent_events(10)
    for event in recent_events:
        user_name = next((u.name for u in users if u.id == event.user_id), "Usuário desconhecido")
        print(f"  {event.timestamp.strftime('%H:%M:%S')} - {user_name}: {event.type.value}")

    print("\n✅ Demonstração concluída!")

if __name__ == "__main__":
    demo_collaboration_system()