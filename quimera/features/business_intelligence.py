#!/usr/bin/env python3
"""
📊 QUIMERA BUSINESS INTELLIGENCE DASHBOARD
Sistema avançado de Business Intelligence para análise de código
"""

import json
import sqlite3
import statistics
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import tempfile
import threading
import time

@dataclass
class MetricSnapshot:
    """Snapshot de métricas em um momento específico"""
    timestamp: datetime
    project_id: str
    metrics: Dict[str, Any]
    quality_score: float
    performance_score: float
    security_score: float
    technical_debt: float

@dataclass
class TeamMember:
    """Membro da equipe"""
    id: str
    name: str
    role: str
    expertise_areas: List[str]
    productivity_score: float
    quality_score: float
    collaboration_score: float

@dataclass
class Project:
    """Projeto"""
    id: str
    name: str
    description: str
    languages: List[str]
    team_members: List[str]
    start_date: datetime
    status: str
    metrics_history: List[MetricSnapshot]

class BusinessIntelligenceEngine:
    """Motor de Business Intelligence"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or ":memory:"
        self.projects: Dict[str, Project] = {}
        self.team_members: Dict[str, TeamMember] = {}
        self.metrics_history: List[MetricSnapshot] = []

        # Configurações de alertas
        self.alert_thresholds = {
            "quality_score": 70.0,
            "security_score": 80.0,
            "performance_score": 75.0,
            "technical_debt": 50.0,
            "code_coverage": 80.0,
            "bug_density": 0.1
        }

        # Cache de análises
        self.analysis_cache = {}
        self.cache_expiry = timedelta(hours=1)

        # Inicializar banco de dados
        self._init_database()

    def _init_database(self):
        """Inicializa banco de dados SQLite"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        # Criar tabelas
        cursor = self.conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT,
                description TEXT,
                languages TEXT,
                team_members TEXT,
                start_date TEXT,
                status TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS team_members (
                id TEXT PRIMARY KEY,
                name TEXT,
                role TEXT,
                expertise_areas TEXT,
                productivity_score REAL,
                quality_score REAL,
                collaboration_score REAL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS metric_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                project_id TEXT,
                metrics TEXT,
                quality_score REAL,
                performance_score REAL,
                security_score REAL,
                technical_debt REAL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                project_id TEXT,
                alert_type TEXT,
                severity TEXT,
                message TEXT,
                is_resolved BOOLEAN DEFAULT FALSE
            )
        ''')

        self.conn.commit()

    def add_project(self, project: Project):
        """Adiciona projeto ao sistema"""
        self.projects[project.id] = project

        # Salvar no banco
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO projects
            (id, name, description, languages, team_members, start_date, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            project.id,
            project.name,
            project.description,
            json.dumps(project.languages),
            json.dumps(project.team_members),
            project.start_date.isoformat(),
            project.status
        ))
        self.conn.commit()

    def add_team_member(self, member: TeamMember):
        """Adiciona membro da equipe"""
        self.team_members[member.id] = member

        # Salvar no banco
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO team_members
            (id, name, role, expertise_areas, productivity_score, quality_score, collaboration_score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            member.id,
            member.name,
            member.role,
            json.dumps(member.expertise_areas),
            member.productivity_score,
            member.quality_score,
            member.collaboration_score
        ))
        self.conn.commit()

    def record_metrics(self, snapshot: MetricSnapshot):
        """Registra snapshot de métricas"""
        self.metrics_history.append(snapshot)

        # Adicionar ao histórico do projeto
        if snapshot.project_id in self.projects:
            self.projects[snapshot.project_id].metrics_history.append(snapshot)

        # Salvar no banco
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO metric_snapshots
            (timestamp, project_id, metrics, quality_score, performance_score, security_score, technical_debt)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            snapshot.timestamp.isoformat(),
            snapshot.project_id,
            json.dumps(snapshot.metrics),
            snapshot.quality_score,
            snapshot.performance_score,
            snapshot.security_score,
            snapshot.technical_debt
        ))
        self.conn.commit()

        # Verificar alertas
        self._check_alerts(snapshot)

    def _check_alerts(self, snapshot: MetricSnapshot):
        """Verifica se algum threshold foi violado"""
        alerts = []

        if snapshot.quality_score < self.alert_thresholds["quality_score"]:
            alerts.append({
                "type": "quality_degradation",
                "severity": "warning",
                "message": f"Qualidade do código abaixo do threshold: {snapshot.quality_score:.1f}%"
            })

        if snapshot.security_score < self.alert_thresholds["security_score"]:
            alerts.append({
                "type": "security_risk",
                "severity": "critical",
                "message": f"Score de segurança baixo: {snapshot.security_score:.1f}%"
            })

        if snapshot.performance_score < self.alert_thresholds["performance_score"]:
            alerts.append({
                "type": "performance_issue",
                "severity": "warning",
                "message": f"Performance abaixo do esperado: {snapshot.performance_score:.1f}%"
            })

        if snapshot.technical_debt > self.alert_thresholds["technical_debt"]:
            alerts.append({
                "type": "technical_debt",
                "severity": "warning",
                "message": f"Dívida técnica alta: {snapshot.technical_debt:.1f}%"
            })

        # Salvar alertas
        for alert in alerts:
            self._save_alert(snapshot.project_id, alert)

    def _save_alert(self, project_id: str, alert: Dict[str, Any]):
        """Salva alerta no banco"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO alerts (timestamp, project_id, alert_type, severity, message)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            project_id,
            alert["type"],
            alert["severity"],
            alert["message"]
        ))
        self.conn.commit()

    def generate_executive_dashboard(self) -> Dict[str, Any]:
        """Gera dashboard executivo"""
        cache_key = "executive_dashboard"

        # Verificar cache
        if self._is_cache_valid(cache_key):
            return self.analysis_cache[cache_key]["data"]

        # Métricas gerais
        total_projects = len(self.projects)
        active_projects = len([p for p in self.projects.values() if p.status == "active"])
        total_team_members = len(self.team_members)

        # Scores médios
        recent_snapshots = self._get_recent_snapshots(days=7)
        if recent_snapshots:
            avg_quality = statistics.mean([s.quality_score for s in recent_snapshots])
            avg_performance = statistics.mean([s.performance_score for s in recent_snapshots])
            avg_security = statistics.mean([s.security_score for s in recent_snapshots])
            avg_technical_debt = statistics.mean([s.technical_debt for s in recent_snapshots])
        else:
            avg_quality = avg_performance = avg_security = avg_technical_debt = 0

        # Alertas críticos
        critical_alerts = self._get_active_alerts(severity="critical")

        # ROI de qualidade
        quality_roi = self._calculate_quality_roi()

        # Tendências
        trends = self._calculate_trends()

        dashboard = {
            "overview": {
                "total_projects": total_projects,
                "active_projects": active_projects,
                "total_team_members": total_team_members,
                "critical_alerts": len(critical_alerts)
            },
            "quality_metrics": {
                "overall_quality_score": avg_quality,
                "performance_score": avg_performance,
                "security_score": avg_security,
                "technical_debt": avg_technical_debt
            },
            "business_impact": {
                "quality_roi": quality_roi,
                "estimated_cost_savings": quality_roi * 10000,  # Exemplo
                "risk_reduction": avg_security * 0.8
            },
            "trends": trends,
            "critical_alerts": critical_alerts[:5],  # Top 5
            "top_performing_projects": self._get_top_projects(5),
            "team_performance": self._get_team_performance_summary()
        }

        # Cache resultado
        self.analysis_cache[cache_key] = {
            "data": dashboard,
            "timestamp": datetime.now()
        }

        return dashboard

    def generate_technical_dashboard(self, project_id: Optional[str] = None) -> Dict[str, Any]:
        """Gera dashboard técnico"""
        cache_key = f"technical_dashboard_{project_id or 'all'}"

        if self._is_cache_valid(cache_key):
            return self.analysis_cache[cache_key]["data"]

        # Filtrar por projeto se especificado
        if project_id:
            snapshots = [s for s in self.metrics_history if s.project_id == project_id]
            projects = [self.projects[project_id]] if project_id in self.projects else []
        else:
            snapshots = self.metrics_history
            projects = list(self.projects.values())

        # Análise de código
        code_analysis = self._analyze_code_metrics(snapshots)

        # Análise de segurança
        security_analysis = self._analyze_security_metrics(snapshots)

        # Análise de performance
        performance_analysis = self._analyze_performance_metrics(snapshots)

        # Análise de dívida técnica
        technical_debt_analysis = self._analyze_technical_debt(snapshots)

        # Linguagens mais usadas
        language_distribution = self._get_language_distribution(projects)

        # Hotspots de problemas
        problem_hotspots = self._identify_problem_hotspots(snapshots)

        dashboard = {
            "code_quality": code_analysis,
            "security": security_analysis,
            "performance": performance_analysis,
            "technical_debt": technical_debt_analysis,
            "language_distribution": language_distribution,
            "problem_hotspots": problem_hotspots,
            "improvement_recommendations": self._generate_technical_recommendations(snapshots)
        }

        self.analysis_cache[cache_key] = {
            "data": dashboard,
            "timestamp": datetime.now()
        }

        return dashboard

    def generate_team_dashboard(self) -> Dict[str, Any]:
        """Gera dashboard da equipe"""
        cache_key = "team_dashboard"

        if self._is_cache_valid(cache_key):
            return self.analysis_cache[cache_key]["data"]

        # Performance individual
        individual_performance = []
        for member in self.team_members.values():
            performance = {
                "name": member.name,
                "role": member.role,
                "productivity_score": member.productivity_score,
                "quality_score": member.quality_score,
                "collaboration_score": member.collaboration_score,
                "overall_score": (member.productivity_score + member.quality_score + member.collaboration_score) / 3,
                "expertise_areas": member.expertise_areas
            }
            individual_performance.append(performance)

        # Ordenar por performance geral
        individual_performance.sort(key=lambda x: x["overall_score"], reverse=True)

        # Análise de colaboração
        collaboration_analysis = self._analyze_team_collaboration()

        # Distribuição de skills
        skill_distribution = self._analyze_skill_distribution()

        # Identificar gaps de conhecimento
        knowledge_gaps = self._identify_knowledge_gaps()

        # Recomendações de treinamento
        training_recommendations = self._generate_training_recommendations()

        dashboard = {
            "team_overview": {
                "total_members": len(self.team_members),
                "avg_productivity": statistics.mean([m.productivity_score for m in self.team_members.values()]) if self.team_members else 0,
                "avg_quality": statistics.mean([m.quality_score for m in self.team_members.values()]) if self.team_members else 0,
                "avg_collaboration": statistics.mean([m.collaboration_score for m in self.team_members.values()]) if self.team_members else 0
            },
            "individual_performance": individual_performance,
            "collaboration_analysis": collaboration_analysis,
            "skill_distribution": skill_distribution,
            "knowledge_gaps": knowledge_gaps,
            "training_recommendations": training_recommendations
        }

        self.analysis_cache[cache_key] = {
            "data": dashboard,
            "timestamp": datetime.now()
        }

        return dashboard

    def _get_recent_snapshots(self, days: int = 7) -> List[MetricSnapshot]:
        """Obtém snapshots recentes"""
        cutoff_date = datetime.now() - timedelta(days=days)
        return [s for s in self.metrics_history if s.timestamp >= cutoff_date]

    def _get_active_alerts(self, severity: Optional[str] = None) -> List[Dict[str, Any]]:
        """Obtém alertas ativos"""
        cursor = self.conn.cursor()

        if severity:
            cursor.execute('''
                SELECT * FROM alerts
                WHERE is_resolved = FALSE AND severity = ?
                ORDER BY timestamp DESC
            ''', (severity,))
        else:
            cursor.execute('''
                SELECT * FROM alerts
                WHERE is_resolved = FALSE
                ORDER BY timestamp DESC
            ''')

        return [dict(row) for row in cursor.fetchall()]

    def _calculate_quality_roi(self) -> float:
        """Calcula ROI da qualidade"""
        # Simplificado - baseado na melhoria da qualidade ao longo do tempo
        if len(self.metrics_history) < 2:
            return 0.0

        recent_quality = statistics.mean([s.quality_score for s in self.metrics_history[-5:]])
        initial_quality = statistics.mean([s.quality_score for s in self.metrics_history[:5]])

        improvement = recent_quality - initial_quality
        return max(0, improvement * 0.01)  # 1% improvement = 1% ROI

    def _calculate_trends(self) -> Dict[str, str]:
        """Calcula tendências das métricas"""
        if len(self.metrics_history) < 10:
            return {"quality": "stable", "performance": "stable", "security": "stable"}

        recent = self.metrics_history[-5:]
        previous = self.metrics_history[-10:-5]

        trends = {}

        for metric in ["quality_score", "performance_score", "security_score"]:
            recent_avg = statistics.mean([getattr(s, metric) for s in recent])
            previous_avg = statistics.mean([getattr(s, metric) for s in previous])

            if recent_avg > previous_avg + 2:
                trends[metric.replace("_score", "")] = "improving"
            elif recent_avg < previous_avg - 2:
                trends[metric.replace("_score", "")] = "declining"
            else:
                trends[metric.replace("_score", "")] = "stable"

        return trends

    def _get_top_projects(self, limit: int) -> List[Dict[str, Any]]:
        """Obtém projetos com melhor performance"""
        project_scores = []

        for project in self.projects.values():
            if project.metrics_history:
                recent_metrics = project.metrics_history[-5:]
                avg_quality = statistics.mean([m.quality_score for m in recent_metrics])
                avg_performance = statistics.mean([m.performance_score for m in recent_metrics])
                avg_security = statistics.mean([m.security_score for m in recent_metrics])

                overall_score = (avg_quality + avg_performance + avg_security) / 3

                project_scores.append({
                    "name": project.name,
                    "overall_score": overall_score,
                    "quality_score": avg_quality,
                    "performance_score": avg_performance,
                    "security_score": avg_security,
                    "status": project.status
                })

        project_scores.sort(key=lambda x: x["overall_score"], reverse=True)
        return project_scores[:limit]

    def _get_team_performance_summary(self) -> Dict[str, Any]:
        """Resumo de performance da equipe"""
        if not self.team_members:
            return {}

        members = list(self.team_members.values())

        return {
            "top_performer": max(members, key=lambda m: m.productivity_score).name if members else None,
            "quality_leader": max(members, key=lambda m: m.quality_score).name if members else None,
            "collaboration_champion": max(members, key=lambda m: m.collaboration_score).name if members else None,
            "team_size_by_role": self._count_by_role()
        }

    def _count_by_role(self) -> Dict[str, int]:
        """Conta membros por role"""
        roles = {}
        for member in self.team_members.values():
            roles[member.role] = roles.get(member.role, 0) + 1
        return roles

    def _analyze_code_metrics(self, snapshots: List[MetricSnapshot]) -> Dict[str, Any]:
        """Analisa métricas de código"""
        if not snapshots:
            return {}

        quality_scores = [s.quality_score for s in snapshots]

        return {
            "average_quality": statistics.mean(quality_scores),
            "quality_trend": "improving" if len(quality_scores) > 5 and quality_scores[-1] > quality_scores[0] else "stable",
            "quality_distribution": {
                "excellent": len([s for s in quality_scores if s >= 90]),
                "good": len([s for s in quality_scores if 70 <= s < 90]),
                "needs_improvement": len([s for s in quality_scores if s < 70])
            }
        }

    def _analyze_security_metrics(self, snapshots: List[MetricSnapshot]) -> Dict[str, Any]:
        """Analisa métricas de segurança"""
        if not snapshots:
            return {}

        security_scores = [s.security_score for s in snapshots]

        return {
            "average_security": statistics.mean(security_scores),
            "security_trend": "improving" if len(security_scores) > 5 and security_scores[-1] > security_scores[0] else "stable",
            "high_risk_projects": len([s for s in security_scores if s < 70])
        }

    def _analyze_performance_metrics(self, snapshots: List[MetricSnapshot]) -> Dict[str, Any]:
        """Analisa métricas de performance"""
        if not snapshots:
            return {}

        performance_scores = [s.performance_score for s in snapshots]

        return {
            "average_performance": statistics.mean(performance_scores),
            "performance_trend": "improving" if len(performance_scores) > 5 and performance_scores[-1] > performance_scores[0] else "stable",
            "slow_projects": len([s for s in performance_scores if s < 75])
        }

    def _analyze_technical_debt(self, snapshots: List[MetricSnapshot]) -> Dict[str, Any]:
        """Analisa dívida técnica"""
        if not snapshots:
            return {}

        debt_scores = [s.technical_debt for s in snapshots]

        return {
            "average_debt": statistics.mean(debt_scores),
            "debt_trend": "increasing" if len(debt_scores) > 5 and debt_scores[-1] > debt_scores[0] else "stable",
            "high_debt_projects": len([s for s in debt_scores if s > 50])
        }

    def _get_language_distribution(self, projects: List[Project]) -> Dict[str, int]:
        """Distribuição de linguagens"""
        language_count = {}

        for project in projects:
            for language in project.languages:
                language_count[language] = language_count.get(language, 0) + 1

        return language_count

    def _identify_problem_hotspots(self, snapshots: List[MetricSnapshot]) -> List[Dict[str, Any]]:
        """Identifica hotspots de problemas"""
        hotspots = []

        # Agrupar por projeto
        project_metrics = {}
        for snapshot in snapshots:
            if snapshot.project_id not in project_metrics:
                project_metrics[snapshot.project_id] = []
            project_metrics[snapshot.project_id].append(snapshot)

        # Identificar projetos problemáticos
        for project_id, metrics in project_metrics.items():
            if not metrics:
                continue

            recent_metrics = metrics[-3:] if len(metrics) >= 3 else metrics
            avg_quality = statistics.mean([m.quality_score for m in recent_metrics])
            avg_security = statistics.mean([m.security_score for m in recent_metrics])
            avg_performance = statistics.mean([m.performance_score for m in recent_metrics])

            issues = []
            if avg_quality < 70:
                issues.append("low_quality")
            if avg_security < 80:
                issues.append("security_risks")
            if avg_performance < 75:
                issues.append("performance_issues")

            if issues:
                project_name = self.projects[project_id].name if project_id in self.projects else project_id
                hotspots.append({
                    "project": project_name,
                    "issues": issues,
                    "severity": "high" if len(issues) >= 2 else "medium"
                })

        return sorted(hotspots, key=lambda x: len(x["issues"]), reverse=True)

    def _generate_technical_recommendations(self, snapshots: List[MetricSnapshot]) -> List[str]:
        """Gera recomendações técnicas"""
        recommendations = []

        if not snapshots:
            return recommendations

        recent_snapshots = snapshots[-10:] if len(snapshots) >= 10 else snapshots

        avg_quality = statistics.mean([s.quality_score for s in recent_snapshots])
        avg_security = statistics.mean([s.security_score for s in recent_snapshots])
        avg_performance = statistics.mean([s.performance_score for s in recent_snapshots])
        avg_debt = statistics.mean([s.technical_debt for s in recent_snapshots])

        if avg_quality < 75:
            recommendations.append("🔧 Implementar revisões de código mais rigorosas")
            recommendations.append("📚 Treinar equipe em melhores práticas de codificação")

        if avg_security < 80:
            recommendations.append("🔒 Realizar auditoria de segurança completa")
            recommendations.append("🛡️ Implementar análise de segurança automatizada")

        if avg_performance < 75:
            recommendations.append("⚡ Otimizar algoritmos críticos")
            recommendations.append("📊 Implementar profiling de performance")

        if avg_debt > 40:
            recommendations.append("🧹 Planejar sprints de refatoração")
            recommendations.append("📈 Estabelecer métricas de dívida técnica")

        return recommendations

    def _analyze_team_collaboration(self) -> Dict[str, Any]:
        """Analisa colaboração da equipe"""
        if not self.team_members:
            return {}

        collaboration_scores = [m.collaboration_score for m in self.team_members.values()]

        return {
            "average_collaboration": statistics.mean(collaboration_scores),
            "top_collaborators": [
                m.name for m in sorted(self.team_members.values(),
                                     key=lambda x: x.collaboration_score, reverse=True)[:3]
            ]
        }

    def _analyze_skill_distribution(self) -> Dict[str, int]:
        """Analisa distribuição de skills"""
        skill_count = {}

        for member in self.team_members.values():
            for skill in member.expertise_areas:
                skill_count[skill] = skill_count.get(skill, 0) + 1

        return skill_count

    def _identify_knowledge_gaps(self) -> List[str]:
        """Identifica gaps de conhecimento"""
        # Linguagens usadas nos projetos
        project_languages = set()
        for project in self.projects.values():
            project_languages.update(project.languages)

        # Skills da equipe
        team_skills = set()
        for member in self.team_members.values():
            team_skills.update(member.expertise_areas)

        # Gaps = linguagens sem especialistas
        gaps = list(project_languages - team_skills)

        return gaps

    def _generate_training_recommendations(self) -> List[str]:
        """Gera recomendações de treinamento"""
        recommendations = []

        gaps = self._identify_knowledge_gaps()
        if gaps:
            recommendations.append(f"📚 Treinar equipe em: {', '.join(gaps)}")

        # Membros com baixa performance
        low_performers = [
            m for m in self.team_members.values()
            if m.productivity_score < 70
        ]

        if low_performers:
            recommendations.append("🎯 Programa de mentoria para desenvolvedores júnior")

        # Baixa colaboração
        low_collaboration = [
            m for m in self.team_members.values()
            if m.collaboration_score < 70
        ]

        if low_collaboration:
            recommendations.append("🤝 Workshop de trabalho em equipe")

        return recommendations

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Verifica se o cache é válido"""
        if cache_key not in self.analysis_cache:
            return False

        cache_entry = self.analysis_cache[cache_key]
        return (datetime.now() - cache_entry["timestamp"]) < self.cache_expiry

def demo_business_intelligence():
    """Demonstração do sistema de Business Intelligence"""
    print("📊 QUIMERA BUSINESS INTELLIGENCE DASHBOARD")
    print("=" * 50)

    # Inicializar sistema
    bi_engine = BusinessIntelligenceEngine()

    # Adicionar projetos de exemplo
    projects = [
        Project(
            id="proj_001",
            name="Sistema de E-commerce",
            description="Plataforma de vendas online",
            languages=["python", "javascript", "typescript"],
            team_members=["dev_001", "dev_002", "dev_003"],
            start_date=datetime.now() - timedelta(days=90),
            status="active",
            metrics_history=[]
        ),
        Project(
            id="proj_002",
            name="API de Pagamentos",
            description="API para processamento de pagamentos",
            languages=["python", "go"],
            team_members=["dev_002", "dev_004"],
            start_date=datetime.now() - timedelta(days=60),
            status="active",
            metrics_history=[]
        ),
        Project(
            id="proj_003",
            name="Dashboard Analytics",
            description="Dashboard de análise de dados",
            languages=["javascript", "typescript", "python"],
            team_members=["dev_001", "dev_003", "dev_005"],
            start_date=datetime.now() - timedelta(days=30),
            status="active",
            metrics_history=[]
        )
    ]

    for project in projects:
        bi_engine.add_project(project)
        print(f"📁 Projeto adicionado: {project.name}")

    # Adicionar membros da equipe
    team_members = [
        TeamMember(
            id="dev_001",
            name="Alice Santos",
            role="Senior Developer",
            expertise_areas=["python", "javascript", "react"],
            productivity_score=88.5,
            quality_score=92.0,
            collaboration_score=85.0
        ),
        TeamMember(
            id="dev_002",
            name="Bob Silva",
            role="Tech Lead",
            expertise_areas=["python", "go", "microservices"],
            productivity_score=85.0,
            quality_score=90.0,
            collaboration_score=95.0
        ),
        TeamMember(
            id="dev_003",
            name="Carol Lima",
            role="Frontend Developer",
            expertise_areas=["javascript", "typescript", "vue"],
            productivity_score=82.0,
            quality_score=87.0,
            collaboration_score=88.0
        ),
        TeamMember(
            id="dev_004",
            name="David Costa",
            role="Backend Developer",
            expertise_areas=["go", "rust", "kubernetes"],
            productivity_score=90.0,
            quality_score=85.0,
            collaboration_score=80.0
        ),
        TeamMember(
            id="dev_005",
            name="Eva Pereira",
            role="Full Stack Developer",
            expertise_areas=["python", "javascript", "docker"],
            productivity_score=87.0,
            quality_score=89.0,
            collaboration_score=92.0
        )
    ]

    for member in team_members:
        bi_engine.add_team_member(member)
        print(f"👤 Membro adicionado: {member.name} ({member.role})")

    # Simular métricas ao longo do tempo
    print(f"\n📈 Simulando métricas históricas...")

    import random
    for i in range(30):  # 30 dias de dados
        date = datetime.now() - timedelta(days=30-i)

        for project_id in ["proj_001", "proj_002", "proj_003"]:
            # Simular evolução das métricas
            base_quality = 75 + (i * 0.5) + random.uniform(-5, 5)
            base_performance = 80 + (i * 0.3) + random.uniform(-3, 3)
            base_security = 85 + (i * 0.2) + random.uniform(-2, 2)
            base_debt = 40 - (i * 0.2) + random.uniform(-2, 2)

            snapshot = MetricSnapshot(
                timestamp=date,
                project_id=project_id,
                metrics={
                    "lines_of_code": random.randint(10000, 50000),
                    "test_coverage": random.uniform(70, 95),
                    "bug_density": random.uniform(0.05, 0.2),
                    "cyclomatic_complexity": random.uniform(1.5, 4.0)
                },
                quality_score=max(0, min(100, base_quality)),
                performance_score=max(0, min(100, base_performance)),
                security_score=max(0, min(100, base_security)),
                technical_debt=max(0, min(100, base_debt))
            )

            bi_engine.record_metrics(snapshot)

    print(f"✅ {len(bi_engine.metrics_history)} snapshots de métricas registrados")

    # Gerar dashboards
    print(f"\n📊 DASHBOARD EXECUTIVO")
    print("-" * 40)

    exec_dashboard = bi_engine.generate_executive_dashboard()

    overview = exec_dashboard["overview"]
    print(f"📈 Visão Geral:")
    print(f"  Projetos totais: {overview['total_projects']}")
    print(f"  Projetos ativos: {overview['active_projects']}")
    print(f"  Membros da equipe: {overview['total_team_members']}")
    print(f"  Alertas críticos: {overview['critical_alerts']}")

    quality_metrics = exec_dashboard["quality_metrics"]
    print(f"\n🎯 Métricas de Qualidade:")
    print(f"  Qualidade geral: {quality_metrics['overall_quality_score']:.1f}%")
    print(f"  Performance: {quality_metrics['performance_score']:.1f}%")
    print(f"  Segurança: {quality_metrics['security_score']:.1f}%")
    print(f"  Dívida técnica: {quality_metrics['technical_debt']:.1f}%")

    business_impact = exec_dashboard["business_impact"]
    print(f"\n💰 Impacto no Negócio:")
    print(f"  ROI de qualidade: {business_impact['quality_roi']:.2f}%")
    print(f"  Economia estimada: ${business_impact['estimated_cost_savings']:.0f}")
    print(f"  Redução de risco: {business_impact['risk_reduction']:.1f}%")

    trends = exec_dashboard["trends"]
    print(f"\n📈 Tendências:")
    for metric, trend in trends.items():
        emoji = "📈" if trend == "improving" else "📉" if trend == "declining" else "➡️"
        print(f"  {metric.capitalize()}: {emoji} {trend}")

    print(f"\n🏆 TOP PROJETOS:")
    for i, project in enumerate(exec_dashboard["top_performing_projects"][:3], 1):
        medal = ["🥇", "🥈", "🥉"][i-1]
        print(f"  {medal} {project['name']}: {project['overall_score']:.1f} pontos")

    # Dashboard técnico
    print(f"\n🔧 DASHBOARD TÉCNICO")
    print("-" * 40)

    tech_dashboard = bi_engine.generate_technical_dashboard()

    code_quality = tech_dashboard["code_quality"]
    print(f"📊 Qualidade de Código:")
    print(f"  Qualidade média: {code_quality.get('average_quality', 0):.1f}%")

    distribution = code_quality.get('quality_distribution', {})
    print(f"  Distribuição: {distribution.get('excellent', 0)} excelente, {distribution.get('good', 0)} bom, {distribution.get('needs_improvement', 0)} precisa melhorar")

    security = tech_dashboard["security"]
    print(f"\n🔒 Segurança:")
    print(f"  Segurança média: {security.get('average_security', 0):.1f}%")
    print(f"  Projetos de alto risco: {security.get('high_risk_projects', 0)}")

    lang_dist = tech_dashboard["language_distribution"]
    print(f"\n💻 Distribuição de Linguagens:")
    for language, count in sorted(lang_dist.items(), key=lambda x: x[1], reverse=True):
        print(f"  {language}: {count} projetos")

    hotspots = tech_dashboard["problem_hotspots"]
    if hotspots:
        print(f"\n🔥 Hotspots de Problemas:")
        for hotspot in hotspots[:3]:
            print(f"  ⚠️  {hotspot['project']}: {', '.join(hotspot['issues'])} ({hotspot['severity']})")

    recommendations = tech_dashboard["improvement_recommendations"]
    if recommendations:
        print(f"\n💡 Recomendações:")
        for rec in recommendations[:3]:
            print(f"  {rec}")

    # Dashboard da equipe
    print(f"\n👥 DASHBOARD DA EQUIPE")
    print("-" * 40)

    team_dashboard = bi_engine.generate_team_dashboard()

    team_overview = team_dashboard["team_overview"]
    print(f"📊 Visão Geral da Equipe:")
    print(f"  Total de membros: {team_overview['total_members']}")
    print(f"  Produtividade média: {team_overview['avg_productivity']:.1f}")
    print(f"  Qualidade média: {team_overview['avg_quality']:.1f}")
    print(f"  Colaboração média: {team_overview['avg_collaboration']:.1f}")

    print(f"\n🏆 TOP PERFORMERS:")
    for i, member in enumerate(team_dashboard["individual_performance"][:3], 1):
        medal = ["🥇", "🥈", "🥉"][i-1]
        print(f"  {medal} {member['name']} ({member['role']}): {member['overall_score']:.1f}")

    skill_dist = team_dashboard["skill_distribution"]
    print(f"\n🎯 Distribuição de Skills:")
    for skill, count in sorted(skill_dist.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"  {skill}: {count} membros")

    gaps = team_dashboard["knowledge_gaps"]
    if gaps:
        print(f"\n⚠️  Gaps de Conhecimento:")
        for gap in gaps:
            print(f"  🔍 {gap}")

    training_recs = team_dashboard["training_recommendations"]
    if training_recs:
        print(f"\n📚 Recomendações de Treinamento:")
        for rec in training_recs:
            print(f"  {rec}")

    print(f"\n✅ BUSINESS INTELLIGENCE SISTEMA FUNCIONANDO PERFEITAMENTE!")

if __name__ == "__main__":
    demo_business_intelligence()