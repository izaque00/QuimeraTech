#!/usr/bin/env python3
"""
Script de Inicialização do Plugin AEGIS Security Core
Registra e ativa o plugin AEGIS no sistema Quimera
"""

import os
import sys
import logging
from pathlib import Path

# Adiciona o diretório do Quimera ao path
sys.path.insert(0, str(Path(__file__).parent))

from quimera.core.plugin_framework import PluginManager
from quimera.aegis.aegis_plugin import AegisSecurityPlugin

def init_aegis_plugin():
    """Inicializa e registra o plugin AEGIS"""
    
    print("🚀 Inicializando AEGIS Security Core Plugin...")
    
    try:
        # Cria o plugin manager
        plugin_manager = PluginManager()
        
        # Cria instância do plugin AEGIS
        aegis_plugin = AegisSecurityPlugin()
        
        # Registra o plugin
        plugin_manager.register_plugin(aegis_plugin)
        
        # Ativa o plugin
        plugin_manager.enable_plugin("aegis_security")
        
        print("✅ AEGIS Security Core Plugin registrado e ativado com sucesso!")
        
        # Testa funcionalidades básicas
        print("🔍 Testando funcionalidades básicas...")
        
        # Obtém instância ativa do plugin
        active_plugin = plugin_manager.get_plugin("aegis_security")
        
        if active_plugin:
            print("✅ Plugin ativo e funcionando")
            
            # Testa scan de código simples
            test_code = "print('Hello World')"
            result = active_plugin.scan_code(test_code)
            
            if result.get('safe', False):
                print("✅ Scan de código funcionando")
            else:
                print("⚠️ Scan de código retornou resultado inesperado")
                
        else:
            print("❌ Plugin não foi ativado corretamente")
            
    except Exception as e:
        print(f"❌ Erro ao inicializar AEGIS Plugin: {e}")
        logging.error(f"Erro detalhado: {e}", exc_info=True)
        return False
        
    return True

def check_aegis_status():
    """Verifica status atual do AEGIS"""
    
    print("\n📊 Verificando status do AEGIS Security Core...")
    
    try:
        from quimera.aegis.aegis_core import AegisCore
        
        # Cria instância do AEGIS Core
        aegis = AegisCore()
        aegis.initialize()
        
        # Verifica componentes
        status = aegis.get_system_status()
        
        print(f"🛡️ Status AEGIS: {status.get('status', 'UNKNOWN')}")
        print(f"🔐 Componentes ativos: {len(status.get('active_components', []))}")
        print(f"⚡ Proteções ativas: {len(status.get('active_protections', []))}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao verificar status AEGIS: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("   AEGIS SECURITY CORE - INICIALIZAÇÃO")
    print("=" * 60)
    
    # Configura logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Inicializa plugin
    success = init_aegis_plugin()
    
    if success:
        # Verifica status
        check_aegis_status()
        
        print("\n🎉 AEGIS Security Core está pronto para uso!")
        print("📋 Para usar em seus scripts, importe:")
        print("   from quimera.aegis.aegis_core import AegisCore")
        
    else:
        print("\n💥 Falha na inicialização do AEGIS!")
        sys.exit(1)