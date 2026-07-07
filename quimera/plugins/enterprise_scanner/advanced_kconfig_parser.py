#!/usr/bin/env python3
"""
Advanced Kconfig Parser using Lark
Parses Kconfig files with full grammar support for accurate dependency analysis
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Set, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import logging

try:
    from lark import Lark, Transformer, v_args, Tree, Token
    LARK_AVAILABLE = True
except ImportError:
    LARK_AVAILABLE = False
    print("Warning: Lark not available, falling back to regex parsing")

logger = logging.getLogger(__name__)


@dataclass
class KconfigSymbol:
    """Represents a Kconfig symbol with all its properties"""
    name: str
    type: str = "unknown"  # bool, tristate, string, hex, int
    prompt: Optional[str] = None
    help_text: Optional[str] = None
    default_values: List[Tuple[str, Optional[str]]] = field(default_factory=list)  # (value, condition)
    depends_on: List[str] = field(default_factory=list)
    selects: List[Tuple[str, Optional[str]]] = field(default_factory=list)  # (symbol, condition)
    implies: List[Tuple[str, Optional[str]]] = field(default_factory=list)  # (symbol, condition)
    ranges: List[Tuple[str, str, Optional[str]]] = field(default_factory=list)  # (min, max, condition)
    location: Optional[str] = None  # file:line
    menu_path: List[str] = field(default_factory=list)  # menu hierarchy
    choice_group: Optional[str] = None
    is_visible: bool = True


@dataclass
class KconfigMenu:
    """Represents a Kconfig menu"""
    title: str
    depends_on: List[str] = field(default_factory=list)
    visible_if: Optional[str] = None
    location: Optional[str] = None


@dataclass
class KconfigChoice:
    """Represents a Kconfig choice group"""
    name: Optional[str] = None
    prompt: Optional[str] = None
    default: Optional[str] = None
    depends_on: List[str] = field(default_factory=list)
    symbols: List[str] = field(default_factory=list)
    location: Optional[str] = None


class KconfigTransformer(Transformer):
    """Transforms Lark parse tree into Kconfig data structures"""

    def __init__(self):
        self.symbols: Dict[str, KconfigSymbol] = {}
        self.menus: List[KconfigMenu] = []
        self.choices: List[KconfigChoice] = []
        self.current_menu_path: List[str] = []
        self.current_choice: Optional[KconfigChoice] = None
        self.mainmenu_title: Optional[str] = None

    def start(self, items):
        return {
            'symbols': self.symbols,
            'menus': self.menus,
            'choices': self.choices,
            'mainmenu': self.mainmenu_title
        }

    def config_stmt(self, items):
        symbol_name = str(items[0])
        symbol = KconfigSymbol(name=symbol_name, menu_path=self.current_menu_path.copy())

        if self.current_choice:
            symbol.choice_group = self.current_choice.name
            self.current_choice.symbols.append(symbol_name)

        # Process config options
        for item in items[1:]:
            if isinstance(item, dict):
                self._apply_config_option(symbol, item)

        self.symbols[symbol_name] = symbol
        return symbol

    def menuconfig_stmt(self, items):
        # Menuconfig is like config but also creates a menu
        symbol = self.config_stmt(items)
        symbol.type = "bool"  # menuconfig is typically bool
        return symbol

    def menu_stmt(self, items):
        title = self._extract_string(items[0])
        menu = KconfigMenu(title=title)

        self.current_menu_path.append(title)

        # Process menu options and statements
        for item in items[1:]:
            if isinstance(item, dict) and 'depends_on' in item:
                menu.depends_on.extend(item['depends_on'])
            elif isinstance(item, dict) and 'visible_if' in item:
                menu.visible_if = item['visible_if']

        self.menus.append(menu)
        return menu

    def choice_stmt(self, items):
        choice = KconfigChoice()
        self.current_choice = choice

        # Process choice options
        for item in items:
            if isinstance(item, dict):
                if 'prompt' in item:
                    choice.prompt = item['prompt']
                elif 'default' in item:
                    choice.default = item['default']
                elif 'depends_on' in item:
                    choice.depends_on.extend(item['depends_on'])

        self.choices.append(choice)
        self.current_choice = None
        return choice

    def mainmenu_stmt(self, items):
        self.mainmenu_title = self._extract_string(items[0])
        return self.mainmenu_title

    def type_option(self, items):
        type_name = str(items[0])
        result = {'type': type_name}

        if len(items) > 1:
            # Has prompt
            result['prompt'] = self._extract_string(items[1])

        return result

    def prompt_option(self, items):
        return {'prompt': self._extract_string(items[0])}

    def default_option(self, items):
        value = str(items[0])
        condition = str(items[1]) if len(items) > 1 else None
        return {'default': (value, condition)}

    def depends_option(self, items):
        return {'depends_on': [str(items[0])]}

    def select_option(self, items):
        symbol = str(items[0])
        condition = str(items[1]) if len(items) > 1 else None
        return {'select': (symbol, condition)}

    def imply_option(self, items):
        symbol = str(items[0])
        condition = str(items[1]) if len(items) > 1 else None
        return {'imply': (symbol, condition)}

    def range_option(self, items):
        min_val = str(items[0])
        max_val = str(items[1])
        condition = str(items[2]) if len(items) > 2 else None
        return {'range': (min_val, max_val, condition)}

    def help_option(self, items):
        help_lines = []
        for item in items:
            if isinstance(item, list):
                help_lines.extend(str(line) for line in item)
        return {'help': '\n'.join(help_lines)}

    def help_text(self, items):
        return [str(item) for item in items]

    def _apply_config_option(self, symbol: KconfigSymbol, option: dict):
        """Apply a parsed config option to a symbol"""
        if 'type' in option:
            symbol.type = option['type']
        if 'prompt' in option:
            symbol.prompt = option['prompt']
        if 'help' in option:
            symbol.help_text = option['help']
        if 'default' in option:
            symbol.default_values.append(option['default'])
        if 'depends_on' in option:
            symbol.depends_on.extend(option['depends_on'])
        if 'select' in option:
            symbol.selects.append(option['select'])
        if 'imply' in option:
            symbol.implies.append(option['imply'])
        if 'range' in option:
            symbol.ranges.append(option['range'])

    def _extract_string(self, item):
        """Extract string value from quoted string token"""
        if isinstance(item, Token):
            return str(item).strip('"')
        return str(item).strip('"')


class AdvancedKconfigParser:
    """Advanced Kconfig parser with full grammar support"""

    def __init__(self):
        self.parser = None
        self.transformer = None
        self._init_parser()

    def _init_parser(self):
        """Initialize the Lark parser"""
        if not LARK_AVAILABLE:
            logger.warning("Lark not available, using fallback regex parser")
            return

        try:
            # Load grammar from file
            grammar_path = Path(__file__).parent / "kconfig_grammar.lark"
            if not grammar_path.exists():
                # Fallback to inline grammar
                grammar = self._get_inline_grammar()
            else:
                with open(grammar_path, 'r') as f:
                    grammar = f.read()

            self.parser = Lark(grammar, parser='lalr', transformer=KconfigTransformer())
            logger.info("Advanced Kconfig parser initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Lark parser: {e}")
            self.parser = None

    def _get_inline_grammar(self):
        """Fallback inline grammar if file not found"""
        return '''
        start: statement*

        statement: config_stmt | menu_stmt | NEWLINE | COMMENT

        config_stmt: "config" SYMBOL NEWLINE config_option*

        menu_stmt: "menu" STRING NEWLINE statement* "endmenu" NEWLINE

        config_option: type_option | prompt_option | default_option | depends_option | help_option

        type_option: ("bool" | "tristate" | "string" | "hex" | "int") [STRING] NEWLINE

        prompt_option: "prompt" STRING NEWLINE

        default_option: "default" SYMBOL NEWLINE

        depends_option: "depends" "on" SYMBOL NEWLINE

        help_option: "help" NEWLINE help_text

        help_text: (HELP_LINE NEWLINE)*

        SYMBOL: /[A-Za-z_][A-Za-z0-9_]*/
        STRING: /"[^"]*"/
        HELP_LINE: /[ \\t]+[^\\n]*/
        COMMENT: /#[^\\n]*/
        NEWLINE: /\\n/

        %import common.WS_INLINE
        %ignore WS_INLINE
        '''

    def parse_file(self, file_path: str) -> Dict[str, Any]:
        """Parse a single Kconfig file"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            return self.parse_content(content, file_path)

        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            return self._fallback_parse_file(file_path)

    def parse_content(self, content: str, source_file: str = None) -> Dict[str, Any]:
        """Parse Kconfig content"""
        if self.parser is None:
            return self._fallback_parse_content(content, source_file)

        try:
            # Preprocess content to handle some edge cases
            content = self._preprocess_content(content)

            # Parse with Lark
            tree = self.parser.parse(content)
            result = tree

            # Add source file information
            if source_file and isinstance(result, dict):
                for symbol in result.get('symbols', {}).values():
                    if hasattr(symbol, 'location') and symbol.location is None:
                        symbol.location = source_file

            return result

        except Exception as e:
            logger.warning(f"Lark parsing failed for {source_file}: {e}, falling back to regex")
            return self._fallback_parse_content(content, source_file)

    def _preprocess_content(self, content: str) -> str:
        """Preprocess Kconfig content to handle edge cases"""
        # Remove comments that might interfere with parsing
        lines = content.split('\n')
        processed_lines = []

        for line in lines:
            # Handle line continuations
            if line.endswith('\\'):
                line = line[:-1] + ' '

            # Normalize whitespace in help sections
            if line.strip().startswith('help') or line.strip().startswith('---help---'):
                processed_lines.append('help')
                continue

            processed_lines.append(line)

        return '\n'.join(processed_lines)

    def _fallback_parse_file(self, file_path: str) -> Dict[str, Any]:
        """Fallback regex-based parsing when Lark fails"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            return self._fallback_parse_content(content, file_path)

        except Exception as e:
            logger.error(f"Fallback parsing also failed for {file_path}: {e}")
            return {'symbols': {}, 'menus': [], 'choices': []}

    def _fallback_parse_content(self, content: str, source_file: str = None) -> Dict[str, Any]:
        """Regex-based fallback parser"""
        symbols = {}
        menus = []

        # Basic regex patterns
        config_pattern = r'^config\s+([A-Z_][A-Z0-9_]*)'
        type_pattern = r'^\s*(bool|tristate|string|hex|int)(?:\s+"([^"]*)")?'
        prompt_pattern = r'^\s*prompt\s+"([^"]*)"'
        default_pattern = r'^\s*default\s+([^\s]+)'
        depends_pattern = r'^\s*depends\s+on\s+(.+)'
        select_pattern = r'^\s*select\s+([A-Z_][A-Z0-9_]*)'
        help_pattern = r'^\s*help\s*$'
        menu_pattern = r'^menu\s+"([^"]*)"'

        lines = content.split('\n')
        current_symbol = None
        in_help = False
        help_lines = []

        for i, line in enumerate(lines):
            line_stripped = line.strip()

            if not line_stripped or line_stripped.startswith('#'):
                continue

            # Config statement
            config_match = re.match(config_pattern, line)
            if config_match:
                if current_symbol and in_help:
                    current_symbol.help_text = '\n'.join(help_lines)

                symbol_name = config_match.group(1)
                current_symbol = KconfigSymbol(name=symbol_name)
                if source_file:
                    current_symbol.location = f"{source_file}:{i+1}"
                symbols[symbol_name] = current_symbol
                in_help = False
                help_lines = []
                continue

            if current_symbol is None:
                continue

            # Type
            type_match = re.match(type_pattern, line)
            if type_match:
                current_symbol.type = type_match.group(1)
                if type_match.group(2):
                    current_symbol.prompt = type_match.group(2)
                continue

            # Prompt
            prompt_match = re.match(prompt_pattern, line)
            if prompt_match:
                current_symbol.prompt = prompt_match.group(1)
                continue

            # Default
            default_match = re.match(default_pattern, line)
            if default_match:
                current_symbol.default_values.append((default_match.group(1), None))
                continue

            # Depends on
            depends_match = re.match(depends_pattern, line)
            if depends_match:
                current_symbol.depends_on.append(depends_match.group(1))
                continue

            # Select
            select_match = re.match(select_pattern, line)
            if select_match:
                current_symbol.selects.append((select_match.group(1), None))
                continue

            # Help
            help_match = re.match(help_pattern, line)
            if help_match:
                in_help = True
                continue

            # Help content
            if in_help and line.startswith('\t'):
                help_lines.append(line[1:])  # Remove tab
                continue
            elif in_help:
                # End of help section
                current_symbol.help_text = '\n'.join(help_lines)
                in_help = False
                help_lines = []

        # Handle last symbol's help
        if current_symbol and in_help:
            current_symbol.help_text = '\n'.join(help_lines)

        return {
            'symbols': symbols,
            'menus': menus,
            'choices': []
        }

    def parse_directory(self, kernel_path: str) -> Dict[str, Any]:
        """Parse all Kconfig files in a kernel directory"""
        all_symbols = {}
        all_menus = []
        all_choices = []

        kconfig_files = self._find_kconfig_files(kernel_path)

        for kconfig_file in kconfig_files:
            try:
                result = self.parse_file(kconfig_file)

                # Merge results
                all_symbols.update(result.get('symbols', {}))
                all_menus.extend(result.get('menus', []))
                all_choices.extend(result.get('choices', []))

            except Exception as e:
                logger.warning(f"Failed to parse {kconfig_file}: {e}")

        return {
            'symbols': all_symbols,
            'menus': all_menus,
            'choices': all_choices,
            'total_files': len(kconfig_files)
        }

    def _find_kconfig_files(self, kernel_path: str) -> List[str]:
        """Find all Kconfig files in kernel directory"""
        kconfig_files = []
        kernel_path = Path(kernel_path)

        if not kernel_path.exists():
            return kconfig_files

        # Common Kconfig file patterns
        patterns = [
            "Kconfig",
            "Kconfig.*",
            "*/Kconfig",
            "*/Kconfig.*"
        ]

        for pattern in patterns:
            kconfig_files.extend(kernel_path.glob(pattern))

        # Convert to strings and sort
        kconfig_files = [str(f) for f in kconfig_files if f.is_file()]
        kconfig_files.sort()

        return kconfig_files

    def build_dependency_graph(self, symbols: Dict[str, KconfigSymbol]) -> Dict[str, Set[str]]:
        """Build dependency graph from parsed symbols"""
        dependency_graph = defaultdict(set)

        for symbol_name, symbol in symbols.items():
            # Add dependencies from 'depends on'
            for dep in symbol.depends_on:
                # Parse dependency expression to extract symbol names
                dep_symbols = self._extract_symbols_from_expression(dep)
                for dep_symbol in dep_symbols:
                    dependency_graph[symbol_name].add(dep_symbol)

            # Add reverse dependencies from 'select'
            for selected_symbol, condition in symbol.selects:
                dependency_graph[selected_symbol].add(symbol_name)
                if condition:
                    condition_symbols = self._extract_symbols_from_expression(condition)
                    for cond_symbol in condition_symbols:
                        dependency_graph[symbol_name].add(cond_symbol)

        return dict(dependency_graph)

    def _extract_symbols_from_expression(self, expression: str) -> Set[str]:
        """Extract symbol names from a dependency expression"""
        # Simple regex to find symbol names (uppercase with underscores)
        symbol_pattern = r'\b[A-Z_][A-Z0-9_]*\b'
        symbols = set(re.findall(symbol_pattern, expression))

        # Filter out common keywords that aren't symbols
        keywords = {'AND', 'OR', 'NOT', 'IF', 'THEN', 'ELSE', 'TRUE', 'FALSE'}
        symbols = symbols - keywords

        return symbols


# Test function
def test_parser():
    """Test the advanced Kconfig parser"""
    parser = AdvancedKconfigParser()

    # Test with sample Kconfig content
    sample_content = '''
config EXAMPLE_BOOL
    bool "Example boolean option"
    default y
    help
      This is an example boolean configuration option.
      It demonstrates the parser capabilities.

config EXAMPLE_TRISTATE
    tristate "Example tristate option"
    depends on EXAMPLE_BOOL
    select SOME_OTHER_OPTION
    help
      This is an example tristate option that depends on EXAMPLE_BOOL.

menu "Example Menu"
    depends on EXAMPLE_BOOL

config MENU_OPTION
    bool "Option inside menu"
    default n

endmenu
'''

    result = parser.parse_content(sample_content, "test.kconfig")

    print("Parsed symbols:")
    for name, symbol in result.get('symbols', {}).items():
        print(f"  {name}: type={symbol.type}, prompt='{symbol.prompt}'")
        if symbol.depends_on:
            print(f"    depends on: {symbol.depends_on}")
        if symbol.selects:
            print(f"    selects: {symbol.selects}")

    print(f"\nParsed menus: {len(result.get('menus', []))}")

    # Test dependency graph
    dependency_graph = parser.build_dependency_graph(result.get('symbols', {}))
    print(f"\nDependency graph: {dict(dependency_graph)}")


if __name__ == "__main__":
    test_parser()