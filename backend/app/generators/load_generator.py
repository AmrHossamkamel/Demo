import time
import math
import psutil
import threading
import multiprocessing
import requests
import logging
from typing import Callable, Optional
from backend.app.config import settings

logger = logging.getLogger("load_generator")

def _cpu_stress_worker(target_percent: int, stop_event: multiprocessing.Event):
    """
    Worker process generating controlled CPU load using duty-cycle sleeping.
    """
    chunk = 0.05 # 50ms interval
    work_time = chunk * (target_percent / 100.0)
    sleep_time = chunk - work_time

    while not stop_event.is_set():
        start = time.time()
        # Busy loop for work_time
        while (time.time() - start) < work_time:
            _ = math.sqrt(12345.6789) * math.sin(987.65)
        if sleep_time > 0:
            time.sleep(sleep_time)

class LoadGenerator:
    """
    Generates isolated, safe, and bounded physical infrastructure load
    (CPU, Memory, Traffic) on the EC2 host for Dynatrace monitoring.
    """
    @staticmethod
    def run_cpu_stress(duration_seconds: int, target_cpu_percent: int = 70, is_cancelled: Optional[Callable[[], bool]] = None) -> int:
        target_cpu_percent = min(target_cpu_percent, settings.MAX_CPU_LOAD_PERCENT)
        duration_seconds = min(duration_seconds, settings.MAX_SCENARIO_DURATION_SECONDS)

        num_cores = max(1, multiprocessing.cpu_count() - 1)
        stop_event = multiprocessing.Event()
        workers = []

        logger.info(f"Starting CPU stress: target={target_cpu_percent}%, duration={duration_seconds}s, cores={num_cores}")

        for _ in range(num_cores):
            p = multiprocessing.Process(target=_cpu_stress_worker, args=(target_cpu_percent, stop_event))
            p.daemon = True
            p.start()
            workers.append(p)

        start_time = time.time()
        try:
            while (time.time() - start_time) < duration_seconds:
                if is_cancelled and is_cancelled():
                    logger.info("CPU stress cancelled early via safety controller.")
                    break
                time.sleep(0.5)
        finally:
            stop_event.set()
            for p in workers:
                p.join(timeout=1)
                if p.is_alive():
                    p.terminate()

        logger.info("CPU stress completed safely.")
        return int(time.time() - start_time)

    @staticmethod
    def run_memory_stress(duration_seconds: int, target_mb: int = 500, is_cancelled: Optional[Callable[[], bool]] = None) -> int:
        target_mb = min(target_mb, settings.MAX_MEMORY_ALLOCATION_MB)
        duration_seconds = min(duration_seconds, settings.MAX_SCENARIO_DURATION_SECONDS)

        logger.info(f"Starting Memory stress: target={target_mb}MB, duration={duration_seconds}s")
        data_block = None
        try:
            # Allocate bytearray (1MB = 1,048,576 bytes)
            data_block = bytearray(target_mb * 1024 * 1024)
            # Touch memory to ensure actual physical allocation
            for i in range(0, len(data_block), 1024 * 1024):
                data_block[i] = 1

            start_time = time.time()
            while (time.time() - start_time) < duration_seconds:
                if is_cancelled and is_cancelled():
                    break
                time.sleep(0.5)
        finally:
            del data_block
            logger.info("Memory stress released memory block safely.")

        return duration_seconds

    @staticmethod
    def run_traffic_stress(url: str, duration_seconds: int, rps: int = 20, is_cancelled: Optional[Callable[[], bool]] = None) -> int:
        rps = min(rps, settings.MAX_REQUESTS_PER_SECOND)
        duration_seconds = min(duration_seconds, settings.MAX_SCENARIO_DURATION_SECONDS)

        logger.info(f"Starting Traffic stress to {url}: rps={rps}, duration={duration_seconds}s")
        total_requests = 0
        start_time = time.time()

        while (time.time() - start_time) < duration_seconds:
            if is_cancelled and is_cancelled():
                break

            interval_start = time.time()
            for _ in range(rps):
                try:
                    requests.get(url, timeout=1)
                    total_requests += 1
                except Exception:
                    pass

            elapsed = time.time() - interval_start
            sleep_time = max(0.0, 1.0 - elapsed)
            time.sleep(sleep_time)

        logger.info(f"Traffic stress completed: {total_requests} total requests sent.")
        return total_requests

load_generator = LoadGenerator()
