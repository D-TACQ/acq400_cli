"""
Utility classes and functions
"""

import time
import inspect
import threading
import logging
import socket
import weakref
import functools
from typing import Any, Callable

from acq400_cli.constants import TIMESTAMP_FMT

class Triplet(str):
    """Helper class for Triplets"""
    def __new__(cls, value, keys=['enabled', 'line', 'sense']):
        if isinstance(value, list):
            value = ",".join(map(str, value))
        value = value.split(' ')[0].lstrip("=")
        obj = super().__new__(cls, value)
        obj.keys = keys
        return obj
    
    def __getitem__(self, key):
        return int(self.split(',')[key])

    def __getattr__(self, attr):
        if attr not in self.keys:
            raise AttributeError(f"{type(self).__name__!r} object has no attribute {attr!r}")
        return int(self[self.keys.index(attr)])
    
    def override(self, name, value):
        arr = self.split(',')
        arr[self.keys.index(name)] = str(value)
        return ','.join(arr)

class DotDict(dict):
    __delattr__ = dict.__delitem__
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


class cached_property:
    """Instanced functools.cached_property"""

    _instance_locks = weakref.WeakKeyDictionary()

    def __init__(self, func):
        self.func = func
        self.attrname = None
        self.__doc__ = func.__doc__

    def __set_name__(self, owner, name):
        self.attrname = name

    def _lock(self, instance):
        locks = self._instance_locks.setdefault(instance, {})
        return locks.setdefault(self.attrname, threading.Lock())

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        cache = instance.__dict__
        if self.attrname in cache:
            return cache[self.attrname]
        with self._lock(instance):
            if self.attrname in cache:
                return cache[self.attrname]
            val = self.func(instance)
            cache[self.attrname] = val
            return val


class RThread(threading.Thread):
    """Thread with return and stop"""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('daemon', True)
        super().__init__(*args, **kwargs)
        self.value = None
        self.exception = None
        self.stop_event = threading.Event()
        self.status = {}
        self.last_status = 0
    
    def run(self):
        try: self.value = self._target(*self._args, **self._kwargs)
        except Exception as e:
            self.exception = e
            logging.debug(f"{self.name} {e}")

    def join(self, *args, **kwargs):
        super().join(*args, **kwargs)
        if self.exception: raise self.exception
        return self.value

    def stop(self):
        self.stop_event.set()

class BackgroundTask:
    """Non blocking proxy UUT thread handler"""

    def __init__(self, threads):
        self.threads = threads

    @property
    def finished(self):
        return all(not t.is_alive() for t in self.threads.values())

    def join(self, *args, **kwargs):
        return {name: t.join(*args, **kwargs) for name, t in self.threads.items()}

    def stop(self):
        for th in self.threads.values():
            th.stop()

    def print_status(self):
        parts = []
        for uutname, thread in self.threads.items():
            for key, value in getattr(thread, 'status', {}).items():
                parts.append(f"{uutname} {key} {value}")
        line = '  '.join(parts)
        pad = getattr(self, '_status_width', 0)
        print('\r' + line.ljust(pad), end='', flush=True)
        self._status_width = max(pad, len(line))

class FanoutProxy(dict):
    """Proxy UUT attributes and methods"""

    def __init__(self, uuts, blocking=True):
        super().__init__(uuts)
        object.__setattr__(self, '_blocking', blocking)
        object.__setattr__(self, '_bg', False)
        object.__setattr__(self, '_parent', None)
        object.__setattr__(self, '_attr', None)

    @property
    def bg(self):
        """Reuse this proxy for the next getattr/call without blocking."""
        object.__setattr__(self, '_bg', True)
        return self

    def _fanout_blocking(self):
        if self._bg:
            object.__setattr__(self, '_bg', False)
            return False
        return self._blocking

    def _fanout(self, fn, *args, blocking=None):
        if blocking is None:
            blocking = self._fanout_blocking()
        threads = {}
        for key, target in self.items():
            thread = RThread(target=fn, args=(target, *args))
            thread._fanout_key = key
            thread.start()
            threads[key] = thread
        if not blocking:
            return BackgroundTask(threads)
        return {key: thread.join() for key, thread in threads.items()}

    def __getattr__(self, name):
        blocking = self._fanout_blocking()
        results = self._fanout(getattr, name, blocking=True)
        proxy = self.__class__(results, blocking)
        object.__setattr__(proxy, '_parent', dict(self))
        object.__setattr__(proxy, '_attr', name)
        return proxy

    def __setattr__(self, name, value):
        if name.startswith('_'):
            object.__setattr__(self, name, value)
            return
        result = self._fanout(setattr, name, value)
        if isinstance(result, BackgroundTask):
            return result

    def __call__(self, *args, **kwargs):
        sample = next(iter(self.values()), None)
        if not callable(sample):
            if self._parent is None or self._attr is None:
                raise TypeError(f'{sample!r} is not callable')
            threads = {}
            for key, target in self._parent.items():
                thread = RThread(target=setattr, args=(target, self._attr, args[0]))
                thread._fanout_key = key
                thread.start()
                threads[key] = thread
            if not self._fanout_blocking():
                return BackgroundTask(threads)
            for thread in threads.values():
                thread.join()
            return

        result = self._fanout(lambda fn: fn(*args, **kwargs))
        if isinstance(result, BackgroundTask):
            return result
        return self.__class__(result, self._blocking)

class StopWatch(list):
    """easy delta time between marks"""
    def __init__(self):
        """Start timer"""
        super().__init__([(0, 'START')]) 
        self.t0 = time.time()

    def mark(self, reason=None):
        t1 = time.time()
        if not reason: reason= f"MARK {len(self)}"
        self.append((t1 - self.t0, reason))

    def __str__(self):
        lines = ['Stopwatch:']
        for elapsed, reason in self:
            lines.append(f"{elapsed:.2f}\t{reason}")
        return '\n'.join(lines)

class SigGen:
    """Send SCPI commands to siggen"""
    def __init__(self, addr):
        logging.debug(f"Initing Siggen {addr}")
        self.addr = addr
        self.socket = socket.socket()
        self.socket.connect((self.addr, 5025))

    def send(self, message):
        logging.trace(message)
        self.socket.send(f"{message}\n".encode())
        if message.endswith('?'): return self.socket.recv(100)

    def trigger(self):
        """Trigger SigGen"""
        self.send("TRIG")
        
    def sync_out(self, enabled=True):
        """Enable of disable output sync"""
        self.send(f"OUTP:SYNC {'ON' if enabled else 'OFF'}")

    def volt_offset_from_range(self, v_min, v_max):
        """Convert input_range to voltage and offset"""
        amplitude = (float(v_max) - float(v_min)) / 2
        offset = (float(v_max) + float(v_min)) / 2
        return amplitude, offset

    def config_free_running(self, freq, voltage, offset=0, shape='SINE'):
        """Configure free running waveform"""
        if isinstance(voltage, (tuple, list)):
            voltage, offset = self.volt_offset_from_range(*voltage)
        self.send('BURS:STAT OFF')
        self.send(f"FREQ {freq}")
        self.send(f"VOLT {voltage}")
        self.send(f"VOLT:OFFS {offset}")
        self.send(f"FUNC:SHAP {shape}")
        self.send('TRIG:SOUR IMM')

    def config_burst(self, freq, voltage, offset=0, shape='SINE', cycles=1, period=None):
        """Config burst waveform"""
        if isinstance(voltage, (tuple, list)):
            voltage, offset = self.volt_offset_from_range(*voltage)
        self.send('BURS:STAT ON')
        self.send(f"FREQ {freq}")
        self.send(f"VOLT {voltage}")
        self.send(f"VOLT:OFFS {offset}")
        self.send(f"FUNC:SHAP {shape}")
        self.send(f"BURS:NCYC {cycles}")
        if period: self.send(f"BURS:INT:PER {period}")
        self.send(f"TRIG:SOUR BUS")

    def config_dc(self, voltage, scaler=2):
        """Config DC out"""
        voltage /= scaler
        self.send("SOUR:FUNC DC")
        self.send(f"SOUR:VOLT:LEV:IMM:OFFS {voltage}")


class Ansi:

    CLEAR = '\033[K'

    @staticmethod
    def move_up(nlines=1):
        if nlines < 1: return
        print(f'\033[{nlines}A', end='')

def is_task_stop():
    """return True if in a thread and thread stop else False"""
    stop = getattr(threading.current_thread(), 'stop_event', None)
    if not stop: return True
    return stop.is_set()

def write_task_status(status, limit=1):
    """write status to thread if status available"""
    thread = threading.current_thread()
    if not hasattr(thread, 'status'): return
    now = time.time()
    if now - thread.last_status < limit: return
    thread.last_status = now
    thread.status = status

def chans_to_bitmask(chans):
    """Converts list of chans to a hex bitmask"""
    return hex(sum(1 << (int(chan) - 1) for chan in sorted(chans)))

def generate_timestamp():
    """Return timestamp"""
    return time.strftime(TIMESTAMP_FMT, time.localtime())

def bitmask_to_chans(mask):
    """Converts a hex bitmask to list of chans"""
    mask = int(mask, 16)
    return [i + 1 for i in range(mask.bit_length()) if mask & (1 << i)]

def background_task(func: Callable[..., Any]) -> Callable[..., RThread]:
    """Runs passed func in the background returns thread"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> RThread:
        thread = RThread(target=func, args=args, kwargs=kwargs)
        thread.daemon = True
        thread.start()
        return thread
    return wrapper

def run_on_all_uuts(func):
    """Run decorated function on all UUTs"""
    sig = inspect.signature(func)
    is_method = sig.parameters.get('self', sig.parameters.get('cls')) != None

    def wrapper(uuts, *args, **kwargs):
        threads = {}
        for uut in uuts:
            threads[uut.hostname] = RThread(target=func, args=[uut, *args], kwargs=kwargs)
            threads[uut.hostname].start()
        for thread in threads.values():
            thread.join()
            if thread.exception is not None: raise thread.exception
        return {uutname: thread.value for uutname, thread in threads.items()}

    def object_wrapper(obj, uuts, *args, **kwargs):
        threads = {}
        for uut in uuts:
            threads[uut.hostname] = RThread(target=func, args=[obj, uut, *args], kwargs=kwargs)
            threads[uut.hostname].start()
        for thread in threads.values():
            thread.join()
            if thread.exception is not None: raise thread.exception
        return {uutname: thread.value for uutname, thread in threads.items()}

    return object_wrapper if is_method else wrapper