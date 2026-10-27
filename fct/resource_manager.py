"""
Resource Manager
Owner: Aakash Agarwal
Maps to SAD component "Resource Manager". Implements: FCT-F-014 (cleanup).

Small enough to just implement directly rather than stub out.
"""
import logging
from pathlib import Path
from typing import Iterable

logger = logging.getLogger("fct.resource_manager")


def cleanup_temp(paths: Iterable[Path]) -> None:
    """
    Remove temporary files created during a compress/extract operation.

    Never raises -- a cleanup failure shouldn't crash an otherwise-successful
    operation. Failures are logged (path + reason only, no file contents,
    per FCT-SR-004).
    """
    for path in paths:
        try:
            p = Path(path)
            if p.exists():
                p.unlink()
        except OSError as exc:
            logger.warning("cleanup failed for %s: %s", path, exc)


def get_current_process_memory() -> int:
    """Return current process resident working set memory in bytes."""
    import os
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.windll.kernel32
        psapi = ctypes.windll.psapi

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        pmc = PROCESS_MEMORY_COUNTERS()
        pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        handle = k32.GetCurrentProcess()
        if psapi.GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb):
            return int(pmc.WorkingSetSize)
        return 0
    else:
        try:
            with open("/proc/self/statm", "r") as f:
                rss_pages = int(f.read().split()[1])
                return int(rss_pages * os.sysconf("SC_PAGE_SIZE"))
        except Exception:
            try:
                import resource
                rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                import sys
                if sys.platform == "darwin":
                    return int(rss)
                return int(rss * 1024)
            except Exception:
                return 0


def get_process_peak_memory() -> int:
    """Return lifetime peak process resident working set memory in bytes."""
    import os
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.windll.kernel32
        psapi = ctypes.windll.psapi

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        pmc = PROCESS_MEMORY_COUNTERS()
        pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        handle = k32.GetCurrentProcess()
        if psapi.GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb):
            return int(pmc.PeakWorkingSetSize)
        return 0
    else:
        try:
            import resource
            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            import sys
            if sys.platform == "darwin":
                return int(rss)
            return int(rss * 1024)
        except Exception:
            return get_current_process_memory()


class MemoryTracker:
    """Context manager for tracking peak process memory and Python heap allocations.

    Maps to SAD Section 4.4 and FCT-NF-002 monitoring requirements.
    """

    def __init__(self, sample_interval_seconds: float = 0.005) -> None:
        self.sample_interval = sample_interval_seconds
        self.initial_process_bytes: int = 0
        self.peak_process_bytes: int = 0
        self.peak_python_bytes: int = 0
        self.elapsed_seconds: float = 0.0
        self._stop_event = None
        self._thread = None
        self._t0: float = 0.0

    def __enter__(self) -> "MemoryTracker":
        import threading
        import time
        import tracemalloc

        tracemalloc.start()
        self.initial_process_bytes = get_current_process_memory()
        self.peak_process_bytes = self.initial_process_bytes

        self._stop_event = threading.Event()

        def _sample() -> None:
            while not self._stop_event.is_set():
                mem = get_current_process_memory()
                if mem > self.peak_process_bytes:
                    self.peak_process_bytes = mem
                self._stop_event.wait(self.sample_interval)

        self._thread = threading.Thread(target=_sample, daemon=True)
        self._thread.start()
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        import time
        import tracemalloc

        self.elapsed_seconds = max(0.0, time.perf_counter() - self._t0)
        if self._stop_event:
            self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)

        # Check OS-reported peak working set in case peak was instantaneous
        os_peak = get_process_peak_memory()
        if os_peak > self.peak_process_bytes:
            self.peak_process_bytes = os_peak

        # Check tracemalloc Python heap peak
        _, peak_py = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        self.peak_python_bytes = peak_py

