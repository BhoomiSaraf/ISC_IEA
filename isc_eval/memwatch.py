"""Windows memory measurement (ctypes, no third-party package): process working set and system RAM.

GetProcessMemoryInfo needs the 64-bit handle declared explicitly; without argtypes/restype the
handle is truncated and the call silently fails (this is why an earlier probe read 0 MB).
"""

import ctypes
import sys

MB = 2 ** 20
_WIN = sys.platform == "win32"


class _PMC(ctypes.Structure):
    _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


class _MSX(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


if _WIN:
    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _psapi = ctypes.WinDLL("psapi", use_last_error=True)
    _k32.GetCurrentProcess.restype = ctypes.c_void_p
    _k32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    _k32.OpenProcess.restype = ctypes.c_void_p
    _k32.CloseHandle.argtypes = [ctypes.c_void_p]
    _k32.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    _psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(_PMC), ctypes.c_ulong]
    _k32.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(_MSX)]

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_VM_READ = 0x0010
STILL_ACTIVE = 259


def _pmc(handle):
    c = _PMC()
    c.cb = ctypes.sizeof(_PMC)
    if not _psapi.GetProcessMemoryInfo(handle, ctypes.byref(c), c.cb):
        raise OSError(ctypes.get_last_error(), "GetProcessMemoryInfo failed")
    return c


def process_mb():
    """(working set MB, peak working set MB) of this process; (None, None) off Windows."""
    if not _WIN:
        return None, None
    c = _pmc(_k32.GetCurrentProcess())
    return c.WorkingSetSize / MB, c.PeakWorkingSetSize / MB


def other_process_mb(pid):
    """(working set MB, peak working set MB) of another process, or None if it cannot be opened."""
    if not _WIN:
        return None
    h = _k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ, 0, pid)
    if not h:
        return None
    try:
        c = _pmc(h)
        return c.WorkingSetSize / MB, c.PeakWorkingSetSize / MB
    except OSError:
        return None
    finally:
        _k32.CloseHandle(h)


def process_alive(pid):
    """True if a process with this pid exists and has not exited (Windows only)."""
    h = _k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, pid)
    if not h:
        return False
    try:
        code = ctypes.c_ulong()
        return bool(_k32.GetExitCodeProcess(h, ctypes.byref(code))) and code.value == STILL_ACTIVE
    finally:
        _k32.CloseHandle(h)


def system_mb():
    """(total physical MB, available physical MB); (None, None) off Windows."""
    if not _WIN:
        return None, None
    m = _MSX()
    m.dwLength = ctypes.sizeof(_MSX)
    if not _k32.GlobalMemoryStatusEx(ctypes.byref(m)):
        raise OSError(ctypes.get_last_error(), "GlobalMemoryStatusEx failed")
    return m.ullTotalPhys / MB, m.ullAvailPhys / MB
