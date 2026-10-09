"""Conservative local capacity check used before admitting work."""

from __future__ import annotations

import ctypes
import os
from dataclasses import dataclass
from sys import platform

from ai_company.application.runtime import RuntimeProfile


@dataclass(frozen=True)
class ResourceSnapshot:
    total_ram_mb: int
    available_ram_mb: int
    logical_cpus: int


class _MemoryStatus(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def read_resources() -> ResourceSnapshot:
    """Read current Windows RAM without requiring WMI administrator access."""
    if platform != "win32":
        raise RuntimeError("Automatic RAM detection is currently implemented for Windows only.")
    status = _MemoryStatus()
    status.dwLength = ctypes.sizeof(_MemoryStatus)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise OSError("Could not read available physical memory.")
    mib = 1024 * 1024
    return ResourceSnapshot(
        total_ram_mb=status.ullTotalPhys // mib,
        available_ram_mb=status.ullAvailPhys // mib,
        logical_cpus=os.cpu_count() or 1,
    )


def safe_worker_count(
    profile: RuntimeProfile,
    resources: ResourceSnapshot,
    requested: int,
    provider_slots: int,
    budget_slots: int,
    *,
    minimum_available_mb: int = 512,
    estimated_worker_mb: int = 512,
) -> int:
    """Cap work conservatively; estimates must be tuned from measured load."""
    if min(requested, provider_slots, budget_slots) <= 0:
        return 0
    if resources.available_ram_mb < minimum_available_mb:
        return 0
    if profile == RuntimeProfile.LITE:
        local_limit = 1
    else:
        if estimated_worker_mb <= 0:
            raise ValueError("estimated_worker_mb must be positive")
        ram_limit = max(0, (resources.available_ram_mb - minimum_available_mb) // estimated_worker_mb)
        cpu_limit = max(1, resources.logical_cpus - 1)
        local_limit = min(ram_limit, cpu_limit)
    return min(requested, provider_slots, budget_slots, local_limit)
