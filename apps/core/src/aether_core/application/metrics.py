"""Host and per-instance resource metrics (CPU, RAM, disk, processo).

Lê a máquina onde o Core roda. Em container (LXC/Docker) os valores do
psutil já refletem os limites do container quando o cgroup está exposto.
"""

import time
from dataclasses import dataclass, field
from typing import Protocol

import psutil


@dataclass
class HostMetrics:
    cpu_percent: float
    cpu_count: int
    mem_total: int
    mem_used: int
    mem_percent: float
    disk_total: int
    disk_used: int
    disk_percent: float
    uptime_seconds: int
    load_avg: list[float] = field(default_factory=list)


@dataclass
class ProcessMetrics:
    instance_id: str
    pid: int | None
    cpu_percent: float
    mem_bytes: int
    running: bool


class SupervisorLike(Protocol):
    def pid_of(self, instance_id: str) -> int | None: ...


class MetricsService:
    """Coleta métricas com histórico curto em memória (para os gráficos)."""

    def __init__(self, supervisor: SupervisorLike, history_size: int = 120) -> None:
        self._supervisor = supervisor
        self._history: list[dict] = []
        self._history_size = history_size
        # Primeira leitura serve de baseline para o cpu_percent não vir 0.
        psutil.cpu_percent(interval=None)
        self._procs: dict[int, psutil.Process] = {}

    def _proc(self, pid: int) -> psutil.Process:
        """Reaproveita o objeto Process entre coletas.

        ``cpu_percent(interval=None)`` é um delta desde a leitura anterior
        *daquele objeto*: recriar o Process a cada chamada devolvia 0.0 para
        sempre. O cache é o que faz o percentual de CPU existir.
        """
        proc = self._procs.get(pid)
        if proc is None or not proc.is_running():
            proc = psutil.Process(pid)
            self._procs[pid] = proc
            proc.cpu_percent(interval=None)  # baseline
        return proc

    def host(self) -> HostMetrics:
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        try:
            load = list(psutil.getloadavg())
        except (AttributeError, OSError):
            load = []
        return HostMetrics(
            cpu_percent=psutil.cpu_percent(interval=None),
            cpu_count=psutil.cpu_count(logical=True) or 1,
            mem_total=mem.total,
            mem_used=mem.total - mem.available,
            mem_percent=mem.percent,
            disk_total=disk.total,
            disk_used=disk.used,
            disk_percent=disk.percent,
            uptime_seconds=int(time.time() - psutil.boot_time()),
            load_avg=load,
        )

    def process(self, instance_id: str) -> ProcessMetrics:
        pid = self._supervisor.pid_of(instance_id)
        if pid is None:
            return ProcessMetrics(instance_id, None, 0.0, 0, False)
        try:
            proc = self._proc(pid)
            with proc.oneshot():
                # Inclui os filhos: o run.sh do Forge inicia o java como filho.
                mem = proc.memory_info().rss
                cpu = proc.cpu_percent(interval=None)
                for child in proc.children(recursive=True):
                    try:
                        cached = self._proc(child.pid)
                        mem += cached.memory_info().rss
                        cpu += cached.cpu_percent(interval=None)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
            # O cache é compartilhado por todas as instâncias: poda pelo que
            # de fato morreu, nunca pelo que não pertence a esta árvore.
            for morto in [p for p, o in self._procs.items() if not o.is_running()]:
                del self._procs[morto]
            return ProcessMetrics(instance_id, pid, round(cpu, 1), mem, True)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            self._procs.pop(pid, None)
            return ProcessMetrics(instance_id, pid, 0.0, 0, False)

    def sample(self) -> dict:
        """Tira uma amostra e guarda no histórico (para gráficos de linha)."""
        h = self.host()
        point = {
            "ts": int(time.time()),
            "cpu": h.cpu_percent,
            "mem_percent": round(h.mem_percent, 1),
            "mem_used": h.mem_used,
        }
        self._history.append(point)
        if len(self._history) > self._history_size:
            del self._history[0 : len(self._history) - self._history_size]
        return point

    def history(self) -> list[dict]:
        return list(self._history)
