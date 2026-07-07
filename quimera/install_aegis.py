#!/usr/bin/env python3
"""
AEGIS Installation Script - Instalador do Sistema de Segurança
=============================================================

Script para instalação e configuração automática do sistema
AEGIS Security Core no projeto Quimera.
"""

import os
import sys
import json
import asyncio
import subprocess
from pathlib import Path
from datetime import datetime

# Cores para output
class Colors:
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_colored(text, color=Colors.WHITE):
    """Imprime texto colorido"""
    print(f"{color}{text}{Colors.END}")

def print_header(text):
    """Imprime cabeçalho formatado"""
    print_colored("="*80, Colors.CYAN)
    print_colored(f"  {text}", Colors.BOLD + Colors.WHITE)
    print_colored("="*80, Colors.CYAN)

def print_step(step_num, text):
    """Imprime passo da instalação"""
    print_colored(f"\n🔸 Passo {step_num}: {text}", Colors.BLUE)

def print_success(text):
    """Imprime mensagem de sucesso"""
    print_colored(f"✅ {text}", Colors.GREEN)

def print_warning(text):
    """Imprime mensagem de aviso"""
    print_colored(f"⚠️  {text}", Colors.YELLOW)

def print_error(text):
    """Imprime mensagem de erro"""
    print_colored(f"❌ {text}", Colors.RED)

class AegisInstaller:
    """Instalador do sistema AEGIS"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.aegis_dir = self.project_root / "quimera" / "aegis"
        self.config_file = self.aegis_dir / "config.json"
        self.requirements = [
            "cryptography>=41.0.0",
            "scikit-learn>=1.0.0",
            "numpy>=1.21.0"
        ]
        
        # Built-in modules que não precisam ser instalados
        self.builtin_modules = [
            "asyncio", "pathlib", "dataclasses", "typing", "weakref", "json", "os", "sys"
        ]
        
    def check_python_version(self):
        """Verifica versão do Python"""
        print_step(1, "Verificando versão do Python")
        
        if sys.version_info < (3, 8):
            print_error("Python 3.8+ é necessário para o AEGIS")
            return False
        
        version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        print_success(f"Python {version} - OK")
        return True
    
    def check_project_structure(self):
        """Verifica estrutura do projeto"""
        print_step(2, "Verificando estrutura do projeto Quimera")
        
        required_dirs = [
            self.project_root / "quimera",
            self.project_root / "quimera" / "agentes",
            self.project_root / "quimera" / "core",
            self.project_root / "quimera" / "logs"
        ]
        
        for dir_path in required_dirs:
            if not dir_path.exists():
                print_error(f"Diretório necessário não encontrado: {dir_path}")
                return False
            print_success(f"✓ {dir_path.name}")
        
        # Verificar arquivos essenciais
        required_files = [
            self.project_root / "quimera" / "agentes" / "agente_base.py",
            self.project_root / "quimera" / "core" / "plugin_framework.py",
            self.project_root / "quimera" / "logs" / "__init__.py"
        ]
        
        for file_path in required_files:
            if not file_path.exists():
                print_error(f"Arquivo necessário não encontrado: {file_path}")
                return False
            print_success(f"✓ {file_path.name}")
        
        return True
    
    def install_dependencies(self):
        """Instala dependências necessárias"""
        print_step(3, "Instalando dependências")
        
        for requirement in self.requirements:
            try:
                print(f"  📦 Instalando {requirement}...")
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install", requirement, "-q"
                ])
                print_success(f"✓ {requirement}")
            except subprocess.CalledProcessError as e:
                print_warning(f"Erro ao instalar {requirement}: {e}")
                # Continuar com outras dependências
        
        # Verificar cryptography especificamente
        try:
            import cryptography
            print_success(f"✓ cryptography {cryptography.__version__}")
        except ImportError:
            print_error("Falha crítica: cryptography não pôde ser importada")
            return False
        
        return True
    
    def verify_aegis_files(self):
        """Verifica se arquivos AEGIS estão presentes"""
        print_step(4, "Verificando arquivos do sistema AEGIS")
        
        aegis_files = [
            "__init__.py",
            "aegis_core.py", 
            "aegis_agent.py",
            "malware_detector.py",
            "integrity_monitor.py",
            "behavior_analyzer.py",
            "crypto_engine.py",
            "aegis_plugin.py",
            "demo_integration.py",
            "config.json"
        ]
        
        if not self.aegis_dir.exists():
            print_error(f"Diretório AEGIS não encontrado: {self.aegis_dir}")
            return False
        
        for file_name in aegis_files:
            file_path = self.aegis_dir / file_name
            if not file_path.exists():
                print_error(f"Arquivo AEGIS não encontrado: {file_name}")
                return False
            print_success(f"✓ {file_name}")
        
        return True
    
    def create_directory_structure(self):
        """Cria estrutura de diretórios necessária"""
        print_step(5, "Criando estrutura de diretórios")
        
        directories = [
            self.project_root / "aegis_keys",
            self.project_root / "aegis_baselines_backup", 
            self.project_root / "configs" / "plugins",
            self.project_root / "logs" / "aegis"
        ]
        
        for dir_path in directories:
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
                # Definir permissões seguras para diretórios de chaves
                if "keys" in dir_path.name:
                    os.chmod(dir_path, 0o700)
                print_success(f"✓ {dir_path}")
            except Exception as e:
                print_error(f"Erro ao criar diretório {dir_path}: {e}")
                return False
        
        return True
    
    def configure_aegis(self):
        """Configura sistema AEGIS"""
        print_step(6, "Configurando sistema AEGIS")
        
        # Copiar configuração padrão se necessário
        config_dest = self.project_root / "configs" / "plugins" / "aegis.json"
        
        try:
            if self.config_file.exists():
                import shutil
                shutil.copy2(self.config_file, config_dest)
                print_success(f"✓ Configuração copiada para {config_dest}")
            else:
                print_warning("Arquivo de configuração padrão não encontrado")
        except Exception as e:
            print_warning(f"Erro ao copiar configuração: {e}")
        
        # Criar arquivo de inicialização
        init_script = self.project_root / "start_aegis.py"
        init_content = '''#!/usr/bin/env python3
"""
Script de Inicialização do AEGIS
"""

import asyncio
import sys
from pathlib import Path

# Adicionar path do projeto
sys.path.insert(0, str(Path(__file__).parent))

from quimera.aegis.demo_integration import QuimeraAegisDemo

async def main():
    """Inicia sistema AEGIS"""
    print("🛡️  Iniciando AEGIS Security System...")
    
    demo = QuimeraAegisDemo()
    success = await demo.initialize_system()
    
    if success:
        print("✅ AEGIS iniciado com sucesso!")
        return True
    else:
        print("❌ Falha ao iniciar AEGIS")
        return False

if __name__ == "__main__":
    asyncio.run(main())
'''
        
        try:
            with open(init_script, 'w') as f:
                f.write(init_content)
            os.chmod(init_script, 0o755)
            print_success(f"✓ Script de inicialização criado: {init_script}")
        except Exception as e:
            print_warning(f"Erro ao criar script de inicialização: {e}")
        
        return True
    
    def test_installation(self):
        """Testa instalação do AEGIS"""
        print_step(7, "Testando instalação")
        
        try:
            # Testar imports
            print("  🔍 Testando imports...")
            sys.path.insert(0, str(self.project_root))
            
            from quimera.aegis.aegis_core import AegisSecurityCore
            from quimera.aegis.malware_detector import CodeMalwareDetector
            from quimera.aegis.crypto_engine import QuantumCryptoEngine
            
            print_success("✓ Imports OK")
            
            # Testar inicialização básica
            print("  ⚙️  Testando inicialização...")
            
            async def test_init():
                core = AegisSecurityCore()
                detector = CodeMalwareDetector()
                crypto = QuantumCryptoEngine()
                
                # Testar inicialização
                core_ok = await core.initialize()
                detector_ok = await detector.initialize()
                crypto_ok = await crypto.initialize()
                
                return core_ok and detector_ok and crypto_ok
            
            init_result = asyncio.run(test_init())
            
            if init_result:
                print_success("✓ Inicialização OK")
            else:
                print_warning("⚠️  Inicialização com avisos")
            
            return True
            
        except ImportError as e:
            print_error(f"Erro de import: {e}")
            return False
        except Exception as e:
            print_error(f"Erro no teste: {e}")
            return False
    
    def create_documentation(self):
        """Cria documentação de instalação"""
        print_step(8, "Criando documentação")
        
        readme_content = f'''# AEGIS Security System - Sistema de Segurança Avançada

## Instalação Concluída

O sistema AEGIS foi instalado com sucesso em: {datetime.now().strftime("%d/%m/%Y às %H:%M:%S")}

## Estrutura de Arquivos

```
quimera/
├── aegis/                     # Sistema AEGIS
│   ├── __init__.py
│   ├── aegis_core.py         # Núcleo do sistema
│   ├── aegis_agent.py        # Agente de segurança
│   ├── malware_detector.py   # Detector de malware
│   ├── integrity_monitor.py  # Monitor de integridade
│   ├── behavior_analyzer.py  # Analisador comportamental
│   ├── crypto_engine.py      # Engine de criptografia
│   ├── aegis_plugin.py       # Plugin para framework
│   └── config.json           # Configurações
├── configs/
│   └── plugins/
│       └── aegis.json        # Configuração do plugin
└── start_aegis.py            # Script de inicialização
```

## Como Usar

### 1. Inicialização Básica

```python
from quimera.aegis.demo_integration import QuimeraAegisDemo

demo = QuimeraAegisDemo()
await demo.initialize_system()
```

### 2. Proteger Componentes

```python
from quimera.aegis.aegis_core import AegisSecurityCore

aegis = AegisSecurityCore()
await aegis.initialize()

# Proteger um componente
registration_id = aegis.register_component(
    component=meu_componente,
    component_id="meu_componente_id",
    protection_level="high"
)
```

### 3. Executar Scans de Segurança

```python
# Scan de um componente específico
report = await aegis.scan_component(registration_id, "full")

# Scan de todos os componentes
full_report = await aegis.scan_all_components("standard")
```

### 4. Usar Criptografia

```python
from quimera.aegis.crypto_engine import QuantumCryptoEngine

crypto = QuantumCryptoEngine()
await crypto.initialize()

# Gerar chave
key_id = await crypto.generate_symmetric_key("AES-256-GCM")

# Criptografar dados
encrypted = await crypto.encrypt_data("dados sensíveis", key_id)

# Descriptografar
decrypted = await crypto.decrypt_data(encrypted)
```

## Funcionalidades Principais

- ✅ **Proteção de Componentes**: Registro e monitoramento automático
- ✅ **Detecção de Malware**: Análise estática e dinâmica de código
- ✅ **Monitoramento de Integridade**: Verificação contínua de alterações
- ✅ **Análise Comportamental**: Detecção de anomalias em tempo real
- ✅ **Criptografia Avançada**: Algoritmos pós-quânticos preparados
- ✅ **Auto-Healing**: Restauração automática de componentes
- ✅ **Dashboard de Segurança**: Visualização completa do status
- ✅ **Integração com Quimera**: Plugin nativo para o framework

## Configuração

Edite o arquivo `configs/plugins/aegis.json` para personalizar:

- Intervalos de scan
- Níveis de detecção
- Algoritmos de criptografia
- Políticas de segurança
- Configurações de performance

## Comandos Úteis

```bash
# Iniciar AEGIS
python start_aegis.py

# Executar demonstração completa
python quimera/aegis/demo_integration.py

# Verificar status
python -c "from quimera.aegis import *; print('AEGIS OK')"
```

## Suporte

Para suporte e documentação adicional, consulte:
- Código fonte em `quimera/aegis/`
- Configurações em `configs/plugins/aegis.json`
- Logs em `logs/aegis/`

## Segurança

🔒 **IMPORTANTE**: 
- Chaves criptográficas são armazenadas em `aegis_keys/` com permissões 700
- Baselines de integridade em `aegis_baselines_backup/`
- Logs de segurança em `logs/aegis/`

⚠️  **Mantenha estes diretórios seguros e faça backup regularmente!**

---
Sistema AEGIS instalado e configurado com sucesso! 🛡️
'''
        
        readme_file = self.project_root / "AEGIS_README.md"
        
        try:
            with open(readme_file, 'w', encoding='utf-8') as f:
                f.write(readme_content)
            print_success(f"✓ Documentação criada: {readme_file}")
        except Exception as e:
            print_warning(f"Erro ao criar documentação: {e}")
        
        return True
    
    def run_installation(self):
        """Executa instalação completa"""
        print_header("AEGIS SECURITY SYSTEM - INSTALADOR")
        print_colored("🛡️  Sistema de Segurança Avançada para Quimera", Colors.CYAN)
        print()
        
        steps = [
            ("Verificação do Python", self.check_python_version),
            ("Estrutura do Projeto", self.check_project_structure),
            ("Dependências", self.install_dependencies),
            ("Arquivos AEGIS", self.verify_aegis_files),
            ("Diretórios", self.create_directory_structure),
            ("Configuração", self.configure_aegis),
            ("Teste", self.test_installation),
            ("Documentação", self.create_documentation)
        ]
        
        success_count = 0
        
        for step_name, step_func in steps:
            try:
                if step_func():
                    success_count += 1
                else:
                    print_error(f"Falha em: {step_name}")
            except Exception as e:
                print_error(f"Erro em {step_name}: {e}")
        
        print_header("RESULTADO DA INSTALAÇÃO")
        
        if success_count == len(steps):
            print_colored("🎉 INSTALAÇÃO CONCLUÍDA COM SUCESSO!", Colors.GREEN + Colors.BOLD)
            print()
            print_colored("✅ Sistema AEGIS está pronto para uso!", Colors.GREEN)
            print_colored("🚀 Execute 'python start_aegis.py' para iniciar", Colors.BLUE)
            print_colored("📖 Consulte AEGIS_README.md para instruções", Colors.CYAN)
            return True
        else:
            print_colored(f"⚠️  INSTALAÇÃO PARCIAL: {success_count}/{len(steps)} passos concluídos", Colors.YELLOW)
            print_colored("🔧 Verifique os erros acima e tente novamente", Colors.RED)
            return False

def main():
    """Função principal"""
    installer = AegisInstaller()
    
    try:
        success = installer.run_installation()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print_colored("\n🛑 Instalação cancelada pelo usuário", Colors.YELLOW)
        sys.exit(1)
    except Exception as e:
        print_error(f"Erro inesperado durante instalação: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()