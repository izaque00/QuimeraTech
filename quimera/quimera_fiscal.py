#!/usr/bin/env python3
"""
Quimera Code Fiscal - CLI
Interface de linha de comando para o Agente Fiscal de Código

Uso:
    python quimera_fiscal.py <caminho> [opções]

Exemplos:
    # Fiscalizar projeto inteiro
    python quimera_fiscal.py /caminho/para/projeto

    # Fiscalizar apenas um arquivo
    python quimera_fiscal.py arquivo.py

    # Usar configuração específica
    python quimera_fiscal.py projeto/ --config config.json

    # Modo CI/CD (sem formatação automática)
    python quimera_fiscal.py projeto/ --ci-mode

    # Gerar relatório HTML
    python quimera_fiscal.py projeto/ --report-html relatorio.html
"""

import os
import sys
import json
import argparse
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional

# Adicionar pasta do projeto ao path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from quimera.agentes.agente_fiscal_codigo import AgenteFiscalCodigo, RelatorioFiscalizacao
except ImportError:
    AgenteFiscalCodigo = None
    RelatorioFiscalizacao = object  # type hint fallback
    from quimera.logs.parser import montar_log
except ImportError as e:
    print(f"❌ Erro ao importar módulos do Quimera: {e}")
    print("💡 Certifique-se de que todas as dependências estão instaladas")
    sys.exit(1)


class QuimeraFiscalCLI:
    """Interface CLI para o Agente Fiscal de Código"""

    def __init__(self):
        self.agente: Optional[AgenteFiscalCodigo] = None

    def parse_arguments(self):
        """Parse argumentos da linha de comando"""
        parser = argparse.ArgumentParser(
            description="Quimera Code Fiscal - Fiscalização automática de código Python",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Exemplos de uso:
  %(prog)s projeto/                              # Fiscalizar projeto inteiro
  %(prog)s arquivo.py                           # Fiscalizar arquivo específico
  %(prog)s projeto/ --ci-mode                   # Modo CI/CD (apenas verificação)
  %(prog)s projeto/ --config custom.json       # Usar configuração personalizada
  %(prog)s projeto/ --report-html report.html  # Gerar relatório HTML
  %(prog)s projeto/ --fix-all                   # Corrigir todos os problemas automaticamente
            """
        )

        # Argumentos obrigatórios
        parser.add_argument(
            'path',
            help='Caminho para arquivo ou diretório Python'
        )

        # Configuração
        parser.add_argument(
            '--config', '-c',
            help='Arquivo de configuração JSON'
        )

        # Modos de operação
        parser.add_argument(
            '--ci-mode',
            action='store_true',
            help='Modo CI/CD: apenas detectar problemas, não corrigir'
        )

        parser.add_argument(
            '--fix-all',
            action='store_true',
            help='Corrigir todos os problemas automaticamente'
        )

        parser.add_argument(
            '--check-only',
            action='store_true',
            help='Apenas verificar problemas, não corrigir nada'
        )

        # Formatters específicos
        parser.add_argument(
            '--use-black',
            action='store_true',
            help='Usar Black para formatação'
        )

        parser.add_argument(
            '--use-autopep8',
            action='store_true',
            help='Usar autopep8 para formatação'
        )

        parser.add_argument(
            '--no-isort',
            action='store_true',
            help='Não organizar imports'
        )

        # Relatórios
        parser.add_argument(
            '--report-html',
            help='Salvar relatório em HTML'
        )

        parser.add_argument(
            '--report-json',
            help='Salvar relatório em JSON'
        )

        # Configurações específicas
        parser.add_argument(
            '--line-length',
            type=int,
            default=88,
            help='Comprimento máximo de linha (padrão: 88)'
        )

        parser.add_argument(
            '--complexity-limit',
            type=int,
            default=10,
            help='Limite de complexidade ciclomática (padrão: 10)'
        )

        parser.add_argument(
            '--no-backup',
            action='store_true',
            help='Não criar backup antes das correções'
        )

        parser.add_argument(
            '--parallel',
            action='store_true',
            help='Processar arquivos em paralelo'
        )

        parser.add_argument(
            '--workers',
            type=int,
            default=4,
            help='Número de workers paralelos (padrão: 4)'
        )

        # Verbosidade
        parser.add_argument(
            '--verbose', '-v',
            action='store_true',
            help='Saída detalhada'
        )

        parser.add_argument(
            '--quiet', '-q',
            action='store_true',
            help='Saída mínima'
        )

        # Versão
        parser.add_argument(
            '--version',
            action='version',
            version='Quimera Code Fiscal v1.0.0'
        )

        return parser.parse_args()

    def load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Carrega configuração de arquivo ou usa padrão"""

        # Configuração padrão
        config = {
            'formatar_com_black': True,
            'formatar_com_autopep8': False,
            'organizar_imports': True,
            'corrigir_sintaxe': True,
            'corrigir_indentacao': True,
            'detectar_complexidade': True,
            'limite_complexidade': 10,
            'limite_linha': 88,
            'modo_agressivo': True,
            'backup_arquivos': True,
            'relatorio_detalhado': True,
            'executar_paralelo': False,
            'max_workers': 4,
            'timeout_por_arquivo': 60,
            'extensions_incluir': ['.py'],
            'diretorios_ignorar': [
                '__pycache__', '.git', '.venv', 'venv',
                'node_modules', 'build', 'dist', '.pytest_cache'
            ],
            'arquivos_ignorar': []
        }

        # Carregar arquivo de configuração se especificado
        if config_path:
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                    config.update(file_config)
                print(f"✅ Configuração carregada de: {config_path}")
            except Exception as e:
                print(f"⚠️  Erro ao carregar configuração {config_path}: {e}")
                print("   Usando configuração padrão")

        return config

    def apply_cli_overrides(self, config: Dict[str, Any], args) -> Dict[str, Any]:
        """Aplica overrides da linha de comando"""

        # Modos especiais
        if args.ci_mode:
            config.update({
                'formatar_com_black': False,
                'formatar_com_autopep8': False,
                'organizar_imports': False,
                'corrigir_sintaxe': False,
                'corrigir_indentacao': False,
                'backup_arquivos': False
            })
            print("🔍 Modo CI/CD: apenas detecção de problemas")

        if args.check_only:
            config.update({
                'formatar_com_black': False,
                'formatar_com_autopep8': False,
                'organizar_imports': False,
                'corrigir_sintaxe': False,
                'corrigir_indentacao': False,
                'backup_arquivos': False
            })
            print("👀 Modo verificação: nenhuma correção será aplicada")

        if args.fix_all:
            config.update({
                'formatar_com_black': True,
                'organizar_imports': True,
                'corrigir_sintaxe': True,
                'corrigir_indentacao': True,
                'modo_agressivo': True
            })
            print("🔧 Modo correção automática: todos os problemas serão corrigidos")

        # Formatters específicos
        if args.use_black:
            config['formatar_com_black'] = True
            config['formatar_com_autopep8'] = False

        if args.use_autopep8:
            config['formatar_com_autopep8'] = True
            config['formatar_com_black'] = False

        if args.no_isort:
            config['organizar_imports'] = False

        # Configurações numéricas
        config['limite_linha'] = args.line_length
        config['limite_complexidade'] = args.complexity_limit
        config['max_workers'] = args.workers

        # Flags
        if args.no_backup:
            config['backup_arquivos'] = False

        if args.parallel:
            config['executar_paralelo'] = True

        return config

    async def run_fiscal(self, path: str, config: Dict[str, Any]) -> RelatorioFiscalizacao:
        """Executa a fiscalização"""

        # Verificar se caminho existe
        if not os.path.exists(path):
            raise FileNotFoundError(f"Caminho não encontrado: {path}")

        # Criar agente
        self.agente = AgenteFiscalCodigo(config) if AgenteFiscalCodigo is not None else None

        # Determinar tipo de fiscalização
        if os.path.isfile(path):
            print(f"📄 Fiscalizando arquivo: {path}")
            return await self.agente.fiscalizar_arquivo(path)
        else:
            print(f"📁 Fiscalizando projeto: {path}")
            return await self.agente.fiscalizar_projeto(path)

    def print_summary(self, relatorio: RelatorioFiscalizacao, verbose: bool = False, quiet: bool = False):
        """Imprime resumo dos resultados"""

        if quiet:
            # Saída mínima - apenas números
            total_problemas = len(relatorio.problemas_encontrados)
            total_corrigidos = len(relatorio.problemas_corrigidos)
            print(f"{total_problemas},{total_corrigidos}")
            return

        print("\n" + "="*60)
        print("🎯 RESUMO DA FISCALIZAÇÃO")
        print("="*60)

        print(f"📊 Arquivos analisados: {relatorio.arquivos_analisados}")
        print(f"🐛 Problemas encontrados: {len(relatorio.problemas_encontrados)}")
        print(f"✅ Problemas corrigidos: {len(relatorio.problemas_corrigidos)}")
        print(f"⏱️  Tempo de execução: {relatorio.tempo_execucao:.2f}s")

        if relatorio.problemas_encontrados:
            taxa_correcao = len(relatorio.problemas_corrigidos) / len(relatorio.problemas_encontrados) * 100
            print(f"📈 Taxa de correção: {taxa_correcao:.1f}%")

        # Estatísticas por severidade
        stats_sev = relatorio.estatisticas.get('problemas_por_severidade', {})
        if stats_sev:
            print("\n📋 Problemas por severidade:")
            for severidade, count in stats_sev.items():
                icon = {'critical': '🔴', 'error': '🟠', 'warning': '🟡', 'info': '🔵'}.get(severidade, '⚪')
                print(f"   {icon} {severidade.upper()}: {count}")

        # Estatísticas por tipo
        stats_tipo = relatorio.estatisticas.get('problemas_por_tipo', {})
        if stats_tipo and verbose:
            print("\n🔍 Problemas por tipo:")
            for tipo, count in stats_tipo.items():
                print(f"   • {tipo.title()}: {count}")

        # Ferramentas utilizadas
        if relatorio.ferramentas_utilizadas:
            print(f"\n🛠️ Ferramentas utilizadas: {', '.join(relatorio.ferramentas_utilizadas)}")

        # Mostrar problemas críticos
        problemas_criticos = [p for p in relatorio.problemas_encontrados if p.severidade == 'critical']
        if problemas_criticos and not verbose:
            print(f"\n🔴 {len(problemas_criticos)} problemas críticos encontrados")
            if len(problemas_criticos) <= 5:
                for problema in problemas_criticos:
                    arquivo = os.path.basename(problema.arquivo)
                    print(f"   • {arquivo}:{problema.linha} - {problema.descricao}")
            else:
                print("   Use --verbose para ver todos os detalhes")

        # Detalhes verbosos
        if verbose and relatorio.problemas_encontrados:
            print("\n📝 DETALHES DOS PROBLEMAS:")
            print("-" * 40)

            # Agrupar por arquivo
            from collections import defaultdict
            problemas_por_arquivo = defaultdict(list)
            for problema in relatorio.problemas_encontrados:
                problemas_por_arquivo[problema.arquivo].append(problema)

            for arquivo, problemas in problemas_por_arquivo.items():
                print(f"\n📄 {os.path.basename(arquivo)}:")
                for problema in problemas[:10]:  # Máximo 10 por arquivo
                    status = "✅" if any(c.arquivo == problema.arquivo and c.linha == problema.linha
                                       for c in relatorio.problemas_corrigidos) else "❌"
                    severidade_icon = {'critical': '🔴', 'error': '🟠', 'warning': '🟡', 'info': '🔵'}.get(problema.severidade, '⚪')
                    print(f"   {status} {severidade_icon} Linha {problema.linha}: {problema.descricao}")

                if len(problemas) > 10:
                    print(f"   ... e mais {len(problemas) - 10} problemas")

        # Status final
        print("\n" + "="*60)
        if not relatorio.problemas_encontrados:
            print("🎉 PARABÉNS! Nenhum problema encontrado!")
        elif len(relatorio.problemas_corrigidos) == len(relatorio.problemas_encontrados):
            print("🎯 SUCESSO! Todos os problemas foram corrigidos!")
        elif relatorio.problemas_corrigidos:
            print("⚠️  PARCIAL: Alguns problemas foram corrigidos, outros requerem atenção manual")
        else:
            print("❌ ATENÇÃO: Problemas detectados precisam ser corrigidos")

        print("="*60)

    def save_reports(self, relatorio: RelatorioFiscalizacao, html_path: Optional[str], json_path: Optional[str]):
        """Salva relatórios em arquivos"""

        if html_path:
            try:
                self.agente.salvar_relatorio_html(relatorio, html_path)
                print(f"📄 Relatório HTML salvo: {html_path}")
            except Exception as e:
                print(f"❌ Erro ao salvar relatório HTML: {e}")

        if json_path:
            try:
                self.agente.salvar_relatorio_json(relatorio, json_path)
                print(f"📄 Relatório JSON salvo: {json_path}")
            except Exception as e:
                print(f"❌ Erro ao salvar relatório JSON: {e}")

    def get_exit_code(self, relatorio: RelatorioFiscalizacao, args) -> int:
        """Determina código de saída"""

        total_problemas = len(relatorio.problemas_encontrados)
        problemas_criticos = len([p for p in relatorio.problemas_encontrados if p.severidade == 'critical'])
        problemas_erros = len([p for p in relatorio.problemas_encontrados if p.severidade == 'error'])

        # Modo CI/CD ou check-only: falhar se há problemas
        if args.ci_mode or args.check_only:
            if problemas_criticos > 0:
                return 2  # Crítico
            elif problemas_erros > 0:
                return 1  # Erro
            elif total_problemas > 0:
                return 1  # Avisos tratados como erro em CI
            else:
                return 0  # Sucesso

        # Modo normal: sucesso se corrigiu tudo que podia
        else:
            problemas_nao_corrigidos = total_problemas - len(relatorio.problemas_corrigidos)
            if problemas_nao_corrigidos > 0:
                return 1  # Problemas restantes
            else:
                return 0  # Sucesso

    async def main(self):
        """Função principal"""
        try:
            # Parse argumentos
            args = self.parse_arguments()

            # Configurar logging baseado na verbosidade
            if args.verbose:
                print("🔍 Modo verboso ativado")

            # Carregar configuração
            config = self.load_config(args.config)
            config = self.apply_cli_overrides(config, args)

            # Executar fiscalização
            relatorio = await self.run_fiscal(args.path, config)

            # Mostrar resultados
            self.print_summary(relatorio, args.verbose, args.quiet)

            # Salvar relatórios
            self.save_reports(relatorio, args.report_html, args.report_json)

            # Determinar código de saída
            exit_code = self.get_exit_code(relatorio, args)

            return exit_code

        except KeyboardInterrupt:
            print("\n⚠️ Operação cancelada pelo usuário")
            return 130

        except FileNotFoundError as e:
            print(f"❌ Arquivo/diretório não encontrado: {e}")
            return 2

        except Exception as e:
            print(f"❌ Erro inesperado: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            return 3


def main():
    """Ponto de entrada CLI"""
    cli = QuimeraFiscalCLI()
    exit_code = asyncio.run(cli.main())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()