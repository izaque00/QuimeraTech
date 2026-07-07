#!/usr/bin/env python3
"""
🔌 QUIMERA ADVANCED IDE INTEGRATION
Sistema avançado de integração com IDEs populares
"""

import json
import os
import subprocess
import tempfile
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Union
import socket
import http.server
import socketserver
from urllib.parse import urlparse, parse_qs

@dataclass
class IDEMessage:
    """Mensagem para comunicação com IDE"""
    id: str
    type: str
    command: str
    data: Dict[str, Any]
    timestamp: datetime

@dataclass
class CodeAnalysisResult:
    """Resultado de análise para IDE"""
    file_path: str
    issues: List[Dict[str, Any]]
    suggestions: List[Dict[str, Any]]
    metrics: Dict[str, Any]
    timestamp: datetime

@dataclass
class IDEPlugin:
    """Informações do plugin para IDE"""
    name: str
    version: str
    ide_type: str
    supported_features: List[str]
    installation_path: str
    is_active: bool

class IDECommunicator(ABC):
    """Interface base para comunicação com IDEs"""

    @abstractmethod
    def send_message(self, message: IDEMessage) -> bool:
        """Envia mensagem para o IDE"""
        pass

    @abstractmethod
    def receive_message(self) -> Optional[IDEMessage]:
        """Recebe mensagem do IDE"""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Verifica se está conectado ao IDE"""
        pass

class VSCodeCommunicator(IDECommunicator):
    """Comunicador para Visual Studio Code"""

    def __init__(self, port: int = 8765):
        self.port = port
        self.connected = False
        self.socket = None
        self.message_queue = []
        self.callbacks: Dict[str, Callable] = {}

    def start_server(self):
        """Inicia servidor para comunicação com VSCode"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.bind(('localhost', self.port))
            self.socket.listen(1)
            self.connected = True

            print(f"🔌 Servidor VSCode iniciado na porta {self.port}")

            # Thread para aceitar conexões
            threading.Thread(target=self._accept_connections, daemon=True).start()

        except Exception as e:
            print(f"❌ Erro ao iniciar servidor VSCode: {e}")
            self.connected = False

    def _accept_connections(self):
        """Aceita conexões do VSCode"""
        while self.connected:
            try:
                client_socket, addr = self.socket.accept()
                print(f"🔗 VSCode conectado de {addr}")
                threading.Thread(
                    target=self._handle_client,
                    args=(client_socket,),
                    daemon=True
                ).start()
            except Exception as e:
                if self.connected:
                    print(f"❌ Erro ao aceitar conexão: {e}")

    def _handle_client(self, client_socket):
        """Lida com mensagens do cliente VSCode"""
        try:
            while self.connected:
                data = client_socket.recv(1024).decode('utf-8')
                if not data:
                    break

                try:
                    message_data = json.loads(data)
                    message = IDEMessage(
                        id=message_data.get('id', ''),
                        type=message_data.get('type', ''),
                        command=message_data.get('command', ''),
                        data=message_data.get('data', {}),
                        timestamp=datetime.now()
                    )

                    self.message_queue.append(message)

                    # Executar callback se existir
                    if message.type in self.callbacks:
                        self.callbacks[message.type](message)

                except json.JSONDecodeError:
                    print(f"❌ Erro ao decodificar mensagem: {data}")

        except Exception as e:
            print(f"❌ Erro ao lidar com cliente: {e}")
        finally:
            client_socket.close()

    def send_message(self, message: IDEMessage) -> bool:
        """Envia mensagem para VSCode"""
        if not self.connected:
            return False

        try:
            # Em implementação real, enviaria via WebSocket ou HTTP
            print(f"📤 Enviando para VSCode: {message.command}")
            return True
        except Exception as e:
            print(f"❌ Erro ao enviar mensagem: {e}")
            return False

    def receive_message(self) -> Optional[IDEMessage]:
        """Recebe mensagem do VSCode"""
        if self.message_queue:
            return self.message_queue.pop(0)
        return None

    def is_connected(self) -> bool:
        return self.connected

    def register_callback(self, message_type: str, callback: Callable):
        """Registra callback para tipo de mensagem"""
        self.callbacks[message_type] = callback

class IntelliJCommunicator(IDECommunicator):
    """Comunicador para IntelliJ IDEA"""

    def __init__(self, port: int = 8766):
        self.port = port
        self.connected = False
        self.message_queue = []

    def send_message(self, message: IDEMessage) -> bool:
        """Envia mensagem para IntelliJ"""
        try:
            # Simulação - em implementação real usaria plugin JetBrains
            print(f"📤 Enviando para IntelliJ: {message.command}")
            return True
        except Exception as e:
            print(f"❌ Erro ao enviar mensagem: {e}")
            return False

    def receive_message(self) -> Optional[IDEMessage]:
        """Recebe mensagem do IntelliJ"""
        if self.message_queue:
            return self.message_queue.pop(0)
        return None

    def is_connected(self) -> bool:
        return self.connected

class SublimeCommunicator(IDECommunicator):
    """Comunicador para Sublime Text"""

    def __init__(self):
        self.connected = False
        self.plugin_path = None
        self.message_queue = []

    def send_message(self, message: IDEMessage) -> bool:
        """Envia mensagem para Sublime Text"""
        try:
            # Simulação - em implementação real usaria plugin Python
            print(f"📤 Enviando para Sublime: {message.command}")
            return True
        except Exception as e:
            print(f"❌ Erro ao enviar mensagem: {e}")
            return False

    def receive_message(self) -> Optional[IDEMessage]:
        """Recebe mensagem do Sublime"""
        if self.message_queue:
            return self.message_queue.pop(0)
        return None

    def is_connected(self) -> bool:
        return self.connected

class IDEIntegrationManager:
    """Gerenciador principal de integração com IDEs"""

    def __init__(self):
        self.communicators: Dict[str, IDECommunicator] = {
            'vscode': VSCodeCommunicator(),
            'intellij': IntelliJCommunicator(),
            'sublime': SublimeCommunicator()
        }

        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.analysis_cache: Dict[str, CodeAnalysisResult] = {}

        # Configurações
        self.auto_analysis = True
        self.real_time_feedback = True
        self.analysis_interval = 5  # segundos

        # Callbacks
        self.on_file_change: Optional[Callable] = None
        self.on_analysis_complete: Optional[Callable] = None

    def start_integration(self, ide_type: str) -> bool:
        """Inicia integração com IDE específico"""
        if ide_type not in self.communicators:
            print(f"❌ IDE não suportado: {ide_type}")
            return False

        communicator = self.communicators[ide_type]

        try:
            if isinstance(communicator, VSCodeCommunicator):
                communicator.start_server()
                self._setup_vscode_callbacks(communicator)

            print(f"✅ Integração com {ide_type.upper()} iniciada")
            return True

        except Exception as e:
            print(f"❌ Erro ao iniciar integração com {ide_type}: {e}")
            return False

    def _setup_vscode_callbacks(self, communicator: VSCodeCommunicator):
        """Configura callbacks para VSCode"""
        communicator.register_callback('file_change', self._handle_file_change)
        communicator.register_callback('analysis_request', self._handle_analysis_request)
        communicator.register_callback('cursor_change', self._handle_cursor_change)

    def _handle_file_change(self, message: IDEMessage):
        """Lida com mudanças em arquivos"""
        file_path = message.data.get('file_path')
        content = message.data.get('content')

        if file_path and self.auto_analysis:
            # Agendar análise automática
            threading.Timer(
                self.analysis_interval,
                self._analyze_file_content,
                args=(file_path, content)
            ).start()

    def _handle_analysis_request(self, message: IDEMessage):
        """Lida com solicitações de análise"""
        file_path = message.data.get('file_path')
        content = message.data.get('content', '')

        if file_path:
            result = self._analyze_file_content(file_path, content)
            self._send_analysis_result(message.id, result)

    def _handle_cursor_change(self, message: IDEMessage):
        """Lida com mudanças de cursor"""
        file_path = message.data.get('file_path')
        position = message.data.get('position', {})

        # Fornecer insights contextuais baseados na posição
        if file_path in self.analysis_cache:
            analysis = self.analysis_cache[file_path]
            contextual_info = self._get_contextual_info(analysis, position)

            if contextual_info:
                self._send_contextual_info(file_path, contextual_info)

    def _analyze_file_content(self, file_path: str, content: str) -> CodeAnalysisResult:
        """Analisa conteúdo de arquivo"""
        try:
            # Simulação de análise avançada
            issues = self._detect_issues(content)
            suggestions = self._generate_suggestions(content, issues)
            metrics = self._calculate_metrics(content)

            result = CodeAnalysisResult(
                file_path=file_path,
                issues=issues,
                suggestions=suggestions,
                metrics=metrics,
                timestamp=datetime.now()
            )

            # Cache do resultado
            self.analysis_cache[file_path] = result

            if self.on_analysis_complete:
                self.on_analysis_complete(result)

            return result

        except Exception as e:
            print(f"❌ Erro na análise de {file_path}: {e}")
            return CodeAnalysisResult(
                file_path=file_path,
                issues=[],
                suggestions=[],
                metrics={},
                timestamp=datetime.now()
            )

    def _detect_issues(self, content: str) -> List[Dict[str, Any]]:
        """Detecta problemas no código"""
        issues = []
        lines = content.split('\n')

        for i, line in enumerate(lines, 1):
            # Detectar linhas muito longas
            if len(line) > 120:
                issues.append({
                    "type": "style",
                    "severity": "warning",
                    "message": "Linha muito longa (>120 caracteres)",
                    "line": i,
                    "column": 120,
                    "suggestion": "Considere quebrar a linha"
                })

            # Detectar TODO/FIXME
            if 'TODO' in line or 'FIXME' in line:
                issues.append({
                    "type": "task",
                    "severity": "info",
                    "message": "Item de tarefa encontrado",
                    "line": i,
                    "column": line.find('TODO') if 'TODO' in line else line.find('FIXME')
                })

            # Detectar imports desnecessários (Python)
            if line.strip().startswith('import ') and 'unused' in line.lower():
                issues.append({
                    "type": "import",
                    "severity": "warning",
                    "message": "Import possivelmente não utilizado",
                    "line": i,
                    "suggestion": "Remover import se não utilizado"
                })

        return issues

    def _generate_suggestions(self, content: str, issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Gera sugestões de melhorias"""
        suggestions = []

        # Sugestões baseadas em issues
        style_issues = [i for i in issues if i['type'] == 'style']
        if style_issues:
            suggestions.append({
                "type": "formatting",
                "priority": "medium",
                "title": "Aplicar formatação automática",
                "description": "Execute um formatador como Black ou Prettier",
                "action": "format_code"
            })

        # Sugestões de refatoração
        if content.count('def ') > 10:
            suggestions.append({
                "type": "refactor",
                "priority": "low",
                "title": "Considere dividir em módulos",
                "description": "Arquivo com muitas funções pode ser dividido",
                "action": "split_module"
            })

        # Sugestões de performance
        if 'for' in content and 'for' in content.replace(content.split('for')[0], ''):
            suggestions.append({
                "type": "performance",
                "priority": "medium",
                "title": "Otimizar loops aninhados",
                "description": "Considere usar compreensões ou algoritmos mais eficientes",
                "action": "optimize_loops"
            })

        return suggestions

    def _calculate_metrics(self, content: str) -> Dict[str, Any]:
        """Calcula métricas do código"""
        lines = content.split('\n')

        return {
            "total_lines": len(lines),
            "code_lines": len([l for l in lines if l.strip() and not l.strip().startswith('#')]),
            "comment_lines": len([l for l in lines if l.strip().startswith('#')]),
            "blank_lines": len([l for l in lines if not l.strip()]),
            "max_line_length": max(len(l) for l in lines) if lines else 0,
            "avg_line_length": sum(len(l) for l in lines) / len(lines) if lines else 0,
            "complexity_estimate": content.count('if') + content.count('for') + content.count('while'),
            "function_count": content.count('def '),
            "class_count": content.count('class ')
        }

    def _get_contextual_info(self, analysis: CodeAnalysisResult, position: Dict[str, int]) -> Optional[Dict[str, Any]]:
        """Obtém informações contextuais baseadas na posição do cursor"""
        line_number = position.get('line', 0)

        # Buscar issues na linha atual
        current_line_issues = [
            issue for issue in analysis.issues
            if issue.get('line') == line_number
        ]

        if current_line_issues or line_number % 10 == 0:  # Simulação
            return {
                "line": line_number,
                "issues": current_line_issues,
                "suggestions": [
                    s for s in analysis.suggestions
                    if s.get('priority') == 'high'
                ],
                "metrics_summary": {
                    "complexity_at_line": min(line_number // 10, 5),
                    "maintenance_tip": "Esta área do código parece estar bem estruturada"
                }
            }

        return None

    def _send_analysis_result(self, request_id: str, result: CodeAnalysisResult):
        """Envia resultado de análise para IDE"""
        message = IDEMessage(
            id=request_id,
            type="analysis_result",
            command="show_analysis",
            data={
                "file_path": result.file_path,
                "issues": result.issues,
                "suggestions": result.suggestions,
                "metrics": result.metrics,
                "timestamp": result.timestamp.isoformat()
            },
            timestamp=datetime.now()
        )

        # Enviar para todos os IDEs conectados
        for ide_type, communicator in self.communicators.items():
            if communicator.is_connected():
                communicator.send_message(message)

    def _send_contextual_info(self, file_path: str, info: Dict[str, Any]):
        """Envia informações contextuais para IDE"""
        message = IDEMessage(
            id=f"context_{int(time.time())}",
            type="contextual_info",
            command="show_context",
            data={
                "file_path": file_path,
                "context": info
            },
            timestamp=datetime.now()
        )

        for ide_type, communicator in self.communicators.items():
            if communicator.is_connected():
                communicator.send_message(message)

    def apply_suggestion(self, file_path: str, suggestion_id: str) -> bool:
        """Aplica sugestão automaticamente"""
        try:
            # Simulação de aplicação de sugestão
            print(f"🔧 Aplicando sugestão {suggestion_id} em {file_path}")

            # Em implementação real, modificaria o arquivo
            message = IDEMessage(
                id=f"apply_{suggestion_id}",
                type="suggestion_applied",
                command="apply_fix",
                data={
                    "file_path": file_path,
                    "suggestion_id": suggestion_id,
                    "status": "success"
                },
                timestamp=datetime.now()
            )

            for communicator in self.communicators.values():
                if communicator.is_connected():
                    communicator.send_message(message)

            return True

        except Exception as e:
            print(f"❌ Erro ao aplicar sugestão: {e}")
            return False

    def generate_ide_plugin(self, ide_type: str, output_dir: str) -> bool:
        """Gera plugin específico para IDE"""
        try:
            plugin_dir = Path(output_dir) / f"quimera_{ide_type}_plugin"
            plugin_dir.mkdir(parents=True, exist_ok=True)

            if ide_type == 'vscode':
                self._generate_vscode_plugin(plugin_dir)
            elif ide_type == 'intellij':
                self._generate_intellij_plugin(plugin_dir)
            elif ide_type == 'sublime':
                self._generate_sublime_plugin(plugin_dir)
            else:
                return False

            print(f"✅ Plugin para {ide_type.upper()} gerado em {plugin_dir}")
            return True

        except Exception as e:
            print(f"❌ Erro ao gerar plugin: {e}")
            return False

    def _generate_vscode_plugin(self, plugin_dir: Path):
        """Gera plugin para VSCode"""
        # package.json
        package_json = {
            "name": "quimera-analyzer",
            "displayName": "Quimera Code Analyzer",
            "description": "Advanced code analysis with Quimera",
            "version": "1.0.0",
            "engines": {"vscode": "^1.60.0"},
            "categories": ["Linters", "Other"],
            "activationEvents": ["*"],
            "main": "./out/extension.js",
            "contributes": {
                "commands": [
                    {
                        "command": "quimera.analyze",
                        "title": "Analyze with Quimera"
                    },
                    {
                        "command": "quimera.applyFix",
                        "title": "Apply Quimera Fix"
                    }
                ],
                "keybindings": [
                    {
                        "command": "quimera.analyze",
                        "key": "ctrl+shift+q",
                        "when": "editorTextFocus"
                    }
                ]
            },
            "scripts": {
                "compile": "tsc -p ./",
                "watch": "tsc -watch -p ./"
            },
            "devDependencies": {
                "@types/vscode": "^1.60.0",
                "typescript": "^4.4.0"
            }
        }

        with open(plugin_dir / "package.json", 'w') as f:
            json.dump(package_json, f, indent=2)

        # Extension TypeScript
        extension_ts = '''
import * as vscode from 'vscode';
import * as http from 'http';

export function activate(context: vscode.ExtensionContext) {
    console.log('Quimera extension is now active!');

    const quimeraPort = 8765;

    // Comando para análise
    let analyzeCommand = vscode.commands.registerCommand('quimera.analyze', () => {
        const editor = vscode.window.activeTextEditor;
        if (editor) {
            analyzeDocument(editor.document);
        }
    });

    // Comando para aplicar correção
    let applyFixCommand = vscode.commands.registerCommand('quimera.applyFix', () => {
        vscode.window.showInformationMessage('Aplicando correção Quimera...');
    });

    // Listener para mudanças no documento
    let changeListener = vscode.workspace.onDidChangeTextDocument((event) => {
        if (event.document === vscode.window.activeTextEditor?.document) {
            // Análise automática após 2 segundos de inatividade
            setTimeout(() => analyzeDocument(event.document), 2000);
        }
    });

    context.subscriptions.push(analyzeCommand, applyFixCommand, changeListener);

    function analyzeDocument(document: vscode.TextDocument) {
        const message = {
            id: Date.now().toString(),
            type: 'analysis_request',
            command: 'analyze_file',
            data: {
                file_path: document.fileName,
                content: document.getText()
            }
        };

        // Enviar para servidor Quimera
        sendToQuimera(message);
    }

    function sendToQuimera(message: any) {
        const postData = JSON.stringify(message);

        const options = {
            hostname: 'localhost',
            port: quimeraPort,
            path: '/analyze',
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(postData)
            }
        };

        const req = http.request(options, (res) => {
            let data = '';
            res.on('data', (chunk) => data += chunk);
            res.on('end', () => {
                try {
                    const result = JSON.parse(data);
                    showAnalysisResult(result);
                } catch (e) {
                    console.error('Erro ao parsear resposta:', e);
                }
            });
        });

        req.on('error', (e) => {
            console.error('Erro ao conectar com Quimera:', e);
        });

        req.write(postData);
        req.end();
    }

    function showAnalysisResult(result: any) {
        if (result.issues && result.issues.length > 0) {
            const message = `Quimera encontrou ${result.issues.length} problema(s)`;
            vscode.window.showWarningMessage(message);

            // Adicionar decorações no editor
            const editor = vscode.window.activeTextEditor;
            if (editor) {
                const decorations = result.issues.map((issue: any) => ({
                    range: new vscode.Range(issue.line - 1, 0, issue.line - 1, 1000),
                    hoverMessage: issue.message
                }));

                const decorationType = vscode.window.createTextEditorDecorationType({
                    backgroundColor: 'rgba(255, 255, 0, 0.3)',
                    border: '1px solid yellow'
                });

                editor.setDecorations(decorationType, decorations);
            }
        }
    }
}

export function deactivate() {}
'''

        # Criar diretório src e escrever arquivo
        src_dir = plugin_dir / "src"
        src_dir.mkdir(exist_ok=True)

        with open(src_dir / "extension.ts", 'w') as f:
            f.write(extension_ts)

        # tsconfig.json
        tsconfig = {
            "compilerOptions": {
                "module": "commonjs",
                "target": "es6",
                "outDir": "out",
                "lib": ["es6"],
                "sourceMap": True,
                "rootDir": "src",
                "strict": True
            },
            "exclude": ["node_modules", ".vscode-test"]
        }

        with open(plugin_dir / "tsconfig.json", 'w') as f:
            json.dump(tsconfig, f, indent=2)

    def _generate_intellij_plugin(self, plugin_dir: Path):
        """Gera plugin para IntelliJ"""
        # Plugin.xml básico
        plugin_xml = '''
<idea-plugin>
    <id>com.quimera.analyzer</id>
    <name>Quimera Analyzer</name>
    <version>1.0.0</version>
    <vendor email="support@quimera.com" url="http://www.quimera.com">Quimera</vendor>

    <description><![CDATA[
        Advanced code analysis with Quimera system
    ]]></description>

    <depends>com.intellij.modules.platform</depends>

    <extensions defaultExtensionNs="com.intellij">
        <inspectionToolProvider implementation="com.quimera.analyzer.QuimeraInspectionProvider"/>
        <annotator language="Python" implementationClass="com.quimera.analyzer.QuimeraAnnotator"/>
    </extensions>

    <actions>
        <action id="QuimeraAnalyze" class="com.quimera.analyzer.AnalyzeAction" text="Analyze with Quimera">
            <keyboard-shortcut keymap="$default" first-keystroke="ctrl shift Q"/>
        </action>
    </actions>
</idea-plugin>
'''

        with open(plugin_dir / "plugin.xml", 'w') as f:
            f.write(plugin_xml)

    def _generate_sublime_plugin(self, plugin_dir: Path):
        """Gera plugin para Sublime Text"""
        # Plugin Python
        plugin_py = '''
import sublime
import sublime_plugin
import json
import urllib.request
import threading

class QuimeraAnalyzeCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        content = self.view.substr(sublime.Region(0, self.view.size()))
        file_path = self.view.file_name()

        if file_path:
            threading.Thread(target=self.analyze_async, args=(file_path, content)).start()

    def analyze_async(self, file_path, content):
        try:
            data = {
                'id': str(hash(file_path)),
                'type': 'analysis_request',
                'command': 'analyze_file',
                'data': {
                    'file_path': file_path,
                    'content': content
                }
            }

            req = urllib.request.Request(
                'http://localhost:8765/analyze',
                data=json.dumps(data).encode(),
                headers={'Content-Type': 'application/json'}
            )

            response = urllib.request.urlopen(req)
            result = json.loads(response.read().decode())

            sublime.set_timeout(lambda: self.show_result(result), 0)

        except Exception as e:
            sublime.set_timeout(lambda: sublime.message_dialog(f"Erro Quimera: {e}"), 0)

    def show_result(self, result):
        if result.get('issues'):
            message = f"Quimera encontrou {len(result['issues'])} problema(s)"
            sublime.message_dialog(message)

class QuimeraListener(sublime_plugin.EventListener):
    def on_modified_async(self, view):
        # Análise automática após modificação
        if view.file_name():
            sublime.set_timeout(lambda: self.delayed_analysis(view), 2000)

    def delayed_analysis(self, view):
        view.run_command('quimera_analyze')
'''

        with open(plugin_dir / "QuimeraAnalyzer.py", 'w') as f:
            f.write(plugin_py)

    def get_integration_status(self) -> Dict[str, Any]:
        """Obtém status das integrações"""
        status = {}

        for ide_type, communicator in self.communicators.items():
            status[ide_type] = {
                "connected": communicator.is_connected(),
                "last_message": None,  # Implementar timestamp da última mensagem
                "active_sessions": len([s for s in self.active_sessions.values() if s.get('ide_type') == ide_type])
            }

        return {
            "integrations": status,
            "total_active_sessions": len(self.active_sessions),
            "cache_size": len(self.analysis_cache),
            "settings": {
                "auto_analysis": self.auto_analysis,
                "real_time_feedback": self.real_time_feedback,
                "analysis_interval": self.analysis_interval
            }
        }

def demo_ide_integration():
    """Demonstração do sistema de integração com IDEs"""
    print("🔌 QUIMERA ADVANCED IDE INTEGRATION")
    print("=" * 50)

    manager = IDEIntegrationManager()

    # Iniciar integração com VSCode
    print("🚀 Iniciando integração com VSCode...")
    success = manager.start_integration('vscode')

    if success:
        print("✅ Integração iniciada com sucesso!")

        # Simular análise de arquivo
        sample_code = '''
def example_function():
            # Implementation: connect to IDE via Language Server Protocol
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect(('localhost', 9876))
            sock.close()
            return True
        except Exception:
            return False
    very_long_line_that_exceeds_the_recommended_120_character_limit_and_should_be_flagged_by_the_analyzer_as_a_style_issue = True

    for i in range(100):
        for j in range(100):  # Nested loop detected
            print(i * j)

    return very_long_line_that_exceeds_the_recommended_120_character_limit_and_should_be_flagged_by_the_analyzer_as_a_style_issue

class ExampleClass:
    def method1(self): pass
    def method2(self): pass
    def method3(self): pass
    def method4(self): pass
    def method5(self): pass
    def method6(self): pass
    def method7(self): pass
    def method8(self): pass
    def method9(self): pass
    def method10(self): pass
    def method11(self): pass  # Many methods - suggest module split
'''

        print("\n📄 Analisando código de exemplo...")
        result = manager._analyze_file_content("example.py", sample_code)

        print(f"\n📊 RESULTADO DA ANÁLISE")
        print(f"Issues encontrados: {len(result.issues)}")
        print(f"Sugestões geradas: {len(result.suggestions)}")

        print("\n⚠️  ISSUES DETECTADOS:")
        for issue in result.issues[:5]:  # Mostrar apenas os 5 primeiros
            print(f"  {issue['severity'].upper()}: {issue['message']} (linha {issue['line']})")

        print("\n💡 SUGESTÕES:")
        for suggestion in result.suggestions:
            print(f"  {suggestion['priority'].upper()}: {suggestion['title']}")
            print(f"    {suggestion['description']}")

        print(f"\n📈 MÉTRICAS:")
        for metric, value in result.metrics.items():
            print(f"  {metric}: {value}")

        # Gerar plugins
        print(f"\n🔧 Gerando plugins...")
        temp_dir = tempfile.mkdtemp()

        for ide in ['vscode', 'intellij', 'sublime']:
            success = manager.generate_ide_plugin(ide, temp_dir)
            if success:
                print(f"  ✅ Plugin {ide.upper()} gerado")

        # Status das integrações
        print(f"\n📊 STATUS DAS INTEGRAÇÕES")
        status = manager.get_integration_status()

        for ide, info in status['integrations'].items():
            status_icon = "🟢" if info['connected'] else "🔴"
            print(f"  {status_icon} {ide.upper()}: {'Conectado' if info['connected'] else 'Desconectado'}")

        print(f"\nSessões ativas: {status['total_active_sessions']}")
        print(f"Cache de análises: {status['cache_size']} arquivos")

        print(f"\n⚙️  CONFIGURAÇÕES:")
        for setting, value in status['settings'].items():
            print(f"  {setting}: {value}")

        print(f"\n📁 Plugins gerados em: {temp_dir}")

    else:
        print("❌ Falha ao iniciar integração")

    print("\n✅ Demonstração concluída!")

if __name__ == "__main__":
    demo_ide_integration()