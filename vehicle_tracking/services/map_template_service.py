#!/usr/bin/env python3
"""
Map Template Service - Manages map providers and templates

Handles loading, configuration, and switching between different map providers
(Leaflet, Mapbox, Google Maps, etc.) for vehicle animation display.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from string import Template
import logging

from core.services.base_service import BaseService
from core.services.interfaces import IService
from core.result_types import Result
from core.exceptions import ValidationError, ConfigurationError
from core.settings_manager import settings

logger = logging.getLogger(__name__)


class MapTemplateError(ConfigurationError):
    """Map template specific errors"""
    pass


class MapProvider:
    """Map provider configuration"""
    
    def __init__(self, name: str, display_name: str, requires_api_key: bool = False):
        self.name = name
        self.display_name = display_name
        self.requires_api_key = requires_api_key
        self.template_path: Optional[Path] = None
        self.config: Dict[str, Any] = {}
        self.is_available: bool = False


class IMapTemplateService(IService):
    """Interface for map template service (defined in interfaces.py)"""
    pass


class MapTemplateService(BaseService, IMapTemplateService):
    """
    Service for managing map templates and providers
    
    Enables hot-swapping between different map providers while maintaining
    the same JavaScript interface for vehicle animation.
    """
    
    # Default template directory
    TEMPLATE_DIR = Path("templates/maps")
    
    # Built-in providers
    PROVIDERS = {
        'leaflet': MapProvider(
            'leaflet', 
            'Leaflet (OpenStreetMap)',
            requires_api_key=False
        ),
        'mapbox': MapProvider(
            'mapbox',
            'Mapbox',
            requires_api_key=True
        ),
        'google': MapProvider(
            'google',
            'Google Maps',
            requires_api_key=True
        ),
        'arcgis': MapProvider(
            'arcgis',
            'ArcGIS',
            requires_api_key=False
        )
    }
    
    # JavaScript interface that all templates must implement
    TEMPLATE_INTERFACE = """
    // Required interface for vehicle map templates
    class VehicleMapTemplate {
        loadVehicles(vehicleData) { }
        startAnimation() { }
        stopAnimation() { }
        pauseAnimation() { }
        seekToTime(timestamp) { }
        setPlaybackSpeed(speed) { }
        updateVehicles(vehicleData) { }
        clearVehicles() { }
        focusVehicle(vehicleId) { }
        setMapStyle(style) { }
    }
    """
    
    def __init__(self):
        """Initialize map template service"""
        super().__init__("MapTemplateService")
        
        # Current provider
        self._current_provider: Optional[str] = None
        self._default_provider: str = 'leaflet'
        
        # Template cache
        self._template_cache: Dict[str, str] = {}
        
        # Initialize providers
        self._initialize_providers()
        
        # Load saved configuration
        self._load_configuration()
    
    def _initialize_providers(self):
        """Initialize provider configurations"""
        for provider_name, provider in self.PROVIDERS.items():
            # Set template path
            provider.template_path = self.TEMPLATE_DIR / f"{provider_name}_vehicle_template.html"
            
            # Check if template exists
            if provider.template_path.exists():
                provider.is_available = True
                self._log_operation("init_provider", f"Provider {provider_name} available")
            else:
                provider.is_available = False
                logger.warning(f"Template not found for {provider_name}: {provider.template_path}")
            
            # Load default config
            provider.config = self._get_default_config(provider_name)
    
    def _get_default_config(self, provider: str) -> Dict[str, Any]:
        """Get default configuration for provider"""
        configs = {
            'leaflet': {
                'tile_url': 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
                'attribution': '© OpenStreetMap contributors',
                'max_zoom': 19,
                'default_zoom': 13,
                'cluster_markers': True,
                'show_scale': True,
                'show_zoom_control': True
            },
            'mapbox': {
                'style': 'mapbox://styles/mapbox/dark-v10',
                'api_key': '',
                'max_zoom': 20,
                'default_zoom': 13,
                'pitch': 0,
                'bearing': 0,
                'enable_3d': False,
                'cluster_markers': True
            },
            'google': {
                'api_key': '',
                'map_type': 'roadmap',  # roadmap, satellite, hybrid, terrain
                'default_zoom': 13,
                'disable_default_ui': False,
                'zoom_control': True,
                'map_type_control': True,
                'street_view_control': False
            },
            'arcgis': {
                'basemap': 'arcgis-navigation',
                'default_zoom': 13,
                'show_attribution': True,
                'nav_widget_position': 'top-left'
            }
        }
        return configs.get(provider, {})
    
    def _load_configuration(self):
        """Load saved provider configurations from settings"""
        try:
            # Load default provider
            self._default_provider = settings.value('vehicle_tracking/default_provider', 'leaflet')
            
            # Load API keys and custom configs
            for provider_name, provider in self.PROVIDERS.items():
                # Load API key if required
                if provider.requires_api_key:
                    api_key = settings.value(f'vehicle_tracking/{provider_name}_api_key', '')
                    if api_key:
                        provider.config['api_key'] = api_key
                
                # Load custom configuration
                custom_config = settings.value(f'vehicle_tracking/{provider_name}_config')
                if custom_config:
                    try:
                        if isinstance(custom_config, str):
                            custom_config = json.loads(custom_config)
                        provider.config.update(custom_config)
                    except json.JSONDecodeError:
                        logger.error(f"Invalid config for {provider_name}")
                        
        except Exception as e:
            logger.error(f"Error loading map configuration: {e}")
    
    def get_available_providers(self) -> List[str]:
        """
        Get list of available map providers
        
        Returns:
            List of provider names that have templates available
        """
        return [
            name for name, provider in self.PROVIDERS.items()
            if provider.is_available
        ]
    
    def load_template(
        self, 
        provider: str, 
        container_id: str = "map"
    ) -> Result[str]:
        """
        Load map template HTML for specified provider
        
        Args:
            provider: Provider name
            container_id: HTML container ID for map
            
        Returns:
            Result containing template HTML or error
        """
        try:
            self._log_operation("load_template", f"Loading template for {provider}")
            
            # Check if provider exists
            if provider not in self.PROVIDERS:
                return Result.error(
                    ValidationError(
                        {'provider': f'Unknown provider: {provider}'},
                        user_message=f"Map provider '{provider}' is not supported"
                    )
                )
            
            provider_obj = self.PROVIDERS[provider]
            
            # Check if template is available
            if not provider_obj.is_available:
                return Result.error(
                    MapTemplateError(
                        f"Template not available for {provider}",
                        user_message=f"Map template for {provider_obj.display_name} is not installed"
                    )
                )
            
            # Check API key if required
            if provider_obj.requires_api_key:
                api_key = provider_obj.config.get('api_key', '')
                if not api_key:
                    return Result.error(
                        ConfigurationError(
                            f"API key required for {provider}",
                            user_message=f"{provider_obj.display_name} requires an API key. "
                                       "Please configure it in settings."
                        )
                    )
            
            # Check cache
            cache_key = f"{provider}_{container_id}"
            if cache_key in self._template_cache:
                return Result.success(self._template_cache[cache_key])
            
            # Load template file
            template_html = self._load_template_file(provider_obj, container_id)
            
            if template_html:
                # Cache the template
                self._template_cache[cache_key] = template_html
                self._current_provider = provider
                self._log_operation("load_template", f"Template loaded for {provider}")
                return Result.success(template_html)
            else:
                return Result.error(
                    MapTemplateError(
                        f"Failed to load template for {provider}",
                        user_message=f"Could not load map template for {provider_obj.display_name}"
                    )
                )
                
        except Exception as e:
            error = MapTemplateError(
                f"Template loading failed: {e}",
                user_message=f"Error loading map template: {str(e)}"
            )
            self._handle_error(error)
            return Result.error(error)
    
    def _load_template_file(self, provider: MapProvider, container_id: str) -> Optional[str]:
        """Load and process template file"""
        try:
            # Read template
            with open(provider.template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
            
            # Create template with substitutions
            template = Template(template_content)
            
            # Prepare substitution variables
            config = provider.config.copy()
            config['container_id'] = container_id
            config['provider_name'] = provider.name
            
            # Add CDN URLs based on provider
            if provider.name == 'leaflet':
                config['leaflet_css'] = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'
                config['leaflet_js'] = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'
                config['timestamped_geojson_js'] = 'https://cdn.jsdelivr.net/npm/leaflet.timeline@1.2.1/dist/leaflet.timeline.min.js'
            elif provider.name == 'mapbox':
                config['mapbox_css'] = 'https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.css'
                config['mapbox_js'] = 'https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.js'
            
            # Perform substitution
            processed_html = template.safe_substitute(**config)
            
            # Inject interface checking
            processed_html = self._inject_interface_check(processed_html)
            
            return processed_html
            
        except Exception as e:
            logger.error(f"Error loading template file: {e}")
            return None
    
    def _inject_interface_check(self, html: str) -> str:
        """Inject JavaScript to verify template implements required interface"""
        interface_check = """
        <script>
        // Verify template implements required interface
        (function() {
            const requiredMethods = [
                'loadVehicles', 'startAnimation', 'stopAnimation',
                'pauseAnimation', 'seekToTime', 'setPlaybackSpeed',
                'updateVehicles', 'clearVehicles', 'focusVehicle'
            ];
            
            window.addEventListener('mapReady', function() {
                if (window.vehicleMap) {
                    const missing = requiredMethods.filter(
                        method => typeof window.vehicleMap[method] !== 'function'
                    );
                    if (missing.length > 0) {
                        console.error('Map template missing methods:', missing);
                    }
                }
            });
        })();
        </script>
        """
        
        # Inject before closing body tag
        if '</body>' in html:
            html = html.replace('</body>', f'{interface_check}</body>')
        else:
            html += interface_check
            
        return html
    
    def get_provider_config(self, provider: str) -> Dict[str, Any]:
        """
        Get configuration for specific provider
        
        Args:
            provider: Provider name
            
        Returns:
            Provider configuration dictionary
        """
        if provider in self.PROVIDERS:
            return self.PROVIDERS[provider].config.copy()
        return {}
    
    def set_provider_config(
        self, 
        provider: str, 
        config: Dict[str, Any]
    ) -> Result[None]:
        """
        Update provider configuration
        
        Args:
            provider: Provider name
            config: Configuration dictionary
            
        Returns:
            Result indicating success or error
        """
        try:
            if provider not in self.PROVIDERS:
                return Result.error(
                    ValidationError(
                        {'provider': f'Unknown provider: {provider}'},
                        user_message=f"Map provider '{provider}' is not supported"
                    )
                )
            
            # Update configuration
            self.PROVIDERS[provider].config.update(config)
            
            # Save to settings
            settings.setValue(
                f'vehicle_tracking/{provider}_config',
                json.dumps(self.PROVIDERS[provider].config)
            )
            
            # Save API key separately if present
            if 'api_key' in config:
                settings.setValue(
                    f'vehicle_tracking/{provider}_api_key',
                    config['api_key']
                )
            
            # Clear cache for this provider
            self._clear_provider_cache(provider)
            
            self._log_operation("set_config", f"Updated config for {provider}")
            return Result.success(None)
            
        except Exception as e:
            error = ConfigurationError(
                f"Failed to update config: {e}",
                user_message=f"Could not update {provider} configuration"
            )
            self._handle_error(error)
            return Result.error(error)
    
    def _clear_provider_cache(self, provider: str):
        """Clear cached templates for a provider"""
        keys_to_remove = [k for k in self._template_cache.keys() if k.startswith(provider)]
        for key in keys_to_remove:
            del self._template_cache[key]
    
    def validate_api_key(self, provider: str, api_key: str) -> Result[bool]:
        """
        Validate API key for provider
        
        Args:
            provider: Provider name
            api_key: API key to validate
            
        Returns:
            Result containing validation status
        """
        try:
            # Basic validation - just check it's not empty
            # Real validation would make API calls to verify
            if not api_key or len(api_key) < 10:
                return Result.success(False)
            
            # Provider-specific validation patterns
            if provider == 'mapbox':
                # Mapbox keys start with 'pk.' or 'sk.'
                is_valid = api_key.startswith(('pk.', 'sk.'))
            elif provider == 'google':
                # Google keys are typically 39 characters
                is_valid = len(api_key) >= 30
            else:
                # Generic validation
                is_valid = len(api_key) >= 10
            
            return Result.success(is_valid)
            
        except Exception as e:
            error = ValidationError(
                {'api_key': f'Validation failed: {e}'},
                user_message="Could not validate API key"
            )
            return Result.error(error)
    
    def get_default_provider(self) -> str:
        """
        Get the default map provider
        
        Returns:
            Default provider name
        """
        return self._default_provider
    
    def set_default_provider(self, provider: str) -> Result[None]:
        """
        Set the default map provider
        
        Args:
            provider: Provider name
            
        Returns:
            Result indicating success or error
        """
        try:
            if provider not in self.PROVIDERS:
                return Result.error(
                    ValidationError(
                        {'provider': f'Unknown provider: {provider}'},
                        user_message=f"Map provider '{provider}' is not supported"
                    )
                )
            
            self._default_provider = provider
            settings.setValue('vehicle_tracking/default_provider', provider)
            
            self._log_operation("set_default", f"Default provider set to {provider}")
            return Result.success(None)
            
        except Exception as e:
            error = ConfigurationError(
                f"Failed to set default provider: {e}",
                user_message="Could not update default map provider"
            )
            self._handle_error(error)
            return Result.error(error)
    
    def get_provider_display_name(self, provider: str) -> str:
        """Get display name for provider"""
        if provider in self.PROVIDERS:
            return self.PROVIDERS[provider].display_name
        return provider
    
    def clear_all_cache(self):
        """Clear all cached templates"""
        self._template_cache.clear()
        self._log_operation("clear_cache", "All template cache cleared")