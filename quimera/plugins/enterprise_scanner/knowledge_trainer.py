#!/usr/bin/env python3
"""
Interface Prática para Expansão da Base de Conhecimento
Ferramenta de linha de comando para treinar o scanner IA
"""

import argparse
import json
import sys
from pathlib import Path
from quimera.plugins.enterprise_scanner.knowledge_expansion_system import KnowledgeManager

class KnowledgeTrainer:
    """Interface de linha de comando para treinar o scanner"""

    def __init__(self):
        self.km = KnowledgeManager()

    def add_single_variation(self, original: str, target: str, confidence: float = 0.95):
        """Adiciona uma única variação"""
        success = self.km.add_manual_variation(original, target, confidence)
        if success:
            self.km.save_all()
            print(f"✅ Variação adicionada: {original} → {target}")
        return success

    def add_from_file(self, file_path: str):
        """Adiciona variações de um arquivo"""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            if isinstance(data, dict):
                # Formato: {"original": "target"}
                added = self.km.add_multiple_variations(data)
                self.km.save_all()
                print(f"✅ Adicionadas {added} variações do arquivo {file_path}")
            else:
                print("❌ Formato de arquivo inválido. Use: {'original': 'target'}")

        except Exception as e:
            print(f"❌ Erro ao ler arquivo: {e}")

    def scan_config_directory(self, directory: str):
        """Escaneia diretório em busca de arquivos .config"""
        config_dir = Path(directory)
        if not config_dir.exists():
            print(f"❌ Diretório não encontrado: {directory}")
            return

        config_files = []
        for pattern in ['*.config', '.config*', '*config*']:
            config_files.extend(config_dir.glob(pattern))

        if not config_files:
            print(f"⚠️ Nenhum arquivo de configuração encontrado em {directory}")
            return

        print(f"🔍 Encontrados {len(config_files)} arquivos de configuração")

        discovered = self.km.discover_from_config_files([str(f) for f in config_files])

        if discovered:
            print(f"\n📋 Variações descobertas:")
            for i, var in enumerate(discovered[:10]):  # Mostrar apenas os primeiros 10
                print(f"   {i+1:2d}. {var.original} → {var.target} (confiança: {var.confidence:.2%})")

            if len(discovered) > 10:
                print(f"   ... e mais {len(discovered) - 10} variações")

            # Pergunta se quer adicionar (simulação)
            print(f"\n💡 Encontradas {len(discovered)} possíveis variações.")
            print("   Use 'confirm_discoveries' para adicioná-las à base de conhecimento.")
        else:
            print("ℹ️ Nenhuma nova variação descoberta")

    def create_training_template(self, output_file: str):
        """Cria um template para adicionar variações manualmente"""
        template = {
            "variations": {
                "CONFIG_OLD_NAME_1": "CONFIG_NEW_NAME_1",
                "CONFIG_OLD_NAME_2": "CONFIG_NEW_NAME_2",
                "CONFIG_CUSTOM_MODULE": "CONFIG_STANDARD_MODULE"
            },
            "description": "Template para adicionar variações de módulos do kernel",
            "instructions": [
                "1. Substitua CONFIG_OLD_NAME_X pelos nomes antigos/variações",
                "2. Substitua CONFIG_NEW_NAME_X pelos nomes corretos/alvos",
                "3. Salve o arquivo e use: python trainer.py --add-from-file template.json"
            ]
        }

        with open(output_file, 'w') as f:
            json.dump(template, f, indent=2)

        print(f"📄 Template criado: {output_file}")
        print("   Edite o arquivo e use --add-from-file para importar")

    def validate_knowledge(self):
        """Valida a base de conhecimento atual"""
        print("🧪 Validando base de conhecimento...")

        # Simular módulos reais (em produção, carregaria de /proc/config.gz)
        real_modules = [
            "CONFIG_SYSVIPC", "CONFIG_NETFILTER", "CONFIG_USB_STORAGE",
            "CONFIG_EXT4_FS", "CONFIG_SOUND_CORE", "CONFIG_DRM_I915",
            "CONFIG_BLUETOOTH", "CONFIG_WIRELESS", "CONFIG_SECURITY_FRAMEWORK"
        ]

        validation_results = self.km.validate_variations(real_modules)

        print("\n📊 Resultados da Validação:")
        perfect = good = poor = 0

        for original, score in validation_results.items():
            if score == 1.0:
                emoji = "✅"
                perfect += 1
            elif score > 0.8:
                emoji = "🟡"
                good += 1
            else:
                emoji = "🔴"
                poor += 1

            print(f"   {emoji} {original}: {score:.1%}")

        print(f"\n📈 Resumo:")
        print(f"   ✅ Perfeitas: {perfect}")
        print(f"   🟡 Boas: {good}")
        print(f"   🔴 Problemáticas: {poor}")

    def show_statistics(self):
        """Mostra estatísticas da base de conhecimento"""
        self.km.display_knowledge_summary()

    def export_knowledge(self, output_file: str):
        """Exporta conhecimento para compartilhamento"""
        self.km.export_knowledge_to_file(output_file)
        print(f"📤 Conhecimento exportado para {output_file}")

    def import_knowledge(self, input_file: str):
        """Importa conhecimento de arquivo externo"""
        imported = self.km.import_knowledge_from_file(input_file)
        if imported > 0:
            self.km.save_all()
            print(f"✅ Importados {imported} itens de {input_file}")

def main():
    """Interface de linha de comando principal"""
    parser = argparse.ArgumentParser(
        description="Treinador da Base de Conhecimento do Scanner IA"
    )

    parser.add_argument('--add', nargs=2, metavar=('ORIGINAL', 'TARGET'),
                       help='Adiciona uma variação: --add CONFIG_OLD CONFIG_NEW')

    parser.add_argument('--add-from-file', metavar='FILE',
                       help='Adiciona variações de um arquivo JSON')

    parser.add_argument('--scan-directory', metavar='DIR',
                       help='Escaneia diretório em busca de arquivos .config')

    parser.add_argument('--create-template', metavar='FILE',
                       help='Cria template para adicionar variações manualmente')

    parser.add_argument('--validate',
                       action='store_true',
                       help='Valida a base de conhecimento atual')

    parser.add_argument('--stats',
                       action='store_true',
                       help='Mostra estatísticas da base de conhecimento')

    parser.add_argument('--export', metavar='FILE',
                       help='Exporta conhecimento para arquivo')

    parser.add_argument('--import', metavar='FILE', dest='import_file',
                       help='Importa conhecimento de arquivo')

    parser.add_argument('--confidence', type=float, default=0.95,
                       help='Nível de confiança para novas variações (0.0-1.0)')

    args = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help()
        return

    trainer = KnowledgeTrainer()

    if args.add:
        trainer.add_single_variation(args.add[0], args.add[1], args.confidence)

    elif args.add_from_file:
        trainer.add_from_file(args.add_from_file)

    elif args.scan_directory:
        trainer.scan_config_directory(args.scan_directory)

    elif args.create_template:
        trainer.create_training_template(args.create_template)

    elif args.validate:
        trainer.validate_knowledge()

    elif args.stats:
        trainer.show_statistics()

    elif args.export:
        trainer.export_knowledge(args.export)

    elif args.import_file:
        trainer.import_knowledge(args.import_file)

if __name__ == "__main__":
    main()