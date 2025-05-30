# core/thermal_manager.py
import psutil
import time
import platform
import subprocess
from typing import Dict, Optional, List
from collections import deque
from threading import Thread, Lock
from pathlib import Path

class ThermalManager:
    """Monitor and adapt to system thermal conditions"""
    
    def __init__(self, temp_threshold: float = 80.0, check_interval: int = 5):
        self.temp_threshold = temp_threshold  # Celsius
        self.check_interval = check_interval  # seconds
        self.temp_history = deque(maxlen=60)  # Last 5 minutes (at 5s intervals)
        self.current_temp = 0.0
        self.is_throttled = False
        self.throttle_factor = 1.0  # 1.0 = no throttle, 0.5 = 50% reduction
        
        self._lock = Lock()
        self._monitoring = False
        self._monitor_thread = None
        
        # Platform-specific temperature sources
        self.temp_sources = self._identify_temp_sources()
        
    def start_monitoring(self):
        """Start thermal monitoring in background"""
        if self._monitoring:
            return
            
        self._monitoring = True
        self._monitor_thread = Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        
    def stop_monitoring(self):
        """Stop thermal monitoring"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=10)
            
    def _monitor_loop(self):
        """Background monitoring loop"""
        while self._monitoring:
            try:
                temps = self._get_cpu_temperatures()
                if temps:
                    with self._lock:
                        # Calculate average temperature inside lock
                        avg_temp = sum(temps.values()) / len(temps)
                        max_temp = max(temps.values())
                        
                        # Use max temperature for throttling decisions
                        self.current_temp = max_temp
                        self.temp_history.append((time.time(), max_temp))
                        self._update_throttle_state()
            except Exception as e:
                # Don't let monitoring errors crash the thread
                pass
                
            time.sleep(self.check_interval)
            
    def _identify_temp_sources(self) -> List[str]:
        """Identify available temperature sources on the system"""
        sources = []
        
        if platform.system() == 'Linux':
            # Check for different sensor types
            possible_sources = [
                'coretemp', 'k10temp', 'zenpower', 'it87', 
                'nct6775', 'dell_smm', 'thinkpad', 'acpitz'
            ]
            
            try:
                if hasattr(psutil, 'sensors_temperatures'):
                    available = psutil.sensors_temperatures()
                    for source in possible_sources:
                        if source in available:
                            sources.append(source)
            except:
                pass
                
        return sources
            
    def _get_cpu_temperatures(self) -> Dict[str, float]:
        """Get CPU temperatures from various sources"""
        temps = {}
        
        try:
            # Try psutil sensors first
            if hasattr(psutil, 'sensors_temperatures'):
                sensor_data = psutil.sensors_temperatures()
                
                # Priority order for CPU temperature sensors
                for sensor_name in ['coretemp', 'k10temp', 'cpu_thermal', 'cpu-thermal']:
                    if sensor_name in sensor_data:
                        for entry in sensor_data[sensor_name]:
                            if entry.current > 0:
                                label = entry.label or f"cpu_{len(temps)}"
                                temps[f"{sensor_name}_{label}"] = entry.current
                                
                # Also check for generic CPU sensors
                for name, entries in sensor_data.items():
                    if 'cpu' in name.lower() and name not in temps:
                        for entry in entries:
                            if entry.current > 0:
                                temps[f"{name}_{entry.label}"] = entry.current
                                
        except:
            pass
            
        # Platform-specific fallbacks if psutil didn't work
        if not temps:
            temps = self._get_platform_specific_temps()
            
        return temps
    
    def _get_platform_specific_temps(self) -> Dict[str, float]:
        """Platform-specific temperature reading"""
        temps = {}
        
        if platform.system() == 'Linux':
            temps.update(self._get_linux_temps())
        elif platform.system() == 'Darwin':  # macOS
            temps.update(self._get_macos_temps())
        elif platform.system() == 'Windows':
            temps.update(self._get_windows_temps())
            
        return temps
    
    def _get_linux_temps(self) -> Dict[str, float]:
        """Linux-specific temperature reading"""
        temps = {}
        
        # Try /sys/class/thermal
        thermal_path = Path('/sys/class/thermal')
        if thermal_path.exists():
            for zone in thermal_path.glob('thermal_zone*'):
                try:
                    temp_file = zone / 'temp'
                    type_file = zone / 'type'
                    
                    if temp_file.exists():
                        # Temperature in millidegrees
                        temp = int(temp_file.read_text().strip()) / 1000
                        
                        # Get zone type if available
                        zone_type = 'unknown'
                        if type_file.exists():
                            zone_type = type_file.read_text().strip()
                            
                        # Only include CPU-related zones
                        if 'cpu' in zone_type.lower() or zone_type == 'x86_pkg_temp':
                            temps[f"{zone.name}_{zone_type}"] = temp
                        elif temp > 20:  # Reasonable temperature, might be CPU
                            temps[zone.name] = temp
                            
                except (ValueError, OSError):
                    continue
                    
        # Try hwmon
        hwmon_path = Path('/sys/class/hwmon')
        if hwmon_path.exists() and len(temps) == 0:
            for hwmon in hwmon_path.iterdir():
                try:
                    name_file = hwmon / 'name'
                    if name_file.exists():
                        name = name_file.read_text().strip()
                        # Look for CPU-related sensors
                        if any(cpu_name in name for cpu_name in ['coretemp', 'k10temp', 'cpu']):
                            # Read all temp inputs
                            for temp_input in hwmon.glob('temp*_input'):
                                temp = int(temp_input.read_text().strip()) / 1000
                                if temp > 20:  # Reasonable temperature
                                    temps[f"{name}_{temp_input.stem}"] = temp
                except:
                    continue
                    
        return temps
    
    def _get_macos_temps(self) -> Dict[str, float]:
        """macOS-specific temperature reading"""
        temps = {}
        
        # Try different temperature tools
        tools = [
            ('osx-cpu-temp', [], r'(\d+\.?\d*)°C'),
            ('istats', ['cpu', 'temp'], r'CPU temp:\s*(\d+\.?\d*)°C'),
            ('sudo', ['powermetrics', '-n', '1', '-i', '1000'], r'CPU die temperature:\s*(\d+\.?\d*) C')
        ]
        
        for cmd, args, pattern in tools:
            try:
                result = subprocess.run(
                    [cmd] + args,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    import re
                    match = re.search(pattern, result.stdout)
                    if match:
                        temp = float(match.group(1))
                        if 20 < temp < 120:  # Reasonable range
                            temps['cpu'] = temp
                            break
            except (subprocess.SubprocessError, FileNotFoundError, ValueError):
                continue
                
        return temps
    
    def _get_windows_temps(self) -> Dict[str, float]:
        """Windows-specific temperature reading"""
        temps = {}
        
        # Try WMI
        try:
            import wmi
            c = wmi.WMI(namespace='root\\wmi')
            
            # Try MSAcpi_ThermalZoneTemperature
            try:
                thermal_zones = c.MSAcpi_ThermalZoneTemperature()
                for i, zone in enumerate(thermal_zones):
                    # Convert from tenths of Kelvin to Celsius
                    temp = (zone.CurrentTemperature / 10) - 273.15
                    if 20 < temp < 120:  # Reasonable range
                        temps[f'thermal_zone_{i}'] = temp
            except:
                pass
                
            # Try Win32_TemperatureProbe (rarely works)
            try:
                temp_probes = c.Win32_TemperatureProbe()
                for i, probe in enumerate(temp_probes):
                    if probe.CurrentReading:
                        temp = probe.CurrentReading / 10 - 273.15
                        if 20 < temp < 120:
                            temps[f'probe_{i}'] = temp
            except:
                pass
                
        except ImportError:
            pass
            
        # Try Open Hardware Monitor CLI if available
        try:
            result = subprocess.run(
                ['OpenHardwareMonitorCLI.exe'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                import re
                # Parse temperature values
                for match in re.finditer(r'CPU Core #?\d+.*?(\d+\.?\d*)°C', result.stdout):
                    temp = float(match.group(1))
                    if 20 < temp < 120:
                        temps[f'core_{len(temps)}'] = temp
        except:
            pass
            
        return temps
    
    def _update_throttle_state(self):
        """Update throttling state based on temperature trends"""
        if not self.temp_history:
            return
            
        # Current temperature check
        if self.current_temp > self.temp_threshold:
            self.is_throttled = True
            
            # Progressive throttling based on how far over threshold
            overage = self.current_temp - self.temp_threshold
            
            if overage > 20:
                # Critical temperature - maximum throttling
                self.throttle_factor = 0.25
            elif overage > 10:
                # High temperature - significant throttling
                self.throttle_factor = 0.5
            else:
                # Moderate temperature - gradual throttling
                self.throttle_factor = max(0.5, 1.0 - (overage / 20))
                
        elif self.current_temp < self.temp_threshold - 5:  # 5°C hysteresis
            # Temperature back to safe levels
            self.is_throttled = False
            self.throttle_factor = 1.0
            
        # Check temperature trend
        if len(self.temp_history) >= 12:  # 1 minute of data
            recent_temps = [temp for _, temp in list(self.temp_history)[-12:]]
            old_temps = [temp for _, temp in list(self.temp_history)[-24:-12]]
            
            if old_temps:  # Have enough history
                recent_avg = sum(recent_temps) / len(recent_temps)
                old_avg = sum(old_temps) / len(old_temps)
                temp_trend = recent_avg - old_avg
                
                if temp_trend > 5:  # Rising rapidly
                    # Preemptive throttling
                    self.throttle_factor = min(self.throttle_factor, 0.7)
                elif temp_trend < -5 and not self.is_throttled:  # Cooling down
                    # Can be more aggressive
                    self.throttle_factor = 1.0
                    
    def get_adjusted_worker_count(self, base_workers: int) -> int:
        """Get thermally-adjusted worker count"""
        with self._lock:
            if self.is_throttled:
                adjusted = max(1, int(base_workers * self.throttle_factor))
                return adjusted
            return base_workers
    
    def get_thermal_status(self) -> Dict[str, any]:
        """Get current thermal status"""
        with self._lock:
            status = {
                'current_temp': round(self.current_temp, 1),
                'is_throttled': self.is_throttled,
                'throttle_factor': round(self.throttle_factor, 2),
                'temp_threshold': self.temp_threshold,
                'adjusted_performance': f"{self.throttle_factor * 100:.0f}%"
            }
            
            # Add temperature trend
            if len(self.temp_history) >= 2:
                recent = list(self.temp_history)[-6:]  # Last 30 seconds
                if len(recent) >= 2:
                    trend = recent[-1][1] - recent[0][1]
                    status['temp_trend'] = 'rising' if trend > 1 else 'falling' if trend < -1 else 'stable'
                    status['temp_change'] = round(trend, 1)
                    
            return status
    
    def should_pause_operations(self) -> bool:
        """Check if operations should be paused due to critical temperature"""
        with self._lock:
            # Pause if temperature is critically high
            return self.current_temp > self.temp_threshold + 15  # 95°C default
    
    def get_recommended_delay(self) -> float:
        """Get recommended delay between operations based on temperature"""
        with self._lock:
            if not self.is_throttled:
                return 0.0
                
            # Add delays based on temperature
            if self.throttle_factor <= 0.25:
                return 2.0  # 2 second delay
            elif self.throttle_factor <= 0.5:
                return 1.0  # 1 second delay
            elif self.throttle_factor <= 0.75:
                return 0.5  # 0.5 second delay
            else:
                return 0.1  # Small delay