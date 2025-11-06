"""
Comprehensive test suite for Plugin Manager functionality.

Includes unit tests, integration tests, and error scenario tests for:
- Plugin discovery and loading
- Plugin instance management
- Plugin synchronization operations
- Error handling for invalid plugins
- State-based plugin lookup
"""

import pytest
import unittest
from unittest.mock import Mock, patch, MagicMock, call
import os
import sys
import inspect

# Import the plugin manager and base plugin
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plugins.plugin_manager import PluginManager
from plugins.base_plugin import BasePlugin


class TestPluginDiscovery(unittest.TestCase):
    """Unit tests for plugin discovery functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_app = Mock()
        self.mock_app.logger = Mock()
        self.mock_db = Mock()
        
        # Create plugin manager without automatic discovery
        self.plugin_manager = PluginManager.__new__(PluginManager)
        self.plugin_manager.app = self.mock_app
        self.plugin_manager.db = self.mock_db
        self.plugin_manager.plugins = {}

    @patch('os.listdir')
    @patch('importlib.import_module')
    @patch('inspect.getmembers')
    def test_discover_plugins_success(self, mock_getmembers, mock_import, mock_listdir):
        """Test successful plugin discovery."""
        # Mock directory listing
        mock_listdir.return_value = [
            'ohio.py',
            'virginia.py', 
            'bigquery_plugin.py',
            'dummy.py',
            'base_plugin.py',  # Should be skipped
            'plugin_manager.py',  # Should be skipped
            '__init__.py',  # Should be skipped
            '.hidden.py'  # Should be skipped
        ]

        # Mock plugin classes
        class MockOhioPlugin(BasePlugin):
            @property
            def name(self):
                return 'ohio'
    
            @property
            def state_code(self):
                return 'OH'
                
            def fetch_polling_places(self, state_code='OH'):
                return []
                
            @property
            def description(self):
                return 'Mock Ohio plugin'
    
        class MockVirginiaPlugin(BasePlugin):
            @property
            def name(self):
                return 'virginia'
    
            @property
            def state_code(self):
                return 'VA'
                
            def fetch_polling_places(self, state_code='VA'):
                return []
                
            @property
            def description(self):
                return 'Mock Virginia plugin'
            
            def get_status(self):
                return {'name': 'virginia', 'state_code': 'VA'}
            
            def sync(self, election_id=None):
                return {'success': True, 'added': 8, 'updated': 3}
        
        class MockDummyPlugin(BasePlugin):
            @property
            def name(self):
                return 'dummy'
            
            @property
            def state_code(self):
                return 'ALL'
            
            def fetch_polling_places(self, state_code='ALL'):
                return []
                
            @property
            def description(self):
                return 'Mock Dummy plugin'
            
            def get_status(self):
                return {'name': 'dummy', 'state_code': 'ALL'}
            
            def sync(self, election_id=None):
                return {'success': True, 'added': 100, 'updated': 0}

        def mock_import_side_effect(module_name):
            if module_name == 'plugins.ohio':
                mock_module = Mock()
                mock_getmembers.return_value = [('MockOhioPlugin', MockOhioPlugin)]
                return mock_module
            elif module_name == 'plugins.virginia':
                mock_module = Mock()
                mock_getmembers.return_value = [('MockVirginiaPlugin', MockVirginiaPlugin)]
                return mock_module
            elif module_name == 'plugins.dummy':
                mock_module = Mock()
                mock_getmembers.return_value = [('MockDummyPlugin', MockDummyPlugin)]
                return mock_module
            else:
                raise ImportError(f"Module {module_name} not found")
        
        mock_import.side_effect = mock_import_side_effect

        # Test discovery
        self.plugin_manager.discover_plugins()

        # Verify plugins were loaded
        self.assertEqual(len(self.plugin_manager.plugins), 3)
        self.assertIn('ohio', self.plugin_manager.plugins)
        self.assertIn('virginia', self.plugin_manager.plugins)
        self.assertIn('dummy', self.plugin_manager.plugins)

        # Test plugin operations
        ohio_plugin = self.plugin_manager.get_plugin('ohio')
        self.assertEqual(ohio_plugin.name, 'ohio')
        self.assertEqual(ohio_plugin.state_code, 'OH')

        va_plugin = self.plugin_manager.get_plugin_by_state('VA')
        self.assertEqual(va_plugin.name, 'virginia')

        # Test listing
        plugin_list = self.plugin_manager.list_plugins()
        self.assertEqual(len(plugin_list), 3)

        # Test sync all
        sync_results = self.plugin_manager.sync_all_plugins()
        self.assertEqual(len(sync_results), 2)  # dummy should be skipped
        self.assertIn('ohio', sync_results)
        self.assertIn('virginia', sync_results)

    def test_plugin_manager_initialization(self):
        """Test plugin manager initialization."""
        # Should call discover_plugins during initialization
        with patch.object(PluginManager, 'discover_plugins') as mock_discover:
            PluginManager(self.mock_app, self.mock_db)
            mock_discover.assert_called_once()

    def test_plugin_manager_logging(self):
        """Test that plugin manager logs appropriately."""
        with patch('plugins.plugin_manager.os.listdir', return_value=[]):
            self.plugin_manager.discover_plugins()
            
            # Should log discovery start and completion
            log_calls = [call.args[0] for call in self.mock_app.logger.info.call_args_list]
            self.assertTrue(any('Discovering plugins' in call for call in log_calls))
            self.assertTrue(any('Discovered 0 plugin(s)' in call for call in log_calls))


class TestPluginManagerErrorScenarios(unittest.TestCase):
    """Error scenario tests for plugin manager."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_app = Mock()
        self.mock_app.logger = Mock()
        self.mock_db = Mock()
        
        # Patch discover_plugins to prevent automatic discovery during initialization
        with patch.object(PluginManager, 'discover_plugins'):
            self.plugin_manager = PluginManager(self.mock_app, self.mock_db)
            # Clear any plugins that might have been loaded
            self.plugin_manager.plugins.clear()

    @patch('plugins.plugin_manager.os.listdir')
    def test_discovery_directory_error(self, mock_listdir):
        """Test handling of directory access errors."""
        mock_listdir.side_effect = PermissionError("Permission denied")
        
        # Should raise PermissionError since os.listdir is not wrapped in try-catch
        with self.assertRaises(PermissionError):
            self.plugin_manager.discover_plugins()

    @patch('plugins.plugin_manager.os.listdir')
    @patch('plugins.plugin_manager.importlib.import_module')
    def test_discovery_corrupted_plugin_file(self, mock_import, mock_listdir):
        """Test handling of corrupted plugin files."""
        mock_listdir.return_value = ['corrupted.py']
        mock_import.side_effect = SyntaxError("Invalid syntax")
        
        self.plugin_manager.discover_plugins()
        
        # Should handle syntax error gracefully
        self.assertEqual(len(self.plugin_manager.plugins), 0)
        self.mock_app.logger.error.assert_called()

    def test_sync_all_with_no_plugins(self):
        """Test sync all with no plugins loaded."""
        self.plugin_manager.plugins = {}
        
        result = self.plugin_manager.sync_all_plugins()
        
        self.assertEqual(result, {})

    def test_plugin_state_conflicts(self):
        """Test handling of plugins with conflicting state codes."""
        # Add two plugins with same state code
        plugin1 = Mock()
        plugin1.name = 'plugin1'
        plugin1.state_code = 'OH'
        
        plugin2 = Mock()
        plugin2.name = 'plugin2'
        plugin2.state_code = 'OH'  # Same state code
        
        self.plugin_manager.plugins = {
            'plugin1': plugin1,
            'plugin2': plugin2
        }
        
        # get_plugin_by_state should return the first one found
        result = self.plugin_manager.get_plugin_by_state('OH')
        self.assertEqual(result, plugin1)

    def test_plugin_name_conflicts(self):
        """Test handling of plugins with conflicting names."""
        # This shouldn't happen in normal operation, but test robustness
        plugin1 = Mock()
        plugin1.name = 'duplicate'
        
        plugin2 = Mock()
        plugin2.name = 'duplicate'  # Same name
        
        # Second plugin should overwrite first in the dictionary
        self.plugin_manager.plugins = {
            'duplicate': plugin1
        }
        self.plugin_manager.plugins['duplicate'] = plugin2
        
        result = self.plugin_manager.get_plugin('duplicate')
        self.assertEqual(result, plugin2)


if __name__ == '__main__':
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestPluginDiscovery,
        TestPluginManagerErrorScenarios
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print(f"\nTest Summary:")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")