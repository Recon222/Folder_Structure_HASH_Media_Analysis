#!/usr/bin/env python3
"""
Simplified Tauri Bridge Service - No async complexity
"""

import json
import subprocess
import threading
import socket
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from websocket_server import WebsocketServer

from core.services.base_service import BaseService
from core.result_types import Result
from core.logger import logger


class TauriBridgeService(BaseService):
    """Simple bridge service using threading instead of asyncio"""

    def __init__(self):
        super().__init__("TauriBridgeService")

        # WebSocket server
        self.ws_server: Optional[WebsocketServer] = None
        self.ws_port: Optional[int] = None
        self.ws_thread: Optional[threading.Thread] = None

        # Tauri process
        self.tauri_process: Optional[subprocess.Popen] = None
        self.tauri_path = Path(__file__).parent.parent / "tauri-map"

        # State
        self.is_running = False
        self.connected_clients = []
        self.pending_messages = []

    def find_free_port(self) -> int:
        """Find an available port"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('localhost', 0))
            s.listen(1)
            port = s.getsockname()[1]
        return port

    def start(self) -> Result[int]:
        """Start WebSocket server and launch Tauri"""
        try:
            # Find available port
            self.ws_port = self.find_free_port()
            logger.info(f"Using WebSocket port: {self.ws_port}")

            # Start WebSocket server in thread
            self._start_websocket_server()

            # Launch Tauri application
            self._launch_tauri()

            self.is_running = True
            return Result.success(self.ws_port)

        except Exception as e:
            logger.error(f"Failed to start bridge: {e}")
            return Result.error(str(e))

    def _start_websocket_server(self):
        """Start WebSocket server in a thread"""
        self.ws_server = WebsocketServer(port=self.ws_port, host='localhost')

        # Set up callbacks
        self.ws_server.set_fn_new_client(self._on_client_connected)
        self.ws_server.set_fn_client_left(self._on_client_disconnected)
        self.ws_server.set_fn_message_received(self._on_message_received)

        # Start in daemon thread
        self.ws_thread = threading.Thread(target=self.ws_server.serve_forever)
        self.ws_thread.daemon = True
        self.ws_thread.start()

        logger.info(f"WebSocket server started on port {self.ws_port}")

    def _launch_tauri(self):
        """Launch Tauri application"""
        try:
            # Build path to Tauri executable
            # The executable name comes from the productName in tauri.conf.json
            if sys.platform == "win32":
                exe_name = "Vehicle Tracking Map.exe"
            else:
                exe_name = "Vehicle Tracking Map"

            exe_path = self.tauri_path / "src-tauri" / "target" / "release" / exe_name

            logger.info(f"Looking for Tauri executable at: {exe_path}")

            # Check if built
            if not exe_path.exists():
                logger.error(f"Tauri executable not found at: {exe_path}")
                logger.error("Please build the Tauri app first by running 'npm run build' in the tauri-map directory")
                raise FileNotFoundError(f"Tauri executable not found: {exe_path}")

            # Launch with WebSocket port parameter
            cmd = [str(exe_path), f"--ws-port={self.ws_port}"]

            # Also pass as URL parameter
            env = os.environ.copy()
            env['TAURI_WS_PORT'] = str(self.ws_port)

            self.tauri_process = subprocess.Popen(
                cmd,
                cwd=self.tauri_path,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            logger.info("Tauri application launched")

        except Exception as e:
            logger.error(f"Failed to launch Tauri: {e}")
            raise

    def _on_client_connected(self, client, server):
        """Handle new WebSocket client"""
        logger.info(f"Tauri client connected: {client['id']}")
        self.connected_clients.append(client)

        # Send any pending messages
        for msg in self.pending_messages:
            server.send_message(client, json.dumps(msg))
        self.pending_messages.clear()

    def _on_client_disconnected(self, client, server):
        """Handle client disconnect"""
        logger.info(f"Tauri client disconnected: {client['id']}")
        if client in self.connected_clients:
            self.connected_clients.remove(client)

    def _on_message_received(self, client, server, message):
        """Handle message from Tauri"""
        try:
            data = json.loads(message)
            msg_type = data.get('type')

            if msg_type == 'ready':
                logger.info("Tauri map ready")
            elif msg_type == 'vehicle_clicked':
                logger.info(f"Vehicle clicked: {data.get('vehicle_id')}")
            elif msg_type == 'error':
                logger.error(f"Tauri error: {data.get('message')}")

        except Exception as e:
            logger.error(f"Error handling message: {e}")

    def send_vehicle_data(self, vehicle_data: Dict[str, Any]) -> Result[None]:
        """Send vehicle data to Tauri"""
        try:
            message = {
                "type": "load_vehicles",
                "data": vehicle_data
            }

            if self.connected_clients and self.ws_server:
                # Send to all connected clients
                self.ws_server.send_message_to_all(json.dumps(message))
                logger.info(f"Sent vehicle data to {len(self.connected_clients)} clients")
            else:
                # Queue for when client connects
                self.pending_messages.append(message)
                logger.info("Queued vehicle data for when client connects")

            return Result.success(None)

        except Exception as e:
            logger.error(f"Failed to send vehicle data: {e}")
            return Result.error(str(e))

    def send_command(self, command_type: str, command: str) -> Result[None]:
        """Send control command to Tauri"""
        try:
            message = {
                "type": command_type,
                "command": command
            }

            if self.connected_clients and self.ws_server:
                self.ws_server.send_message_to_all(json.dumps(message))
                return Result.success(None)
            else:
                logger.warning("No connected clients to send command to")
                return Result.error("No connected clients")

        except Exception as e:
            logger.error(f"Failed to send command: {e}")
            return Result.error(str(e))

    def shutdown(self):
        """Clean shutdown"""
        logger.info("Shutting down Tauri bridge...")

        # Stop WebSocket server
        if self.ws_server:
            try:
                self.ws_server.shutdown()
            except:
                pass

        # Terminate Tauri process
        if self.tauri_process:
            self.tauri_process.terminate()
            try:
                self.tauri_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.tauri_process.kill()

        self.is_running = False
        logger.info("Tauri bridge shutdown complete")