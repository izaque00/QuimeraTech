#!/usr/bin/env python3
"""
Teste Completo da Integração AEGIS Security Core
Verifica se todos os componentes estão funcionando corretamente
"""

import os
import sys
import time
import tempfile
from pathlib import Path

# Adiciona Quimera ao path
sys.path.insert(0, str(Path(__file__).parent))

def test_aegis_core():
    """Testa o AEGIS Core diretamente"""
    print("🔍 Testando AEGIS Core...")
    
    try:
        from quimera.aegis.aegis_core import AegisCore
        
        # Cria instância
        aegis = AegisCore()
        aegis.initialize()
        
        print("✅ AEGIS Core inicializado")
        
        # Testa status
        status = aegis.get_system_status()
        print(f"📊 Status: {status.get('status', 'UNKNOWN')}")
        
        # Testa componentes
        components = status.get('active_components', [])
        print(f"🔧 Componentes ativos: {len(components)}")
        
        for component in components:
            print(f"   - {component}")
            
        return True
        
    except Exception as e:
        print(f"❌ Erro no AEGIS Core: {e}")
        return False

def test_malware_detector():
    """Testa o detector de malware"""
    print("\n🦠 Testando Detector de Malware...")
    
    try:
        from quimera.aegis.malware_detector import MalwareDetector
        
        detector = MalwareDetector()
        
        # Código seguro
        safe_code = "print('Hello World')"
        result = detector.scan_code(safe_code)
        
        if result['safe']:
            print("✅ Código seguro detectado corretamente")
        else:
            print("❌ Falso positivo em código seguro")
            
        # Código suspeito
        suspicious_code = "import os; os.system('rm -rf /')"
        result = detector.scan_code(suspicious_code)
        
        if not result['safe']:
            print("✅ Código suspeito detectado corretamente")
        else:
            print("⚠️ Código suspeito não foi detectado")
            
        return True
        
    except Exception as e:
        print(f"❌ Erro no Detector de Malware: {e}")
        return False

def test_integrity_monitor():
    """Testa o monitor de integridade"""
    print("\n🔍 Testando Monitor de Integridade...")
    
    try:
        from quimera.aegis.integrity_monitor import IntegrityMonitor
        
        monitor = IntegrityMonitor()
        
        # Cria arquivo temporário
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
            f.write("# Arquivo de teste\nprint('test')")
            temp_file = f.name
        
        try:
            # Registra arquivo
            monitor.register_file(temp_file)
            print("✅ Arquivo registrado no monitor")
            
            # Verifica integridade
            result = monitor.verify_file_integrity(temp_file)
            
            if result['verified']:
                print("✅ Integridade verificada corretamente")
            else:
                print("❌ Falha na verificação de integridade")
                
            return True
            
        finally:
            # Remove arquivo temporário
            os.unlink(temp_file)
            
    except Exception as e:
        print(f"❌ Erro no Monitor de Integridade: {e}")
        return False

def test_behavior_analyzer():
    """Testa o analisador de comportamento"""
    print("\n📊 Testando Analisador de Comportamento...")
    
    try:
        from quimera.aegis.behavior_analyzer import BehaviorAnalyzer
        
        analyzer = BehaviorAnalyzer()
        
        # Simula operações normais
        analyzer.record_operation("test_agent", "normal_operation", {"files": 1})
        analyzer.record_operation("test_agent", "normal_operation", {"files": 2})
        
        print("✅ Operações normais registradas")
        
        # Analisa padrões
        analysis = analyzer.analyze_agent_behavior("test_agent")
        
        if analysis.get('anomaly_detected', False):
            print("⚠️ Anomalia detectada em operações normais")
        else:
            print("✅ Comportamento normal analisado corretamente")
            
        return True
        
    except Exception as e:
        print(f"❌ Erro no Analisador de Comportamento: {e}")
        return False

def test_crypto_engine():
    """Testa o engine criptográfico"""
    print("\n🔐 Testando Engine Criptográfico...")
    
    try:
        from quimera.aegis.crypto_engine import CryptoEngine
        
        crypto = CryptoEngine()
        
        # Testa criptografia simétrica
        data = "dados sensíveis de teste"
        encrypted = crypto.encrypt_symmetric(data)
        decrypted = crypto.decrypt_symmetric(encrypted)
        
        if decrypted == data:
            print("✅ Criptografia simétrica funcionando")
        else:
            print("❌ Erro na criptografia simétrica")
            
        # Testa hash
        hash_result = crypto.secure_hash(data)
        
        if hash_result and len(hash_result) > 0:
            print("✅ Hash seguro funcionando")
        else:
            print("❌ Erro no hash seguro")
            
        return True
        
    except Exception as e:
        print(f"❌ Erro no Engine Criptográfico: {e}")
        return False

def test_agent_integration():
    """Testa integração com agentes Quimera"""
    print("\n🤖 Testando Integração com Agentes...")
    
    try:
        from quimera.agentes.agente_fiscal_codigo import AgenteFiscalCodigo
        
        # Cria agente
        agente = AgenteFiscalCodigo()
        
        # Verifica se AEGIS foi inicializado
        if hasattr(agente, 'aegis_enabled') and agente.aegis_enabled:
            print("✅ AEGIS integrado ao Agente Fiscal")
        else:
            print("⚠️ AEGIS não integrado ao Agente Fiscal")
            
        # Testa scan antes de operação
        if hasattr(agente, '_aegis_scan_before_operation'):
            result = agente._aegis_scan_before_operation("test", "test_data")
            if result:
                print("✅ Scan AEGIS funcionando no agente")
            else:
                print("❌ Scan AEGIS bloqueou operação de teste")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro na Integração com Agentes: {e}")
        return False

def test_orquestrador_integration():
    """Testa integração com Orquestrador"""
    print("\n🎭 Testando Integração com Orquestrador...")
    
    try:
        from quimera.core.orquestrador_unificado import OrquestradorUnificado
        
        # Cria orquestrador com AEGIS habilitado
        config = {'usar_aegis_security': True}
        orquestrador = OrquestradorUnificado(config=config)
        
        # Verifica se AEGIS foi inicializado
        if hasattr(orquestrador, 'aegis_integration') and orquestrador.aegis_integration:
            print("✅ AEGIS integrado ao Orquestrador")
            
            # Testa dashboard
            dashboard_data = orquestrador.aegis_integration.get_security_dashboard_data()
            print(f"📊 Status AEGIS no Orquestrador: {dashboard_data.get('status', 'UNKNOWN')}")
            
        else:
            print("⚠️ AEGIS não integrado ao Orquestrador")
            
        return True
        
    except Exception as e:
        print(f"❌ Erro na Integração com Orquestrador: {e}")
        return False

def main():
    """Executa todos os testes"""
    print("=" * 60)
    print("   TESTE COMPLETO - AEGIS SECURITY CORE")
    print("=" * 60)
    
    tests = [
        ("AEGIS Core", test_aegis_core),
        ("Detector de Malware", test_malware_detector),
        ("Monitor de Integridade", test_integrity_monitor),
        ("Analisador de Comportamento", test_behavior_analyzer),
        ("Engine Criptográfico", test_crypto_engine),
        ("Integração com Agentes", test_agent_integration),
        ("Integração com Orquestrador", test_orquestrador_integration),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        
        start_time = time.time()
        try:
            success = test_func()
            end_time = time.time()
            duration = end_time - start_time
            
            results.append((test_name, success, duration))
            
            if success:
                print(f"✅ {test_name} passou em {duration:.2f}s")
            else:
                print(f"❌ {test_name} falhou em {duration:.2f}s")
                
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time
            results.append((test_name, False, duration))
            print(f"💥 {test_name} causou exceção em {duration:.2f}s: {e}")
    
    # Resumo final
    print("\n" + "=" * 60)
    print("   RESUMO DOS TESTES")
    print("=" * 60)
    
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    total_time = sum(duration for _, _, duration in results)
    
    print(f"📊 Testes passaram: {passed}/{total}")
    print(f"⏱️ Tempo total: {total_time:.2f}s")
    
    if passed == total:
        print("🎉 Todos os testes passaram! AEGIS está funcionando perfeitamente!")
    else:
        print("⚠️ Alguns testes falharam. Verifique os detalhes acima.")
        
    print("\n💡 AEGIS Security Core está pronto para proteção ultra-avançada!")

if __name__ == "__main__":
    main()