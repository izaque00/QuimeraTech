#!/usr/bin/env python3
"""
🎮 QUIMERA ADVANCED GAMIFICATION SYSTEM
Sistema avançado de gamificação para análise de código
"""

import json
import math
import random
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Any, Optional, Set, Tuple
from pathlib import Path
import threading

class AchievementType(Enum):
    """Tipos de conquistas"""
    CODE_QUALITY = "code_quality"
    PERFORMANCE = "performance"
    SECURITY = "security"
    COLLABORATION = "collaboration"
    LEARNING = "learning"
    STREAK = "streak"
    MILESTONE = "milestone"
    SPECIAL = "special"

class BadgeRarity(Enum):
    """Raridade dos badges"""
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"
    MYTHIC = "mythic"

@dataclass
class Achievement:
    """Conquista do sistema"""
    id: str
    name: str
    description: str
    type: AchievementType
    rarity: BadgeRarity
    points: int
    requirements: Dict[str, Any]
    icon: str
    unlock_message: str
    is_hidden: bool = False
    series: Optional[str] = None

@dataclass
class Player:
    """Jogador/Desenvolvedor"""
    id: str
    username: str
    email: str
    level: int
    experience: int
    total_points: int
    achievements: List[str]
    badges: List[str]
    streaks: Dict[str, int]
    stats: Dict[str, Any]
    preferences: Dict[str, Any]
    joined_date: datetime
    last_activity: datetime

@dataclass
class Challenge:
    """Desafio gamificado"""
    id: str
    name: str
    description: str
    type: str
    difficulty: str  # "easy", "medium", "hard", "expert"
    points_reward: int
    time_limit: Optional[timedelta]
    requirements: Dict[str, Any]
    start_date: datetime
    end_date: Optional[datetime]
    participants: List[str]
    is_active: bool

@dataclass
class QuestLine:
    """Linha de missões"""
    id: str
    name: str
    description: str
    chapters: List[str]
    current_chapter: int
    completion_reward: Achievement
    is_completed: bool

class GamificationEngine:
    """Motor principal de gamificação"""

    def __init__(self):
        self.players: Dict[str, Player] = {}
        self.achievements: Dict[str, Achievement] = {}
        self.challenges: Dict[str, Challenge] = {}
        self.quest_lines: Dict[str, QuestLine] = {}
        self.leaderboards: Dict[str, List[Dict[str, Any]]] = {}

        # Sistema de eventos
        self.event_handlers: Dict[str, List[callable]] = {}

        # Configurações
        self.level_thresholds = self._calculate_level_thresholds()
        self.point_multipliers = {
            BadgeRarity.COMMON: 1.0,
            BadgeRarity.UNCOMMON: 1.5,
            BadgeRarity.RARE: 2.0,
            BadgeRarity.EPIC: 3.0,
            BadgeRarity.LEGENDARY: 5.0,
            BadgeRarity.MYTHIC: 10.0
        }

        # Inicializar sistema
        self._initialize_achievements()
        self._initialize_challenges()
        self._initialize_quest_lines()

    def _calculate_level_thresholds(self) -> List[int]:
        """Calcula thresholds de experiência para cada nível"""
        thresholds = [0]  # Nível 0

        for level in range(1, 101):  # Até nível 100
            # Fórmula exponencial crescente
            threshold = int(100 * (level ** 1.5) + 50 * level)
            thresholds.append(threshold)

        return thresholds

    def _initialize_achievements(self):
        """Inicializa conquistas do sistema"""
        achievements = [
            # Qualidade de código
            Achievement(
                id="first_analysis",
                name="Primeira Análise",
                description="Execute sua primeira análise de código",
                type=AchievementType.CODE_QUALITY,
                rarity=BadgeRarity.COMMON,
                points=10,
                requirements={"analyses_count": 1},
                icon="🔍",
                unlock_message="Bem-vindo ao mundo da análise de código!"
            ),
            Achievement(
                id="code_perfectionist",
                name="Perfeccionista",
                description="Resolva 100 issues de qualidade de código",
                type=AchievementType.CODE_QUALITY,
                rarity=BadgeRarity.RARE,
                points=500,
                requirements={"issues_resolved": 100},
                icon="✨",
                unlock_message="Sua dedicação à qualidade é inspiradora!"
            ),
            Achievement(
                id="zero_issues_master",
                name="Mestre Zero Issues",
                description="Tenha 10 arquivos com zero issues",
                type=AchievementType.CODE_QUALITY,
                rarity=BadgeRarity.EPIC,
                points=1000,
                requirements={"zero_issue_files": 10},
                icon="🏆",
                unlock_message="Código perfeito é sua especialidade!"
            ),

            # Performance
            Achievement(
                id="speed_demon",
                name="Demônio da Velocidade",
                description="Otimize 50 problemas de performance",
                type=AchievementType.PERFORMANCE,
                rarity=BadgeRarity.UNCOMMON,
                points=300,
                requirements={"performance_optimizations": 50},
                icon="⚡",
                unlock_message="Velocidade é seu segundo nome!"
            ),
            Achievement(
                id="algorithm_wizard",
                name="Mago dos Algoritmos",
                description="Refatore 20 algoritmos complexos",
                type=AchievementType.PERFORMANCE,
                rarity=BadgeRarity.LEGENDARY,
                points=2000,
                requirements={"algorithm_refactors": 20},
                icon="🧙‍♂️",
                unlock_message="Você domina a arte da otimização!"
            ),

            # Segurança
            Achievement(
                id="security_guardian",
                name="Guardião da Segurança",
                description="Resolva 25 vulnerabilidades de segurança",
                type=AchievementType.SECURITY,
                rarity=BadgeRarity.RARE,
                points=750,
                requirements={"security_fixes": 25},
                icon="🛡️",
                unlock_message="O código está mais seguro com você!"
            ),
            Achievement(
                id="hacker_hunter",
                name="Caçador de Hackers",
                description="Identifique 100 potenciais vulnerabilidades",
                type=AchievementType.SECURITY,
                rarity=BadgeRarity.EPIC,
                points=1500,
                requirements={"vulnerabilities_found": 100},
                icon="🎯",
                unlock_message="Nenhuma vulnerabilidade escapa de você!"
            ),

            # Colaboração
            Achievement(
                id="team_player",
                name="Jogador de Equipe",
                description="Participe de 10 sessões colaborativas",
                type=AchievementType.COLLABORATION,
                rarity=BadgeRarity.UNCOMMON,
                points=200,
                requirements={"collaboration_sessions": 10},
                icon="🤝",
                unlock_message="Trabalho em equipe faz a diferença!"
            ),
            Achievement(
                id="mentor_master",
                name="Mestre Mentor",
                description="Ajude 50 outros desenvolvedores",
                type=AchievementType.COLLABORATION,
                rarity=BadgeRarity.LEGENDARY,
                points=2500,
                requirements={"mentorship_actions": 50},
                icon="👨‍🏫",
                unlock_message="Você está formando a próxima geração!"
            ),

            # Streaks
            Achievement(
                id="consistency_king",
                name="Rei da Consistência",
                description="Mantenha um streak de 30 dias",
                type=AchievementType.STREAK,
                rarity=BadgeRarity.EPIC,
                points=1000,
                requirements={"daily_streak": 30},
                icon="🔥",
                unlock_message="Consistência é a chave do sucesso!"
            ),
            Achievement(
                id="unstoppable_force",
                name="Força Imparável",
                description="Mantenha um streak de 100 dias",
                type=AchievementType.STREAK,
                rarity=BadgeRarity.MYTHIC,
                points=5000,
                requirements={"daily_streak": 100},
                icon="💫",
                unlock_message="Você é uma força da natureza!"
            ),

            # Especiais
            Achievement(
                id="night_owl",
                name="Coruja Noturna",
                description="Faça análises entre 22h e 6h por 7 dias",
                type=AchievementType.SPECIAL,
                rarity=BadgeRarity.RARE,
                points=400,
                requirements={"night_analyses": 7},
                icon="🦉",
                unlock_message="A madrugada é seu horário nobre!"
            ),
            Achievement(
                id="language_polyglot",
                name="Poliglota das Linguagens",
                description="Analise código em 10 linguagens diferentes",
                type=AchievementType.LEARNING,
                rarity=BadgeRarity.LEGENDARY,
                points=3000,
                requirements={"languages_analyzed": 10},
                icon="🌍",
                unlock_message="Você fala a linguagem universal do código!"
            )
        ]

        for achievement in achievements:
            self.achievements[achievement.id] = achievement

    def _initialize_challenges(self):
        """Inicializa desafios do sistema"""
        challenges = [
            Challenge(
                id="weekly_quality_sprint",
                name="Sprint de Qualidade Semanal",
                description="Resolva 50 issues de qualidade em uma semana",
                type="quality",
                difficulty="medium",
                points_reward=500,
                time_limit=timedelta(days=7),
                requirements={"issues_to_resolve": 50},
                start_date=datetime.now(),
                end_date=datetime.now() + timedelta(days=7),
                participants=[],
                is_active=True
            ),
            Challenge(
                id="security_weekend",
                name="Final de Semana de Segurança",
                description="Encontre e corrija 10 vulnerabilidades em 2 dias",
                type="security",
                difficulty="hard",
                points_reward=1000,
                time_limit=timedelta(days=2),
                requirements={"vulnerabilities_to_fix": 10},
                start_date=datetime.now(),
                end_date=datetime.now() + timedelta(days=2),
                participants=[],
                is_active=True
            ),
            Challenge(
                id="performance_marathon",
                name="Maratona de Performance",
                description="Otimize 100 problemas de performance em um mês",
                type="performance",
                difficulty="expert",
                points_reward=2000,
                time_limit=timedelta(days=30),
                requirements={"optimizations_needed": 100},
                start_date=datetime.now(),
                end_date=datetime.now() + timedelta(days=30),
                participants=[],
                is_active=True
            )
        ]

        for challenge in challenges:
            self.challenges[challenge.id] = challenge

    def _initialize_quest_lines(self):
        """Inicializa linhas de missões"""
        quest_lines = [
            QuestLine(
                id="code_master_journey",
                name="Jornada do Mestre do Código",
                description="Uma jornada épica através dos domínios da qualidade de código",
                chapters=[
                    "Primeiros Passos na Análise",
                    "Dominando a Qualidade",
                    "Mestre da Refatoração",
                    "Guardião da Excelência"
                ],
                current_chapter=0,
                completion_reward=Achievement(
                    id="code_master",
                    name="Mestre do Código",
                    description="Complete a Jornada do Mestre do Código",
                    type=AchievementType.MILESTONE,
                    rarity=BadgeRarity.MYTHIC,
                    points=10000,
                    requirements={},
                    icon="👑",
                    unlock_message="Você alcançou a maestria suprema!"
                ),
                is_completed=False
            )
        ]

        for quest in quest_lines:
            self.quest_lines[quest.id] = quest

    def register_player(self, username: str, email: str) -> str:
        """Registra novo jogador"""
        player_id = str(uuid.uuid4())

        player = Player(
            id=player_id,
            username=username,
            email=email,
            level=1,
            experience=0,
            total_points=0,
            achievements=[],
            badges=[],
            streaks={"daily": 0, "weekly": 0},
            stats={
                "analyses_count": 0,
                "issues_resolved": 0,
                "vulnerabilities_found": 0,
                "performance_optimizations": 0,
                "collaboration_sessions": 0,
                "total_files_analyzed": 0,
                "languages_analyzed": set()
            },
            preferences={
                "notifications": True,
                "public_profile": True,
                "challenge_invites": True
            },
            joined_date=datetime.now(),
            last_activity=datetime.now()
        )

        self.players[player_id] = player

        # Trigger primeiro achievement
        self._trigger_event("player_registered", {"player_id": player_id})

        return player_id

    def award_points(self, player_id: str, points: int, reason: str = "") -> bool:
        """Concede pontos ao jogador"""
        if player_id not in self.players:
            return False

        player = self.players[player_id]
        old_level = player.level

        player.total_points += points
        player.experience += points

        # Verificar se subiu de nível
        new_level = self._calculate_level(player.experience)
        if new_level > old_level:
            player.level = new_level
            self._trigger_event("level_up", {
                "player_id": player_id,
                "old_level": old_level,
                "new_level": new_level
            })

        # Trigger evento de pontos
        self._trigger_event("points_awarded", {
            "player_id": player_id,
            "points": points,
            "reason": reason
        })

        return True

    def _calculate_level(self, experience: int) -> int:
        """Calcula nível baseado na experiência"""
        for level, threshold in enumerate(self.level_thresholds):
            if experience < threshold:
                return max(1, level - 1)
        return len(self.level_thresholds) - 1

    def check_achievements(self, player_id: str, event_data: Dict[str, Any]) -> List[Achievement]:
        """Verifica e concede achievements"""
        if player_id not in self.players:
            return []

        player = self.players[player_id]
        newly_unlocked = []

        for achievement_id, achievement in self.achievements.items():
            if achievement_id in player.achievements:
                continue  # Já possui

            if self._check_achievement_requirements(player, achievement, event_data):
                player.achievements.append(achievement_id)

                # Conceder pontos do achievement
                bonus_points = int(achievement.points * self.point_multipliers[achievement.rarity])
                self.award_points(player_id, bonus_points, f"Achievement: {achievement.name}")

                newly_unlocked.append(achievement)

                # Trigger evento
                self._trigger_event("achievement_unlocked", {
                    "player_id": player_id,
                    "achievement": achievement
                })

        return newly_unlocked

    def _check_achievement_requirements(self, player: Player, achievement: Achievement, event_data: Dict[str, Any]) -> bool:
        """Verifica se os requisitos do achievement foram atendidos"""
        requirements = achievement.requirements
        stats = player.stats

        for req_key, req_value in requirements.items():
            if req_key == "analyses_count":
                if stats.get("analyses_count", 0) < req_value:
                    return False
            elif req_key == "issues_resolved":
                if stats.get("issues_resolved", 0) < req_value:
                    return False
            elif req_key == "zero_issue_files":
                if stats.get("zero_issue_files", 0) < req_value:
                    return False
            elif req_key == "performance_optimizations":
                if stats.get("performance_optimizations", 0) < req_value:
                    return False
            elif req_key == "security_fixes":
                if stats.get("security_fixes", 0) < req_value:
                    return False
            elif req_key == "vulnerabilities_found":
                if stats.get("vulnerabilities_found", 0) < req_value:
                    return False
            elif req_key == "collaboration_sessions":
                if stats.get("collaboration_sessions", 0) < req_value:
                    return False
            elif req_key == "daily_streak":
                if player.streaks.get("daily", 0) < req_value:
                    return False
            elif req_key == "languages_analyzed":
                if len(stats.get("languages_analyzed", set())) < req_value:
                    return False
            elif req_key == "night_analyses":
                if stats.get("night_analyses", 0) < req_value:
                    return False

        return True

    def update_player_stats(self, player_id: str, stat_updates: Dict[str, Any]):
        """Atualiza estatísticas do jogador"""
        if player_id not in self.players:
            return

        player = self.players[player_id]

        for stat_key, value in stat_updates.items():
            if stat_key == "languages_analyzed" and isinstance(value, str):
                # Adicionar linguagem ao set
                if "languages_analyzed" not in player.stats:
                    player.stats["languages_analyzed"] = set()
                player.stats["languages_analyzed"].add(value)
            else:
                # Incrementar estatística
                player.stats[stat_key] = player.stats.get(stat_key, 0) + value

        player.last_activity = datetime.now()

        # Verificar achievements
        self.check_achievements(player_id, stat_updates)

    def join_challenge(self, player_id: str, challenge_id: str) -> bool:
        """Jogador entra em um desafio"""
        if player_id not in self.players or challenge_id not in self.challenges:
            return False

        challenge = self.challenges[challenge_id]

        if not challenge.is_active:
            return False

        if player_id not in challenge.participants:
            challenge.participants.append(player_id)

        return True

    def check_challenge_progress(self, player_id: str, challenge_id: str) -> Dict[str, Any]:
        """Verifica progresso em um desafio"""
        if player_id not in self.players or challenge_id not in self.challenges:
            return {}

        player = self.players[player_id]
        challenge = self.challenges[challenge_id]

        progress = {}
        requirements = challenge.requirements

        for req_key, req_value in requirements.items():
            if req_key == "issues_to_resolve":
                current = player.stats.get("issues_resolved", 0)
                progress[req_key] = {
                    "current": current,
                    "required": req_value,
                    "percentage": min(100, (current / req_value) * 100)
                }
            elif req_key == "vulnerabilities_to_fix":
                current = player.stats.get("security_fixes", 0)
                progress[req_key] = {
                    "current": current,
                    "required": req_value,
                    "percentage": min(100, (current / req_value) * 100)
                }
            elif req_key == "optimizations_needed":
                current = player.stats.get("performance_optimizations", 0)
                progress[req_key] = {
                    "current": current,
                    "required": req_value,
                    "percentage": min(100, (current / req_value) * 100)
                }

        # Verificar se completou
        completed = all(
            progress[key]["percentage"] >= 100
            for key in progress.keys()
        )

        if completed and player_id in challenge.participants:
            # Conceder recompensa
            self.award_points(player_id, challenge.points_reward, f"Challenge: {challenge.name}")

        return {
            "challenge_name": challenge.name,
            "progress": progress,
            "completed": completed,
            "time_remaining": (challenge.end_date - datetime.now()).total_seconds() if challenge.end_date else None
        }

    def get_leaderboard(self, category: str = "overall", limit: int = 10) -> List[Dict[str, Any]]:
        """Obtém leaderboard"""
        players_list = list(self.players.values())

        if category == "overall":
            players_list.sort(key=lambda p: p.total_points, reverse=True)
        elif category == "level":
            players_list.sort(key=lambda p: (p.level, p.experience), reverse=True)
        elif category == "achievements":
            players_list.sort(key=lambda p: len(p.achievements), reverse=True)
        elif category == "streak":
            players_list.sort(key=lambda p: p.streaks.get("daily", 0), reverse=True)

        leaderboard = []
        for i, player in enumerate(players_list[:limit]):
            entry = {
                "rank": i + 1,
                "player_id": player.id,
                "username": player.username,
                "level": player.level,
                "total_points": player.total_points,
                "achievements_count": len(player.achievements),
                "daily_streak": player.streaks.get("daily", 0)
            }

            if category == "overall":
                entry["score"] = player.total_points
            elif category == "level":
                entry["score"] = f"Level {player.level}"
            elif category == "achievements":
                entry["score"] = len(player.achievements)
            elif category == "streak":
                entry["score"] = player.streaks.get("daily", 0)

            leaderboard.append(entry)

        return leaderboard

    def get_player_profile(self, player_id: str) -> Optional[Dict[str, Any]]:
        """Obtém perfil completo do jogador"""
        if player_id not in self.players:
            return None

        player = self.players[player_id]

        # Achievements por raridade
        achievements_by_rarity = {}
        for achievement_id in player.achievements:
            if achievement_id in self.achievements:
                achievement = self.achievements[achievement_id]
                rarity = achievement.rarity.value
                if rarity not in achievements_by_rarity:
                    achievements_by_rarity[rarity] = []
                achievements_by_rarity[rarity].append(achievement)

        # Progresso para próximo nível
        current_level_threshold = self.level_thresholds[player.level] if player.level < len(self.level_thresholds) else 0
        next_level_threshold = self.level_thresholds[player.level + 1] if player.level + 1 < len(self.level_thresholds) else current_level_threshold
        level_progress = 0
        if next_level_threshold > current_level_threshold:
            level_progress = ((player.experience - current_level_threshold) / (next_level_threshold - current_level_threshold)) * 100

        # Desafios ativos
        active_challenges = []
        for challenge_id, challenge in self.challenges.items():
            if challenge.is_active and player_id in challenge.participants:
                progress = self.check_challenge_progress(player_id, challenge_id)
                active_challenges.append(progress)

        return {
            "player_info": {
                "id": player.id,
                "username": player.username,
                "level": player.level,
                "experience": player.experience,
                "total_points": player.total_points,
                "level_progress": level_progress,
                "joined_date": player.joined_date.isoformat(),
                "last_activity": player.last_activity.isoformat()
            },
            "achievements": {
                "total": len(player.achievements),
                "by_rarity": achievements_by_rarity,
                "recent": [
                    self.achievements[aid] for aid in player.achievements[-5:]
                    if aid in self.achievements
                ]
            },
            "stats": dict(player.stats),
            "streaks": player.streaks,
            "active_challenges": active_challenges,
            "preferences": player.preferences
        }

    def _trigger_event(self, event_type: str, data: Dict[str, Any]):
        """Dispara evento do sistema"""
        if event_type in self.event_handlers:
            for handler in self.event_handlers[event_type]:
                try:
                    handler(data)
                except Exception as e:
                    print(f"Erro ao executar handler de evento {event_type}: {e}")

    def register_event_handler(self, event_type: str, handler: callable):
        """Registra handler para evento"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)

    def simulate_code_analysis_activity(self, player_id: str, analysis_result: Dict[str, Any]):
        """Simula atividade de análise de código para gamificação"""
        if player_id not in self.players:
            return

        # Atualizar estatísticas baseadas na análise
        stats_update = {
            "analyses_count": 1,
            "total_files_analyzed": 1
        }

        # Análise de linguagem
        file_path = analysis_result.get("file_path", "")
        if file_path:
            extension = Path(file_path).suffix.lower()
            language_map = {
                ".py": "python",
                ".js": "javascript",
                ".ts": "typescript",
                ".java": "java",
                ".cpp": "cpp",
                ".go": "go",
                ".rs": "rust",
                ".php": "php"
            }
            if extension in language_map:
                stats_update["languages_analyzed"] = language_map[extension]

        # Issues resolvidos
        issues = analysis_result.get("issues", [])
        issues_resolved = len([i for i in issues if i.get("resolved", False)])
        if issues_resolved > 0:
            stats_update["issues_resolved"] = issues_resolved

        # Zero issues (arquivo perfeito)
        if len(issues) == 0:
            stats_update["zero_issue_files"] = 1

        # Vulnerabilidades encontradas
        security_issues = len([i for i in issues if i.get("type") == "security"])
        if security_issues > 0:
            stats_update["vulnerabilities_found"] = security_issues

        # Otimizações de performance
        performance_issues = len([i for i in issues if i.get("type") == "performance"])
        if performance_issues > 0:
            stats_update["performance_optimizations"] = performance_issues

        # Análise noturna (22h-6h)
        current_hour = datetime.now().hour
        if current_hour >= 22 or current_hour <= 6:
            stats_update["night_analyses"] = 1

        # Atualizar estatísticas
        self.update_player_stats(player_id, stats_update)

        # Conceder pontos base
        base_points = 10

        # Bonus por qualidade
        if len(issues) == 0:
            base_points += 20  # Bonus por código perfeito
        elif issues_resolved > 0:
            base_points += issues_resolved * 5  # 5 pontos por issue resolvido

        # Bonus por linguagem nova
        player = self.players[player_id]
        if "languages_analyzed" in stats_update:
            language = stats_update["languages_analyzed"]
            if language not in player.stats.get("languages_analyzed", set()):
                base_points += 50  # Bonus por nova linguagem

        self.award_points(player_id, base_points, "Análise de código")

def demo_gamification_system():
    """Demonstração do sistema de gamificação"""
    print("🎮 QUIMERA ADVANCED GAMIFICATION SYSTEM")
    print("=" * 50)

    # Inicializar sistema
    game_engine = GamificationEngine()

    # Registrar alguns jogadores
    players = []
    for i, (username, email) in enumerate([
        ("alice_dev", "alice@example.com"),
        ("bob_coder", "bob@example.com"),
        ("charlie_hacker", "charlie@example.com")
    ]):
        player_id = game_engine.register_player(username, email)
        players.append(player_id)
        print(f"👤 Jogador registrado: {username} (ID: {player_id[:8]}...)")

    print(f"\n🎯 Total de achievements disponíveis: {len(game_engine.achievements)}")
    print(f"🏆 Total de desafios ativos: {len([c for c in game_engine.challenges.values() if c.is_active])}")

    # Simular atividades para Alice
    alice_id = players[0]
    print(f"\n🎪 Simulando atividades para Alice...")

    # Primeira análise
    analysis_result = {
        "file_path": "main.py",
        "issues": [
            {"type": "style", "resolved": True},
            {"type": "security", "resolved": True}
        ]
    }
    game_engine.simulate_code_analysis_activity(alice_id, analysis_result)

    # Mais algumas análises
    for i in range(15):
        analysis_result = {
            "file_path": f"module_{i}.py",
            "issues": [{"type": "style", "resolved": True}] * random.randint(0, 3)
        }
        game_engine.simulate_code_analysis_activity(alice_id, analysis_result)

    # Análise em JavaScript
    analysis_result = {
        "file_path": "app.js",
        "issues": [{"type": "performance", "resolved": True}]
    }
    game_engine.simulate_code_analysis_activity(alice_id, analysis_result)

    # Código perfeito
    for i in range(3):
        analysis_result = {
            "file_path": f"perfect_{i}.py",
            "issues": []  # Zero issues
        }
        game_engine.simulate_code_analysis_activity(alice_id, analysis_result)

    # Verificar perfil da Alice
    print(f"\n👤 PERFIL DA ALICE")
    print("-" * 30)
    alice_profile = game_engine.get_player_profile(alice_id)

    player_info = alice_profile["player_info"]
    print(f"Nível: {player_info['level']}")
    print(f"Experiência: {player_info['experience']}")
    print(f"Pontos totais: {player_info['total_points']}")
    print(f"Progresso do nível: {player_info['level_progress']:.1f}%")

    achievements_info = alice_profile["achievements"]
    print(f"\n🏆 Achievements desbloqueados: {achievements_info['total']}")

    if achievements_info["recent"]:
        print("Achievements recentes:")
        for achievement in achievements_info["recent"]:
            rarity_icons = {
                "common": "🥉",
                "uncommon": "🥈",
                "rare": "🥇",
                "epic": "💎",
                "legendary": "👑",
                "mythic": "⭐"
            }
            icon = rarity_icons.get(achievement.rarity.value, "🏆")
            print(f"  {icon} {achievement.name} - {achievement.description}")

    stats = alice_profile["stats"]
    print(f"\n📊 Estatísticas:")
    print(f"  Análises realizadas: {stats.get('analyses_count', 0)}")
    print(f"  Issues resolvidos: {stats.get('issues_resolved', 0)}")
    print(f"  Arquivos zero issues: {stats.get('zero_issue_files', 0)}")
    print(f"  Linguagens analisadas: {len(stats.get('languages_analyzed', set()))}")

    # Simular atividades para outros jogadores
    print(f"\n🎪 Simulando atividades para outros jogadores...")

    for player_id in players[1:]:
        for i in range(random.randint(5, 20)):
            analysis_result = {
                "file_path": f"file_{i}.py",
                "issues": [{"type": "style", "resolved": True}] * random.randint(0, 5)
            }
            game_engine.simulate_code_analysis_activity(player_id, analysis_result)

    # Desafios
    print(f"\n🏁 DESAFIOS ATIVOS")
    print("-" * 30)

    for challenge_id, challenge in game_engine.challenges.items():
        if challenge.is_active:
            print(f"\n🎯 {challenge.name}")
            print(f"   Descrição: {challenge.description}")
            print(f"   Dificuldade: {challenge.difficulty.upper()}")
            print(f"   Recompensa: {challenge.points_reward} pontos")
            print(f"   Participantes: {len(challenge.participants)}")

            # Alice entra no desafio
            if alice_id not in challenge.participants:
                game_engine.join_challenge(alice_id, challenge_id)
                print(f"   ✅ Alice entrou no desafio!")

            # Verificar progresso
            progress = game_engine.check_challenge_progress(alice_id, challenge_id)
            if progress:
                print(f"   📈 Progresso da Alice:")
                for req, data in progress["progress"].items():
                    print(f"      {data['current']}/{data['required']} ({data['percentage']:.1f}%)")

    # Leaderboard
    print(f"\n🏆 LEADERBOARD GERAL")
    print("-" * 30)
    leaderboard = game_engine.get_leaderboard("overall", 5)

    for entry in leaderboard:
        medals = ["🥇", "🥈", "🥉", "🏅", "🏅"]
        medal = medals[entry["rank"] - 1] if entry["rank"] <= len(medals) else "🏅"

        print(f"{medal} #{entry['rank']} {entry['username']}")
        print(f"    Level {entry['level']} | {entry['total_points']} pontos | {entry['achievements_count']} achievements")

    # Leaderboard por achievements
    print(f"\n🏆 LEADERBOARD POR ACHIEVEMENTS")
    print("-" * 30)
    achievement_board = game_engine.get_leaderboard("achievements", 3)

    for entry in achievement_board:
        medals = ["🥇", "🥈", "🥉"]
        medal = medals[entry["rank"] - 1] if entry["rank"] <= len(medals) else "🏅"

        print(f"{medal} {entry['username']}: {entry['score']} achievements")

    # Sistema de quest lines
    print(f"\n⚔️  QUEST LINES")
    print("-" * 30)

    for quest_id, quest in game_engine.quest_lines.items():
        print(f"🗡️  {quest.name}")
        print(f"   {quest.description}")
        print(f"   Capítulo atual: {quest.current_chapter + 1}/{len(quest.chapters)}")
        print(f"   Capítulo: {quest.chapters[quest.current_chapter]}")
        if quest.completion_reward:
            print(f"   Recompensa final: {quest.completion_reward.name} ({quest.completion_reward.points} pontos)")

    print(f"\n✨ SISTEMA FUNCIONANDO PERFEITAMENTE!")
    print(f"🎮 Jogadores engajados através de gamificação avançada!")

if __name__ == "__main__":
    demo_gamification_system()