"""Process-local product render jobs. Cancellation never publishes a partial video."""
from concurrent.futures import ThreadPoolExecutor
import copy
from pathlib import Path
import threading
import uuid

from gilvy.errors import GilvyError


class RenderCancelled(GilvyError):
    pass


class RenderControl:
    def __init__(self):
        self.lock = threading.RLock()
        self.cancelled = threading.Event()
        self.data = {"status": "queued", "rendered_frames": 0, "total_frames": 0,
                     "slowest_frame": None}

    def check(self):
        if self.cancelled.is_set():
            raise RenderCancelled("render cancelled before publication")

    def update(self, status, **fields):
        self.check()
        with self.lock:
            self.data.update(status=status, **fields)

    def frame_done(self, index, elapsed):
        with self.lock:
            slow = self.data["slowest_frame"]
            if slow is None or elapsed > slow["seconds"]:
                self.data["slowest_frame"] = {"frame": index, "seconds": elapsed}

    def publish(self, callback):
        # Serialize cancellation against the commit point. Once published, a
        # cancellation request reports false rather than claiming rollback.
        with self.lock:
            self.check()
            callback()
            self.data["status"] = "published"

    def snapshot(self):
        with self.lock:
            return copy.deepcopy(self.data)


class RenderJobs:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gilvy-render")
        self.lock = threading.Lock()
        self.jobs = {}

    def start(self, spec_path, output, start=0, duration=None):
        from gilvy.product import load_product
        from gilvy.product_render import render_product
        # Reject invalid input synchronously, before allocating a job.
        source = Path(spec_path).expanduser().resolve()
        film = load_product(source)
        dest = Path(output).expanduser().resolve()
        if dest.suffix.lower() != ".mp4":
            raise GilvyError("product output must end in .mp4")
        from gilvy.product import finite
        if not finite(start) or not 0 <= start < film.duration:
            raise GilvyError("invalid product start time")
        if duration is not None and (not finite(duration) or duration <= 0 or start+duration > film.duration+1e-9):
            raise GilvyError("invalid product render window")
        with self.lock:
            if any(j["output"] == str(dest) and j["control"].snapshot()["status"] not in ("completed", "failed", "cancelled")
                   for j in self.jobs.values()):
                raise GilvyError("an active job already owns this output")
            if sum(j["control"].snapshot()["status"] not in ("completed", "failed", "cancelled")
                   for j in self.jobs.values()) >= 8:
                raise GilvyError("at most eight active render jobs")
            for key in list(self.jobs):
                if len(self.jobs) < 32: break
                if self.jobs[key]["control"].snapshot()["status"] in ("completed", "failed", "cancelled"):
                    del self.jobs[key]
            identifier = uuid.uuid4().hex
            control = RenderControl()
            self.jobs[identifier] = {"control": control, "output": str(dest)}

        def run():
            try:
                result = render_product(source, dest, start, duration, control=control)
                with control.lock:
                    control.data.update(status="completed", result=result)
            except Exception as exc:
                with control.lock:
                    control.data.update(status="cancelled" if isinstance(exc, RenderCancelled) else "failed", error=str(exc))

        self.executor.submit(run)
        return {"job_id": identifier, "status": "queued", "scope": "current MCP process"}

    def get(self, identifier):
        with self.lock:
            job = self.jobs.get(identifier)
            if job is None: raise GilvyError("unknown render job in this process")
            return {"job_id": identifier, "output": job["output"], **job["control"].snapshot()}

    def cancel(self, identifier):
        with self.lock:
            job = self.jobs.get(identifier)
            if job is None: raise GilvyError("unknown render job in this process")
            control = job["control"]
            with control.lock:
                accepted = control.data["status"] not in ("published", "completed", "failed", "cancelled")
                if accepted: control.cancelled.set()
            return {**control.snapshot(), "job_id": identifier, "cancel_requested": accepted}


jobs = RenderJobs()
