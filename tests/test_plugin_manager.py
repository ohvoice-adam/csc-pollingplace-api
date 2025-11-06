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
        self.plugin_manager = PluginManager(self.mock_app, self.mock_db)

    @patch('plugins.plugin_manager.os.listdir')
    @patch('plugins.plugin_manager.importlib.import_module')
    @patch('plugins.plugin_manager.inspect.getmembers')
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

        # Mock successful plugin import and class discovery
        mock_module = Mock()
        mock_import.return_value = mock_module
        
        # Mock plugin classes
        class MockOhioPlugin(BasePlugin):
            @property
            def name(self):
                return 'ohio'
            
            @property
            def state_code(self):
                return 'OH'
        
        class MockVirginiaPlugin(BasePlugin):
            @property
            def name(self):
                return 'virginia'
            
            @property
            def state_code(self):
                return 'VA'
        
        mock_getmembers.return_value = [
            ('MockOhioPlugin', MockOhioPlugin),
            ('BasePlugin', BasePlugin),  # Should be skipped
            ('MockVirginiaPlugin', MockVirginiaPlugin)
        ]

        # Mock plugin instantiation
        with patch.object(MockOhioPlugin, '__init__', return_value=None):
            with patch.object(MockVirginiaPlugin, '__init__', return_value=None):
                self.plugin_manager.discover_plugins()

        # Should have loaded 2 plugins (ohio and virginia)
        self.assertEqual(len(self.plugin_manager.plugins), 2)
        self.assertIn('ohio', self.plugin_manager.plugins)
        self.assertIn('virginia', self.plugin_manager.plugins)

    @patch('plugins.plugin_manager.os.listdir')
    def test_discover_plugins_empty_directory(self, mock_listdir):
        """Test plugin discovery with empty directory."""
        mock_listdir.return_value = []

        self.plugin_manager.discover_plugins()

        self.assertEqual(len(self.plugin_manager.plugins), 0)

    @patch('plugins.plugin_manager.os.listdir')
    @patch('plugins.plugin_manager.importlib.import_module')
    def test_discover_plugins_import_error(self, mock_import, mock_listdir):
        """Test plugin discovery with import error."""
        mock_listdir.return_value = ['broken_plugin.py']
        mock_import.side_effect = ImportError("Module not found")

        self.plugin_manager.discover_plugins()

        # Should handle import error gracefully
        self.assertEqual(len(self.plugin_manager.plugins), 0)
        self.mock_app.logger.error.assert_called()

    @patch('plugins.plugin_manager.os.listdir')
    @patch('plugins.plugin_manager.importlib.import_module')
    @patch('plugins.plugin_manager.inspect.getmembers')
    def test_discover_plugins_name_mismatch(self, mock_getmembers, mock_import, mock_listdir):
        """Test plugin discovery with module name mismatch."""
        mock_listdir.return_value = ['mismatched_plugin.py']
        
        mock_module = Mock()
        mock_import.return_value = mock_module
        
        class MismatchedPlugin(BasePlugin):
            @property
            def name(self):
                return 'different_name'  # Doesn't match filename
        
        mock_getmembers.return_value = [('MismatchedPlugin', MismatchedPlugin)]

        with patch.object(MismatchedPlugin, '__init__', return_value=None):
            self.plugin_manager.discover_plugins()

        # Should skip plugin due to name mismatch
        self.assertEqual(len(self.plugin_manager.plugins), 0)
        self.mock_app.logger.warning.assert_called()

    @patch('plugins.plugin_manager.os.listdir')
    @patch('plugins.plugin_manager.importlib.import_module')
    @patch('plugins.plugin_manager.inspect.getmembers')
    def test_discover_plugins_instantiation_error(self, mock_getmembers, mock_import, mock_listdir):
        """Test plugin discovery with instantiation error."""
        mock_listdir.return_value = ['problematic_plugin.py']
        
        mock_module = Mock()
        mock_import.return_value = mock_module
        
        class ProblematicPlugin(BasePlugin):
            def __init__(self, app, db):
                raise Exception("Initialization failed")
            
            @property
            def name(self):
                return 'problematic'
        
        mock_getmembers.return_value = [('ProblematicPlugin', ProblematicPlugin)]

        self.plugin_manager.discover_plugins()

        # Should handle instantiation error gracefully
        self.assertEqual(len(self.plugin_manager.plugins), 0)
        self.mock_app.logger.error.assert_called()


class TestPluginManagement(unittest.TestCase):
    """Unit tests for plugin management functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_app = Mock()
        self.mock_app.logger = Mock()
        self.mock_db = Mock()
        self.plugin_manager = PluginManager(self.mock_app, self.mock_db)

        # Add mock plugins
        self.mock_plugin1 = Mock()
        self.mock_plugin1.name = 'test1'
        self.mock_plugin1.state_code = 'TS'
        
        self.mock_plugin2 = Mock()
        self.mock_plugin2.name = 'test2'
        self.mock_plugin2.state_code = 'T2'
        
        self.plugin_manager.plugins = {
            'test1': self.mock_plugin1,
            'test2': self.mock_plugin2
        }

    def test_get_plugin_success(self):
        """Test successful plugin retrieval."""
        result = self.plugin_manager.get_plugin('test1')
        
        self.assertEqual(result, self.mock_plugin1)

    def test_get_plugin_not_found(self):
        """Test plugin retrieval with non-existent plugin."""
        with self.assertRaises(KeyError) as context:
            self.plugin_manager.get_plugin('nonexistent')
        
        self.assertIn("Plugin 'nonexistent' not found", str(context.exception))

    def test_list_plugins(self):
        """Test listing all plugins."""
        # Mock plugin get_status method
        self.mock_plugin1.get_status.return_value = {
            'name': 'test1',
            'state_code': 'TS',
            'description': 'Test plugin 1'
        }
        self.mock_plugin2.get_status.return_value = {
            'name': 'test2', 
            'state_code': 'T2',
            'description': 'Test plugin 2'
        }
        
        result = self.plugin_manager.list_plugins()
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['name'], 'test1')
        self.assertEqual(result[1]['name'], 'test2')

    def test_get_plugin_by_state_success(self):
        """Test successful plugin retrieval by state code."""
        result = self.plugin_manager.get_plugin_by_state('TS')
        
        self.assertEqual(result, self.mock_plugin1)

    def test_get_plugin_by_state_not_found(self):
        """Test plugin retrieval by state code with non-existent state."""
        with self.assertRaises(KeyError) as context:
            self.plugin_manager.get_plugin_by_state('XX')
        
        self.assertIn("No plugin found for state 'XX'", str(context.exception))

    def test_get_plugin_by_state_case_insensitive(self):
        """Test plugin retrieval by state code is case insensitive."""
        result = self.plugin_manager.get_plugin_by_state('ts')  # lowercase
        
        self.assertEqual(result, self.mock_plugin1)


class TestPluginSynchronization(unittest.TestCase):
    """Unit tests for plugin synchronization functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_app = Mock()
        self.mock_app.logger = Mock()
        self.mock_db = Mock()
        self.plugin_manager = PluginManager(self.mock_app, self.mock_db)

        # Add mock plugins
        self.mock_plugin1 = Mock()
        self.mock_plugin1.name = 'test1'
        self.mock_plugin1.sync.return_value = {
            'success': True,
            'added': 10,
            'updated': 5,
            'errors': 0
        }
        
        self.mock_plugin2 = Mock()
        self.mock_plugin2.name = 'test2'
        self.mock_plugin2.sync.return_value = {
            'success': True,
            'added': 8,
            'updated': 3,
            'errors': 0
        }
        
        self.dummy_plugin = Mock()
        self.dummy_plugin.name = 'dummy'
        
        self.plugin_manager.plugins = {
            'test1': self.mock_plugin1,
            'test2': self.mock_plugin2,
            'dummy': self.dummy_plugin
        }

    def test_sync_plugin_success(self):
        """Test successful single plugin synchronization."""
        result = self.plugin_manager.sync_plugin('test1')
        
        self.assertEqual(result, self.mock_plugin1.sync.return_value)
        self.mock_plugin1.sync.assert_called_once_with(election_id=None)

    def test_sync_plugin_with_election_id(self):
        """Test plugin synchronization with election ID."""
        election_id = 123
        self.plugin_manager.sync_plugin('test1', election_id=election_id)
        
        self.mock_plugin1.sync.assert_called_once_with(election_id=election_id)

    def test_sync_plugin_not_found(self):
        """Test plugin synchronization with non-existent plugin."""
        with self.assertRaises(KeyError):
            self.plugin_manager.sync_plugin('nonexistent')

    def test_sync_plugin_error(self):
        """Test plugin synchronization with error."""
        self.mock_plugin1.sync.side_effect = Exception("Sync failed")
        
        with self.assertRaises(Exception):
            self.plugin_manager.sync_plugin('test1')

    def test_sync_all_plugins_success(self):
        """Test successful synchronization of all plugins."""
        result = self.plugin_manager.sync_all_plugins()
        
        # Should have results for non-dummy plugins
        self.assertEqual(len(result), 2)
        self.assertIn('test1', result)
        self.assertIn('test2', result)
        self.assertNotIn('dummy', result)  # Dummy plugin should be skipped
        
        # Verify sync was called on non-dummy plugins
        self.mock_plugin1.sync.assert_called_once()
        self.mock_plugin2.sync.assert_called_once()
        self.dummy_plugin.sync.assert_not_called()

    def test_sync_all_plugins_partial_failure(self):
        """Test synchronization of all plugins with some failures."""
        self.mock_plugin2.sync.side_effect = Exception("Sync failed")
        
        result = self.plugin_manager.sync_all_plugins()
        
        # Should have results for both plugins
        self.assertEqual(len(result), 2)
        
        # First plugin should succeed
        self.assertEqual(result['test1']['success'], True)
        
        # Second plugin should fail
        self.assertEqual(result['test2']['success'], False)
        self.assertIn('message', result['test2'])
        self.assertEqual(result['test2']['errors'], 1)


class TestPluginManagerIntegration(unittest.TestCase):
    """Integration tests for plugin manager workflow."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_app = Mock()
        self.mock_app.logger = Mock()
        self.mock_db = Mock()
        self.plugin_manager = PluginManager(self.mock_app, self.mock_db)

    @patch('plugins.plugin_manager.os.listdir')
    @patch('plugins.plugin_manager.importlib.import_module')
    @patch('plugins.plugin_manager.inspect.getmembers')
    def test_complete_discovery_workflow(self, mock_getmembers, mock_import, mock_listdir):
        """Test complete plugin discovery workflow."""
        # Mock realistic plugin directory
        mock_listdir.return_value = [
            'ohio.py',
            'virginia.py',
            'dummy.py',
            'base_plugin.py',
            'plugin_manager.py'
        ]

        # Create mock modules with proper plugin classes
        def mock_import_side_effect(module_name):
            if module_name == 'plugins.ohio':
                mock_module = Mock()
                
                class MockOhioPlugin(BasePlugin):
                    @property
                    def name(self):
                        return 'ohio'
                    
                    @property
                    def state_code(self):
                        return 'OH'
                    
                    def get_status(self):
                        return {'name': 'ohio', 'state_code': 'OH'}
                    
                    def sync(self, election_id=None):
                        return {'success': True, 'added': 5, 'updated': 2}
                
                mock_getmembers.return_value = [('MockOhioPlugin', MockOhioPlugin)]
                return mock_module
            elif module_name == 'plugins.virginia':
                mock_module = Mock()
                
                class MockVirginiaPlugin(BasePlugin):
                    @property
                    def name(self):
                        return 'virginia'
                    
                    @property
                    def state_code(self):
                        return 'VA'
                    
                    def get_status(self):
                        return {'name': 'virginia', 'state_code': 'VA'}
                    
                    def sync(self, election_id=None):
                        return {'success': True, 'added': 8, 'updated': 3}
                
                mock_getmembers.return_value = [('MockVirginiaPlugin', MockVirginiaPlugin)]
                return mock_module
            elif module_name == 'plugins.dummy':
                mock_module = Mock()
                
                class MockDummyPlugin(BasePlugin):
                    @property
                    def name(self):
                        return 'dummy'
                    
                    @property
                    def state_code(self):
                        return 'ALL'
                    
                    def get_status(self):
                        return {'name': 'dummy', 'state_code': 'ALL'}
                    
                    def sync(self, election_id=None):
                        return {'success': True, 'added': 100, 'updated': 0}
                
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
        with patch.object(self.plugin_manager, 'discover_plugins') as mock_discover:
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
        self.plugin_manager = PluginManager(self.mock_app, self.mock_db)

    @patch('plugins.plugin_manager.os.listdir')
    def test_discovery_directory_error(self, mock_listdir):
        """Test handling of directory access errors."""
        mock_listdir.side_effect = PermissionError("Permission denied")
        
        self.plugin_manager.discover_plugins()
        
        # Should handle error gracefully
        self.assertEqual(len(self.plugin_manager.plugins), 0)

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
        TestPluginManagement,
        TestPluginSynchronization,
        TestPluginManagerIntegration,
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