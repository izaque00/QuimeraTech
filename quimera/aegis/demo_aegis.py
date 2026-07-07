"""
AEGIS System Demo - Demonstração Completa do Sistema AEGIS
==========================================================

Script de demonstração que mostra como usar o sistema AEGIS completo
de forma integrada com o projeto Quimera.
"""

import asyncio
import time
from datetime import datetime
from pathlib import Path

# Importar componentes do sistema
from quimera.logs.parser import montar_log
from quimera.aegis.aegis_core import AegisSecurityCore
from quimera.aegis.aegis_agent import AegisSecurityAgent
from quimera.aegis.malware_detector import CodeMalwareDetector
from quimera.aegis.integrity_monitor import IntegrityMonitor
from quimera.aegis.behavior_analyzer import BehaviorAnalyzer
from quimera.aegis.crypto_engine import QuantumCryptoEngine
from quimera.aegis.aegis_plugin import AegisSecurityPlugin
from quimera.aegis.aegis_dashboard import AegisDashboard


class AegisSystemDemo:
    """
    Demonstração completa do sistema AEGIS
    
    Este demo mostra como:
    1. Inicializar todos os componentes AEGIS
    2. Proteger componentes do sistema
    3. Detectar e responder a ameaças
    4. Monitorar segurança em tempo real
    5. Usar o dashboard de controle
    """
    
    def __init__(self):
        self.components = {}
        self.demo_components = []
        self.dashboard = None
    
    async def run_complete_demo(self):
        """Executa demonstração completa do sistema AEGIS"""
        print("\n" + "="*80)
        print("🛡️  AEGIS SECURITY SYSTEM - DEMONSTRAÇÃO COMPLETA")
        print("="*80)
        
        try:
            # 1. Inicializar sistema AEGIS
            await self._demo_initialization()
            
            # 2. Demonstrar proteção de componentes
            await self._demo_component_protection()
            
            # 3. Demonstrar detecção de malware
            await self._demo_malware_detection()
            
            # 4. Demonstrar monitoramento de integridade
            await self._demo_integrity_monitoring()
            
            # 5. Demonstrar análise comportamental
            await self._demo_behavior_analysis()
            
            # 6. Demonstrar criptografia quântica
            await self._demo_quantum_crypto()
            
            # 7. Demonstrar resposta automática a ameaças
            await self._demo_threat_response()
            
            # 8. Demonstrar dashboard de segurança
            await self._demo_security_dashboard()
            
            # 9. Demonstrar relatórios de segurança
            await self._demo_security_reports()
            
            print("\n🎉 Demonstração completa do AEGIS finalizada com sucesso!")
            print("="*80)
            
        except Exception as e:
            print(f"\n❌ Erro durante demonstração: {e}")
        finally:
            await self._cleanup_demo()
    
    async def _demo_initialization(self):
        """Demonstra inicialização do sistema AEGIS"""
        print("\n🚀 FASE 1: Inicialização do Sistema AEGIS")
        print("-" * 50)
        
        # Inicializar AEGIS Core
        print("🔧 Inicializando AEGIS Core...")
        self.components['core'] = AegisSecurityCore()
        success = await self.components['core'].initialize()
        print(f"   ✅ AEGIS Core: {'Inicializado' if success else 'Falha'}")
        
        # Inicializar Detector de Malware
        print("🦠 Inicializando Detector de Malware...")
        self.components['malware_detector'] = CodeMalwareDetector()
        success = await self.components['malware_detector'].initialize()
        print(f"   ✅ Detector de Malware: {'Inicializado' if success else 'Falha'}")
        
        # Inicializar Monitor de Integridade
        print("🔍 Inicializando Monitor de Integridade...")
        self.components['integrity_monitor'] = IntegrityMonitor()
        success = await self.components['integrity_monitor'].initialize()
        print(f"   ✅ Monitor de Integridade: {'Inicializado' if success else 'Falha'}")
        
        # Inicializar Analisador Comportamental
        print("📊 Inicializando Analisador Comportamental...")
        self.components['behavior_analyzer'] = BehaviorAnalyzer()
        success = await self.components['behavior_analyzer'].initialize()
        print(f"   ✅ Analisador Comportamental: {'Inicializado' if success else 'Falha'}")
        
        # Inicializar Motor Criptográfico
        print("🔐 Inicializando Motor Criptográfico Quântico...")
        self.components['crypto_engine'] = QuantumCryptoEngine()
        success = await self.components['crypto_engine'].initialize()
        print(f"   ✅ Motor Criptográfico: {'Inicializado' if success else 'Falha'}")
        
        # Inicializar Dashboard
        print("📱 Inicializando Dashboard de Segurança...")
        self.dashboard = AegisDashboard()
        success = await self.dashboard.initialize()
        print(f"   ✅ Dashboard: {'Inicializado' if success else 'Falha'}")
        
        print("\n✨ Sistema AEGIS totalmente inicializado!")
        await asyncio.sleep(2)
    
    async def _demo_component_protection(self):
        """Demonstra proteção de componentes"""
        print("\n🛡️ FASE 2: Proteção de Componentes")
        print("-" * 50)
        
        # Criar componentes de exemplo
        class ExampleAgent:
            def __init__(self, name):
                self.name = name
                self.id_registro = f"agent_{name}"
                self.data = {"config": "example", "status": "active"}
            
            def execute(self):
                return f"Executando {self.name}"
        
        # Registrar componentes para proteção
        example_agents = [
            ExampleAgent("critical_system"),
            ExampleAgent("user_interface"),
            ExampleAgent("data_processor")
        ]
        
        for agent in example_agents:
            print(f"🔒 Protegendo componente: {agent.name}")
            
            # Registrar no AEGIS Core
            registration_id = self.components['core'].register_component(
                agent, agent.id_registro, 'critical' if 'critical' in agent.name else 'standard'
            )
            
            # Registrar no monitor de integridade
            await self.components['integrity_monitor'].register_component(
                agent, agent.id_registro, {'priority': 'critical' if 'critical' in agent.name else 'normal'}
            )
            
            # Registrar no analisador comportamental
            await self.components['behavior_analyzer'].register_component(
                agent, agent.id_registro, {'monitoring_level': 'high'}
            )
            
            self.demo_components.append({
                'agent': agent,
                'registration_id': registration_id
            })
            
            print(f"   ✅ {agent.name} protegido com ID: {registration_id}")
        
        print(f"\n🎯 {len(example_agents)} componentes protegidos pelo AEGIS!")
        await asyncio.sleep(2)
    
    async def _demo_malware_detection(self):
        """Demonstra detecção de malware"""
        print("\n🦠 FASE 3: Detecção de Malware")
        print("-" * 50)
        
        # Código suspeito para teste
        suspicious_codes = [
            {
                'name': 'Código Limpo',
                'code': '''
def hello_world():
    print("Hello, World!")
    return "success"
                ''',
                'expected': 'SAFE'
            },
            {
                'name': 'Execução de Sistema Suspeita',
                'code': '''
import os
def malicious_function():
    os.system("rm -rf /")
    eval("__import__('os').system('malicious command')")
                ''',
                'expected': 'MALWARE'
            },
            {
                'name': 'Import Suspeito',
                'code': '''
import subprocess
import ctypes
def suspicious_operation():
    subprocess.Popen(['curl', 'evil-site.com'])
                ''',
                'expected': 'SUSPICIOUS'
            }
        ]
        
        detector = self.components['malware_detector']
        
        for test_case in suspicious_codes:
            print(f"🔍 Escaneando: {test_case['name']}")
            
            # Executar scan
            result = await detector.scan_code(test_case['code'])
            
            threats_found = len(result.threats)
            confidence = result.confidence_score
            
            if threats_found == 0:
                status = "✅ LIMPO"
            elif confidence > 0.7:
                status = "❌ MALWARE DETECTADO"
            else:
                status = "⚠️ SUSPEITO"
            
            print(f"   {status} - Ameaças: {threats_found}, Confiança: {confidence:.2f}")
            
            if result.threats:
                for threat in result.threats[:2]:  # Mostrar apenas 2 primeiras
                    print(f"     🚨 {threat.get('type', 'unknown')}: {threat.get('description', 'N/A')}")
        
        print("\n🎯 Demonstração de detecção de malware concluída!")
        await asyncio.sleep(2)
    
    async def _demo_integrity_monitoring(self):
        """Demonstra monitoramento de integridade"""
        print("\n🔍 FASE 4: Monitoramento de Integridade")
        print("-" * 50)
        
        monitor = self.components['integrity_monitor']
        
        print("📊 Verificando integridade de todos os componentes...")
        
        # Executar verificação completa
        integrity_report = await monitor.verify_all_components()
        
        total_components = integrity_report['total_components']
        violations = integrity_report['violations_detected']
        
        print(f"   📈 Componentes verificados: {total_components}")
        print(f"   🚨 Violações detectadas: {violations}")
        
        if violations == 0:
            print("   ✅ Todos os componentes íntegros!")
        else:
            print("   ⚠️ Algumas violações de integridade encontradas")
            
            # Mostrar detalhes das violações
            for comp_id, result in integrity_report['results'].items():
                if not result.get('integrity_ok', True):
                    print(f"     🔴 {comp_id}: {result.get('status', 'unknown')}")
        
        # Demonstrar restauração automática
        print("\n🔄 Demonstrando restauração automática...")
        for demo_comp in self.demo_components[:1]:  # Apenas um para demo
            comp_id = demo_comp['agent'].id_registro
            print(f"🔧 Tentando restaurar integridade de: {comp_id}")
            
            restore_result = await monitor.restore_component_integrity(comp_id)
            
            if restore_result.get('status') == 'success':
                print(f"   ✅ {comp_id}: Integridade restaurada")
            else:
                print(f"   ⚠️ {comp_id}: {restore_result.get('message', 'Falha na restauração')}")
        
        print("\n🎯 Demonstração de monitoramento de integridade concluída!")
        await asyncio.sleep(2)
    
    async def _demo_behavior_analysis(self):
        """Demonstra análise comportamental"""
        print("\n📊 FASE 5: Análise Comportamental")
        print("-" * 50)
        
        analyzer = self.components['behavior_analyzer']
        
        print("🧠 Simulando atividade de componentes...")
        
        # Simular execuções normais e anômalas
        for demo_comp in self.demo_components:
            comp_id = demo_comp['agent'].id_registro
            
            # Simular execuções normais
            for i in range(10):
                execution_data = {
                    'execution_time': 0.1 + (i * 0.01),  # Tempo crescente normal
                    'success': True,
                    'memory_usage': 50.0 + (i * 2),
                    'cpu_usage': 20.0 + (i * 1)
                }
                await analyzer.record_execution(comp_id, execution_data)
            
            # Simular uma execução anômala
            anomalous_data = {
                'execution_time': 10.0,  # Muito alto
                'success': False,
                'memory_usage': 500.0,  # Muito alto
                'cpu_usage': 95.0       # Muito alto
            }
            await analyzer.record_execution(comp_id, anomalous_data)
        
        print("🔍 Analisando padrões comportamentais...")
        
        # Executar análise comportamental
        behavior_report = await analyzer.detect_anomalies_batch()
        
        total_components = behavior_report['total_components']
        total_anomalies = behavior_report['total_anomalies']
        
        print(f"   📈 Componentes analisados: {total_components}")
        print(f"   🚨 Anomalias detectadas: {total_anomalies}")
        
        if total_anomalies > 0:
            print("   ⚠️ Anomalias comportamentais encontradas:")
            
            for comp_id, result in behavior_report['results'].items():
                if result.get('anomalies_count', 0) > 0:
                    anomalies = result.get('anomalies', [])
                    for anomaly in anomalies[:2]:  # Mostrar apenas 2
                        print(f"     🔴 {comp_id}: {anomaly.get('description', 'Anomalia detectada')}")
        else:
            print("   ✅ Nenhuma anomalia comportamental detectada!")
        
        print("\n🎯 Demonstração de análise comportamental concluída!")
        await asyncio.sleep(2)
    
    async def _demo_quantum_crypto(self):
        """Demonstra criptografia quântica"""
        print("\n🔐 FASE 6: Criptografia Quântica")
        print("-" * 50)
        
        crypto = self.components['crypto_engine']
        
        # Dados para criptografar
        test_data = "Dados confidenciais do sistema AEGIS - Ultra Secreto!"
        
        print("🔒 Demonstrando criptografia AES-256-GCM...")
        
        # Criptografar dados
        encryption_result = await crypto.encrypt_data(test_data, "AES-256-GCM")
        
        if encryption_result.success:
            print(f"   ✅ Dados criptografados com sucesso")
            print(f"   🔑 Algoritmo: {encryption_result.algorithm}")
            print(f"   📏 Tamanho criptografado: {len(encryption_result.encrypted_data)} bytes")
            
            # Descriptografar dados
            decryption_result = await crypto.decrypt_data(
                encryption_result.encrypted_data,
                encryption_result.key_id,
                encryption_result.algorithm,
                encryption_result.iv,
                encryption_result.auth_tag
            )
            
            if decryption_result.success:
                decrypted_text = decryption_result.decrypted_data.decode('utf-8')
                print(f"   ✅ Dados descriptografados: {decrypted_text[:30]}...")
                print(f"   🔍 Verificação: {'✅ OK' if decrypted_text == test_data else '❌ FALHA'}")
            else:
                print(f"   ❌ Falha na descriptografia")
        else:
            print(f"   ❌ Falha na criptografia")
        
        print("\n🔐 Demonstrando assinatura digital...")
        
        # Criar assinatura digital
        signature_result = await crypto.sign_data(test_data)
        
        if signature_result.get('success'):
            print(f"   ✅ Assinatura digital criada")
            print(f"   🔑 Algoritmo: {signature_result.get('algorithm')}")
            
            # Verificar assinatura
            verification_result = await crypto.verify_signature(
                test_data,
                signature_result['signature'],
                signature_result['key_id'],
                signature_result['algorithm']
            )
            
            if verification_result.get('verified'):
                print(f"   ✅ Assinatura verificada com sucesso")
            else:
                print(f"   ❌ Falha na verificação da assinatura")
        else:
            print(f"   ❌ Falha na criação da assinatura")
        
        print("\n🔐 Demonstrando hash seguro...")
        
        # Gerar hash seguro
        hash_result = await crypto.generate_secure_hash(test_data, "SHA-256")
        
        if hash_result.get('success'):
            print(f"   ✅ Hash SHA-256 gerado")
            print(f"   🔍 Hash: {hash_result['hash_hex'][:32]}...")
        else:
            print(f"   ❌ Falha na geração do hash")
        
        print("\n🎯 Demonstração de criptografia quântica concluída!")
        await asyncio.sleep(2)
    
    async def _demo_threat_response(self):
        """Demonstra resposta automática a ameaças"""
        print("\n🚨 FASE 7: Resposta Automática a Ameaças")
        print("-" * 50)
        
        core = self.components['core']
        
        print("⚡ Simulando detecção de ameaça crítica...")
        
        # Simular scan que encontra ameaças
        scan_report = await core.scan_all_components('deep')
        
        print(f"   📊 Componentes escaneados: {scan_report.components_scanned}")
        print(f"   🚨 Ameaças detectadas: {len(scan_report.threats_detected)}")
        
        # Simular resposta a ameaças se encontradas
        if scan_report.threats_detected:
            print("\n🛡️ Ativando resposta automática...")
            
            for threat in scan_report.threats_detected[:3]:  # Primeiras 3 ameaças
                print(f"   🎯 Respondendo a: {threat.description}")
                print(f"     📈 Severidade: {threat.level.value}")
                
                # Simular ações de mitigação
                if threat.level.value == 'critical':
                    print(f"     🔒 Ação: Quarentena imediata")
                elif threat.level.value == 'dangerous':
                    print(f"     🔧 Ação: Auto-healing iniciado")
                else:
                    print(f"     👁️ Ação: Monitoramento intensivo")
        else:
            print("   ✅ Nenhuma ameaça crítica detectada - Sistema seguro!")
        
        print("\n🔄 Demonstrando auto-healing...")
        
        # Demonstrar auto-healing em um componente
        if self.demo_components:
            demo_comp = self.demo_components[0]
            comp_id = demo_comp['registration_id']
            
            # Simular ameaça para auto-healing
            from quimera.aegis.aegis_core import SecurityThreat, ThreatLevel
            
            fake_threat = SecurityThreat(
                id="demo_threat_001",
                threat_type="integrity_violation",
                level=ThreatLevel.DANGEROUS,
                source=comp_id,
                description="Demonstração de violação de integridade",
                timestamp=datetime.now()
            )
            
            print(f"🔧 Executando auto-healing em componente: {comp_id}")
            
            healing_result = await core.auto_heal_component(comp_id, fake_threat)
            
            if healing_result:
                print(f"   ✅ Auto-healing bem-sucedido")
            else:
                print(f"   ⚠️ Auto-healing não foi possível")
        
        print("\n🎯 Demonstração de resposta a ameaças concluída!")
        await asyncio.sleep(2)
    
    async def _demo_security_dashboard(self):
        """Demonstra dashboard de segurança"""
        print("\n📱 FASE 8: Dashboard de Segurança")
        print("-" * 50)
        
        if not self.dashboard:
            print("   ⚠️ Dashboard não está disponível")
            return
        
        print("📊 Obtendo visão geral do sistema...")
        
        # Obter visão geral
        overview = await self.dashboard.get_system_overview()
        
        print(f"   🏥 Saúde do Sistema: {overview.get('system_health', 'unknown')}")
        print(f"   🛡️ Status de Proteção: {overview.get('protection_status', 'unknown')}")
        print(f"   🔧 Componentes Ativos: {overview.get('components_active', 0)}")
        print(f"   ⏱️ Uptime: {overview.get('uptime', '0:00:00')}")
        
        print("\n🔍 Análise de ameaças...")
        
        threat_analysis = await self.dashboard.get_threat_analysis()
        
        print(f"   📈 Nível de Risco: {threat_analysis.get('risk_assessment', 'unknown')}")
        print(f"   🚫 Ataques Bloqueados: {threat_analysis.get('blocked_attacks', 0)}")
        print(f"   ⚠️ Ameaças Ativas: {len(threat_analysis.get('current_threats', []))}")
        
        recommendations = threat_analysis.get('recommendations', [])
        if recommendations:
            print(f"   💡 Recomendações:")
            for rec in recommendations[:2]:
                print(f"     • {rec}")
        
        print("\n⚡ Métricas em tempo real...")
        
        live_metrics = await self.dashboard.get_live_metrics()
        
        print(f"   🖥️ Carga do Sistema: {live_metrics.get('system_load', 0):.1f}%")
        print(f"   ⚡ Tempo de Resposta: {live_metrics.get('response_time', 0):.3f}s")
        print(f"   🎯 Nível de Ameaça: {live_metrics.get('threat_level', 'safe')}")
        
        component_status = live_metrics.get('components_status', {})
        online_components = sum(1 for status in component_status.values() if status.get('status') == 'online')
        total_components = len(component_status)
        
        print(f"   🔧 Componentes Online: {online_components}/{total_components}")
        
        print("\n🎯 Demonstração do dashboard concluída!")
        await asyncio.sleep(2)
    
    async def _demo_security_reports(self):
        """Demonstra relatórios de segurança"""
        print("\n📋 FASE 9: Relatórios de Segurança")
        print("-" * 50)
        
        if not self.dashboard:
            print("   ⚠️ Dashboard não está disponível para relatórios")
            return
        
        print("📄 Gerando relatório de segurança das últimas 24h...")
        
        # Gerar relatório
        report = await self.dashboard.get_security_report('24h')
        
        if 'error' in report:
            print(f"   ❌ Erro ao gerar relatório: {report['error']}")
            return
        
        summary = report.get('summary', {})
        
        print(f"   📊 Período: {report.get('period', 'N/A')}")
        print(f"   🔍 Total de Scans: {summary.get('total_scans', 0)}")
        print(f"   🚨 Ameaças Detectadas: {summary.get('threats_detected', 0)}")
        print(f"   ✅ Ameaças Mitigadas: {summary.get('threats_mitigated', 0)}")
        print(f"   📈 Uptime: {summary.get('uptime_percentage', 0):.2f}%")
        
        # Breakdown de ameaças
        breakdown = report.get('threat_breakdown', {})
        if any(breakdown.values()):
            print(f"\n   🔍 Tipos de Ameaças:")
            for threat_type, count in breakdown.items():
                if count > 0:
                    print(f"     • {threat_type.replace('_', ' ').title()}: {count}")
        
        # Recomendações
        recommendations = report.get('recommendations', [])
        if recommendations:
            print(f"\n   💡 Recomendações:")
            for rec in recommendations:
                print(f"     • {rec}")
        
        print("\n💾 Demonstrando exportação de logs...")
        
        # Demonstrar exportação
        export_result = await self.dashboard.execute_command('export_logs', {
            'format': 'json',
            'period': '1h'
        })
        
        if export_result.get('success'):
            result = export_result.get('result', {})
            print(f"   ✅ Logs exportados: {result.get('filename', 'N/A')}")
            print(f"   📝 Eventos Exportados: {result.get('events_exported', 0)}")
        else:
            print(f"   ⚠️ Falha na exportação: {export_result.get('error', 'Erro desconhecido')}")
        
        print("\n🎯 Demonstração de relatórios concluída!")
        await asyncio.sleep(2)
    
    async def _cleanup_demo(self):
        """Limpa recursos da demonstração"""
        print("\n🧹 Finalizando demonstração...")
        
        try:
            # Finalizar dashboard
            if self.dashboard:
                await self.dashboard.shutdown()
            
            # Finalizar componentes AEGIS
            if 'core' in self.components:
                await self.components['core'].shutdown()
            
            print("   ✅ Recursos limpos com sucesso")
            
        except Exception as e:
            print(f"   ⚠️ Erro na limpeza: {e}")


async def main():
    """Função principal da demonstração"""
    print("🛡️ Iniciando demonstração do sistema AEGIS...")
    
    demo = AegisSystemDemo()
    await demo.run_complete_demo()
    
    print("\n👋 Obrigado por usar o AEGIS Security System!")


if __name__ == "__main__":
    # Executar demonstração
    asyncio.run(main())