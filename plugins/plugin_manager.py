"""
Plugin Manager for discovering and loading state-specific plugins

This manager automatically discovers plugin modules in the plugins directory
and provides an interface for interacting with them.
"""

import os
import importlib
import inspect
from typing import Dict, List, Any, Optional
from .base_plugin import BasePlugin


class PluginManager:
    """
    Manages discovery, loading, and execution of state-specific plugins.
    """

    def __init__(self, app, db):
        """
        Initialize the plugin manager.

        Args:
            app: Flask application instance
            db: SQLAlchemy database instance
        """
        self.app = app
        self.db = db
        self.plugins: Dict[str, BasePlugin] = {}
        self.discover_plugins()

    def discover_plugins(self):
        """
        Discover and load all plugins from the plugins directory.

        Plugins are Python modules in the plugins directory that contain
        a class inheriting from BasePlugin. The module name should match
        the plugin's name property.
        """
        plugins_dir = os.path.dirname(__file__)
        self.app.logger.info(f"Discovering plugins in: {plugins_dir}")

        # Get all Python files in plugins directory
        for filename in os.listdir(plugins_dir):
            # Skip special files
            if filename.startswith('_') or filename.startswith('.'):
                continue

            if not filename.endswith('.py'):
                continue

            # Skip base_plugin and plugin_manager
            if filename in ['base_plugin.py', 'plugin_manager.py']:
                continue

            module_name = filename[:-3]  # Remove .py extension

            try:
                # Import the module
                module_path = f'plugins.{module_name}'
                module = importlib.import_module(module_path)

                # Find classes that inherit from BasePlugin
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, BasePlugin) and obj is not BasePlugin:
                        # Instantiate the plugin
                        plugin_instance = obj(self.app, self.db)
                        plugin_name = plugin_instance.name

                        # Verify module name matches plugin name
                        if module_name != plugin_name:
                            self.app.logger.warning(
                                f"Plugin module name '{module_name}' doesn't match "
                                f"plugin name '{plugin_name}'. Skipping."
                            )
                            continue

                        self.plugins[plugin_name] = plugin_instance
                        self.app.logger.info(
                            f"Loaded plugin: {plugin_name} ({plugin_instance.state_code})"
                        )

            except Exception as e:
                self.app.logger.error(f"Error loading plugin {module_name}: {e}")

        self.app.logger.info(f"Discovered {len(self.plugins)} plugin(s)")

    def get_plugin(self, name: str) -> BasePlugin:
        """
        Get a specific plugin by name.

        Args:
            name: Plugin name

        Returns:
            Plugin instance

        Raises:
            KeyError: If plugin not found
        """
        if name not in self.plugins:
            raise KeyError(f"Plugin '{name}' not found")

        return self.plugins[name]

    def list_plugins(self) -> List[Dict[str, Any]]:
        """
        List all loaded plugins and their status.

        Returns:
            List of plugin status dictionaries
        """
        return [plugin.get_status() for plugin in self.plugins.values()]

    def sync_plugin(self, name: str, election_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Trigger a data sync for a specific plugin.

        Args:
            name: Plugin name
            election_id: Optional election ID to link assignments to

        Returns:
            Sync result dictionary

        Raises:
            KeyError: If plugin not found
        """
        plugin = self.get_plugin(name)
        return plugin.sync(election_id=election_id)

    def sync_all_plugins(self) -> Dict[str, Any]:
        """
        Trigger a data sync for all plugins.

        Returns:
            Dictionary with results for each plugin
        """
        results = {}

        for name, plugin in self.plugins.items():
            # Skip dummy plugin
            if name == 'dummy':
                continue

            try:
                results[name] = plugin.sync()
            except Exception as e:
                self.app.logger.error(f"Error syncing plugin {name}: {e}")
                results[name] = {
                    'success': False,
                    'message': str(e),
                    'added': 0,
                    'updated': 0,
                    'errors': 1
                }

        return results

    def get_plugin_by_state(self, state_code: str) -> BasePlugin:
        """
        Get a plugin by state code.

        Args:
            state_code: Two-letter state code (e.g., 'CA')

        Returns:
            Plugin instance

        Raises:
            KeyError: If no plugin found for state
        """
        state_code = state_code.upper()

        for plugin in self.plugins.values():
            if plugin.state_code == state_code:
                return plugin

        raise KeyError(f"No plugin found for state '{state_code}'")
