from __future__ import annotations

import logging
from queue import Empty, Queue
from threading import Event, Lock, Thread

from sqlalchemy import select

from app.core.config import Settings
from app.db.session import Database
from app.models import SessionRecord

logger = logging.getLogger(__name__)


class PostSessionTaskQueue:
    """Small in-process worker for post-session analytics jobs."""

    def __init__(
        self,
        *,
        database: Database,
        settings: Settings,
        service_factory,
    ) -> None:
        self.database = database
        self.settings = settings
        self.service_factory = service_factory
        self._queue: Queue[str | None] = Queue()
        self._pending_ids: set[str] = set()
        self._pending_lock = Lock()
        self._stop_event = Event()
        self._idle_event = Event()
        self._idle_event.set()
        self._worker: Thread | None = None

    def start(self) -> None:
        if self._worker is not None:
            return

        self._worker = Thread(
            target=self._run,
            name="post-session-worker",
            daemon=True,
        )
        self._worker.start()
        self._enqueue_recoverable_sessions()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        self._queue.put(None)
        if self._worker is not None:
            self._worker.join(timeout=timeout)
            self._worker = None

    def enqueue(self, session_id: str) -> bool:
        normalized = session_id.strip()
        if not normalized:
            return False

        with self._pending_lock:
            if normalized in self._pending_ids:
                return False
            self._pending_ids.add(normalized)

        self._idle_event.clear()
        self._queue.put(normalized)
        logger.info("Queued post-session work for %s", normalized)
        return True

    def wait_until_idle(self, timeout: float | None = None) -> bool:
        return self._idle_event.wait(timeout=timeout)

    def _enqueue_recoverable_sessions(self) -> None:
        with self.database.session() as db:
            session_ids = db.scalars(
                select(SessionRecord.session_id)
                .where(SessionRecord.status == "closed")
                .where(SessionRecord.processing_state.in_(("queued", "processing")))
                .order_by(SessionRecord.updated_at.asc(), SessionRecord.id.asc())
            ).all()

        for session_id in session_ids:
            self.enqueue(session_id)

    def _run(self) -> None:
        while True:
            try:
                session_id = self._queue.get(timeout=0.25)
            except Empty:
                if self._stop_event.is_set():
                    break
                continue

            if session_id is None:
                self._queue.task_done()
                break

            try:
                self._process(session_id)
            except Exception:
                logger.exception("Unhandled post-session queue failure for %s", session_id)
            finally:
                with self._pending_lock:
                    self._pending_ids.discard(session_id)
                    if not self._pending_ids and self._queue.unfinished_tasks <= 1:
                        self._idle_event.set()
                self._queue.task_done()

        with self._pending_lock:
            if not self._pending_ids:
                self._idle_event.set()

    def _process(self, session_id: str) -> None:
        with self.database.session() as db:
            service = self.service_factory(db, self.settings, self)
            service.process_post_session_queue_item(session_id)

