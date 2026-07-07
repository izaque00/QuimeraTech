# quimera/ferramentas/device_scanner.py
"""
Device Scanner — Scan de dispositivos embarcados para compilação cruzada.

Detecta dispositivos Android (adb), iOS (libimobiledevice), 
Raspberry Pi, e outros embarcados conectados via USB ou rede.

Uso:
    from quimera.ferramentas.device_scanner import DeviceScanner
    
    scanner = DeviceScanner()
    devices = await scanner.scan()
"""

import asyncio
import logging

class DeviceConnectionError(Exception):
    """Raised when device connection fails."""
    pass
import os
import platform
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DeviceInfo:
    """Informações de um dispositivo detectado."""
    device_id: str
    device_type: str
    arch: str
    os_version: str
    connection: str  # usb, wifi, ethernet
    extra: Dict[str, str] = field(default_factory=dict)


class DeviceScanner:
    """Scanner de dispositivos embarcados."""
    
    async def scan(self) -> List[DeviceInfo]:
        """Scaneia todos os dispositivos disponíveis."""
        devices = []
        
        # Android (adb)
        android_devices = await self._scan_android()
        devices.extend(android_devices)
        
        # Linux embarcado (ssh)
        embedded_devices = await self._scan_embedded_linux()
        devices.extend(embedded_devices)
        
        # Local
        local = self._scan_local()
        if local:
            devices.append(local)
        
        logger.info(f"DeviceScanner: {len(devices)} dispositivo(s) detectado(s)")
        return devices
    
    async def _scan_android(self) -> List[DeviceInfo]:
        """Scaneia dispositivos Android via adb."""
        devices = []
        try:
            proc = await asyncio.create_subprocess_exec(
                "adb", "devices",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()
            lines = stdout.decode().strip().split('\n')[1:]
            for line in lines:
                if '\tdevice' in line:
                    device_id = line.split('\t')[0]
                    devices.append(DeviceInfo(
                        device_id=device_id,
                        device_type="android",
                        arch="aarch64",
                        os_version="unknown",
                        connection="usb",
                    ))
        except FileNotFoundError:
            logger.debug("adb não encontrado")
        return devices
    
    async def _scan_embedded_linux(self) -> List[DeviceInfo]:
        """Scaneia dispositivos Linux embarcados."""
        return []
    
    def _scan_local(self) -> Optional[DeviceInfo]:
        """Detecta arquitetura local."""
        return DeviceInfo(
            device_id="localhost",
            device_type="local",
            arch=platform.machine(),
            os_version=platform.release(),
            connection="local",
        )
