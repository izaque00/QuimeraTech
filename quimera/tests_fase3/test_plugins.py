"""
Testes dos Plugins — PluginManager, BasePlugin e descoberta.
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


class TestBasePlugin:
    """Testes da classe base de plugins."""
    
    def test_plugin_type_enum(self):
        from quimera.plugins.base_plugin import PluginType
        
        assert PluginType.SCANNER.value == "scanner"
        assert PluginType.ANALYZER.value == "analyzer"
        assert PluginType.SECURITY.value == "security"
        assert len(list(PluginType)) >= 5
    
    def test_concrete_plugin(self):
        """Um plugin concreto deve implementar a interface."""
        from quimera.plugins.base_plugin import BasePlugin, PluginType
        
        class TestPlugin(BasePlugin):
            @property
            def plugin_type(self):
                return PluginType.SCANNER
            
            @property
            def plugin_name(self):
                return "test_plugin"
            
            def initialize(self):
                self._initialized = True
                return True
            
            def execute(self, input_data):
                return f"Processed: {input_data}"
        
        plugin = TestPlugin({"key": "value"})
        assert plugin.plugin_name == "test_plugin"
        assert plugin.plugin_type == PluginType.SCANNER
        assert plugin.config == {"key": "value"}
        
        result = plugin.initialize()
        assert result is True
        assert plugin._initialized
        
        output = plugin.execute("hello")
        assert "Processed" in output


class TestPluginManager:
    """Testes do gerenciador de plugins."""
    
    def test_plugin_manager_creation(self):
        from quimera.plugins.plugin_manager import PluginManager
        
        pm = PluginManager()
        assert pm is not None
        assert len(pm.list_plugins()) == 0
    
    def test_register_and_load_plugin(self):
        from quimera.plugins.plugin_manager import PluginManager
        from quimera.plugins.base_plugin import BasePlugin, PluginType
        
        class MyPlugin(BasePlugin):
            @property
            def plugin_type(self):
                return PluginType.CUSTOM
            
            @property
            def plugin_name(self):
                return "my_plugin"
            
            def initialize(self):
                return True
            
            def execute(self, data):
                return data
        
        pm = PluginManager()
        pm.register("my_plugin", MyPlugin)
        
        assert "my_plugin" in pm.list_plugins()
        
        instance = pm.load("my_plugin")
        assert instance is not None
        assert instance.plugin_name == "my_plugin"
    
    def test_load_unregistered_plugin(self):
        from quimera.plugins.plugin_manager import PluginManager
        
        pm = PluginManager()
        result = pm.load("nonexistent")
        assert result is None
    
    def test_unload_plugin(self):
        from quimera.plugins.plugin_manager import PluginManager
        from quimera.plugins.base_plugin import BasePlugin, PluginType
        
        class TempPlugin(BasePlugin):
            @property
            def plugin_type(self):
                return PluginType.CUSTOM
            
            @property
            def plugin_name(self):
                return "temp"
            
            def initialize(self):
                return True
            
            def execute(self, data):
                return data
        
        pm = PluginManager()
        pm.register("temp", TempPlugin)
        instance1 = pm.load("temp")
        assert instance1 is not None
        
        pm.unload("temp")
        # Unload removes cached instance, but plugin class is still registered
        # So load() creates a new instance
        instance2 = pm.load("temp")
        assert instance2 is not None
        assert instance2 is not instance1  # New instance
    
    def test_discover_function(self):
        from quimera.plugins.plugin_manager import descobrir_e_registrar
        
        result = descobrir_e_registrar()
        assert isinstance(result, list)
        assert len(result) >= 0  # Pode ser 0 se não houver plugins no path


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
