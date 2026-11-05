"""Observe Win32 accessibility events for one owned browser PID."""
import ctypes
from ctypes import wintypes
import json
import sys
import threading
import time


LIVE_REGION_CHANGED = 0x8019
callback_type = ctypes.WINFUNCTYPE(
    None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND, wintypes.LONG,
    wintypes.LONG, wintypes.DWORD, wintypes.DWORD
)
user32 = ctypes.WinDLL('user32', use_last_error=True)
user32.SetWinEventHook.argtypes = [
    wintypes.DWORD, wintypes.DWORD, wintypes.HMODULE, callback_type,
    wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
]
user32.SetWinEventHook.restype = wintypes.HANDLE
user32.UnhookWinEvent.argtypes = [wintypes.HANDLE]
user32.PeekMessageW.argtypes = [
    ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT,
]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]


@callback_type
def observe(_hook, event, _window, object_id, child_id, _thread, _time):
    print(json.dumps({
        'type': 'live_region_changed', 'event': event, 'epoch_ms': time.time_ns() // 1_000_000,
        'object_id': object_id, 'child_id': child_id,
    }), flush=True)


pid = int(sys.argv[1])
message = wintypes.MSG()
user32.PeekMessageW(ctypes.byref(message), None, 0, 0, 0)
hook = user32.SetWinEventHook(LIVE_REGION_CHANGED, LIVE_REGION_CHANGED, None, observe, pid, 0, 0)
if not hook:
    raise ctypes.WinError(ctypes.get_last_error())

done = threading.Event()


def wait_for_stop():
    sys.stdin.readline()
    done.set()


threading.Thread(target=wait_for_stop, daemon=True).start()
print(json.dumps({'type': 'ready', 'pid': pid}), flush=True)
deadline = time.monotonic() + 45
try:
    while not done.is_set() and time.monotonic() < deadline:
        while user32.PeekMessageW(ctypes.byref(message), None, 0, 0, 1):
            user32.DispatchMessageW(ctypes.byref(message))
        done.wait(.01)
finally:
    user32.UnhookWinEvent(hook)
