"""Shared persistence for lite SQLite and standard PostgreSQL profiles."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    create_engine,
    event,
    func,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

from ai_company.domain.policy import CampaignStatus
from ai_company.domain.workflow import (
    ArtifactEvidence,
    Chapter,
    DomainError,
    GateName,
    GateOutcome,
    SourceType,
    StorySnapshot,
    StoryStage,
    decide_final_review,
    mark_production_ready,
)


class Base(DeclarativeBase):
    pass


JSON_DOCUMENT = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CampaignRow(Base):
    __tablename__ = "campaigns"
    __table_args__ = (CheckConstraint("target_count > 0"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200))
    source_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(48), default=CampaignStatus.DRAFT.value)
    target_count: Mapped[int] = mapped_column(Integer, default=60)
    kpi_timezone: Mapped[str] = mapped_column(String(64), default="Asia/Ho_Chi_Minh")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    stories: Mapped[list[StoryRow]] = relationship(back_populates="campaign")


class StoryRow(Base):
    __tablename__ = "stories"
    __table_args__ = (Index("ix_stories_ready_at", "production_ready_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    campaign_id: Mapped[UUID] = mapped_column(ForeignKey("campaigns.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(32))
    idea: Mapped[str | None] = mapped_column(Text, nullable=True)
    stage: Mapped[str] = mapped_column(String(48), default=StoryStage.DRAFT.value)
    planned_chapters: Mapped[int] = mapped_column(Integer, default=0)
    has_story_bible: Mapped[bool] = mapped_column(Boolean, default=False)
    has_hook_contract: Mapped[bool] = mapped_column(Boolean, default=False)
    production_ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_decision_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    row_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    campaign: Mapped[CampaignRow] = relationship(back_populates="stories")
    chapters: Mapped[list[ChapterRow]] = relationship(back_populates="story", cascade="all, delete-orphan")
    gates: Mapped[list[GateRow]] = relationship(back_populates="story", cascade="all, delete-orphan")
    artifacts: Mapped[list[ArtifactRow]] = relationship(back_populates="story", cascade="all, delete-orphan")


class ChapterRow(Base):
    __tablename__ = "chapters"
    __table_args__ = (
        UniqueConstraint("story_id", "number"),
        CheckConstraint("number BETWEEN 1 AND 20"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    story_id: Mapped[UUID] = mapped_column(ForeignKey("stories.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(300))
    recap: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text)
    story: Mapped[StoryRow] = relationship(back_populates="chapters")


class GateRow(Base):
    __tablename__ = "gate_decisions"
    __table_args__ = (UniqueConstraint("story_id", "gate_name"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    story_id: Mapped[UUID] = mapped_column(ForeignKey("stories.id"), index=True)
    gate_name: Mapped[str] = mapped_column(String(64))
    outcome: Mapped[str] = mapped_column(String(32))
    evidence: Mapped[dict] = mapped_column(JSON_DOCUMENT, default=dict)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    story: Mapped[StoryRow] = relationship(back_populates="gates")


class ArtifactRow(Base):
    __tablename__ = "artifacts"
    __table_args__ = (UniqueConstraint("story_id", "filename"), CheckConstraint("byte_size > 0"))

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    story_id: Mapped[UUID] = mapped_column(ForeignKey("stories.id"), index=True)
    filename: Mapped[str] = mapped_column(String(100))
    storage_uri: Mapped[str] = mapped_column(Text)
    sha256_hex: Mapped[str] = mapped_column(String(64))
    byte_size: Mapped[int] = mapped_column(Integer)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)
    story: Mapped[StoryRow] = relationship(back_populates="artifacts")


class AuditEventRow(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_entity", "entity_type", "entity_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    entity_type: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[UUID] = mapped_column(Uuid)
    action: Mapped[str] = mapped_column(String(100))
    outcome: Mapped[str] = mapped_column(String(30))
    details: Mapped[dict] = mapped_column(JSON_DOCUMENT, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TaskRow(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("idempotency_key"),
        Index("ix_tasks_claim", "status", "eligible_at"),
        CheckConstraint("attempt_limit > 0"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    story_id: Mapped[UUID] = mapped_column(ForeignKey("stories.id"), index=True)
    task_type: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(40), default="queued")
    idempotency_key: Mapped[str] = mapped_column(String(200))
    eligible_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempt_limit: Mapped[int] = mapped_column(Integer, default=1)
    attempt_no: Mapped[int] = mapped_column(Integer, default=0)
    lease_owner: Mapped[str | None] = mapped_column(String(200), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checkpoint: Mapped[dict | None] = mapped_column(JSON_DOCUMENT, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TaskAttemptRow(Base):
    __tablename__ = "task_attempts"
    __table_args__ = (UniqueConstraint("task_id", "attempt_no"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(ForeignKey("tasks.id"), index=True)
    attempt_no: Mapped[int] = mapped_column(Integer)
    worker_id: Mapped[str] = mapped_column(String(200))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(40), nullable=True)
    failure_class: Mapped[str | None] = mapped_column(String(40), nullable=True)


def make_session_factory(database_url: str) -> sessionmaker[Session]:
    engine = create_engine(database_url, pool_pre_ping=True)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def _configure_sqlite(dbapi_connection, _connection_record) -> None:
            dbapi_connection.execute("PRAGMA foreign_keys=ON")
            dbapi_connection.execute("PRAGMA busy_timeout=5000")
            dbapi_connection.execute("PRAGMA synchronous=FULL")

        if database_url not in {"sqlite://", "sqlite:///:memory:", "sqlite+pysqlite:///:memory:"}:
            with engine.connect() as connection:
                mode = connection.exec_driver_sql("PRAGMA journal_mode=WAL").scalar()
                if mode != "wal":
                    raise RuntimeError("SQLite WAL mode could not be enabled.")
    return sessionmaker(engine, expire_on_commit=False)


def initialize_lite_schema(sessions: sessionmaker[Session]) -> None:
    """Initialize schema v1 on a new local database; reject unknown versions."""
    engine = sessions.kw["bind"]
    if engine.dialect.name != "sqlite":
        raise DomainError("Lite schema initialization requires SQLite.")
    with engine.connect() as connection:
        version = connection.exec_driver_sql("PRAGMA user_version").scalar()
    if version == 0:
        Base.metadata.create_all(engine)
        with engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA user_version=1")
    elif version != 1:
        raise DomainError(f"Unsupported lite database schema version: {version}.")


def snapshot_from_row(row: StoryRow) -> StorySnapshot:
    chapters = tuple(
        Chapter(item.number, item.title, item.content, item.recap)
        for item in sorted(row.chapters, key=lambda chapter: chapter.number)
    )
    gates = {GateName(item.gate_name): GateOutcome(item.outcome) for item in row.gates}
    artifacts = {
        item.filename: ArtifactEvidence(
            item.filename, item.sha256_hex, item.byte_size, item.verified, item.is_mock
        )
        for item in row.artifacts
    }
    ready_at = row.production_ready_at
    review_at = row.review_decision_at
    # SQLite loses timezone info in tests; PostgreSQL TIMESTAMPTZ is timezone aware.
    if ready_at is not None and ready_at.tzinfo is None:
        ready_at = ready_at.replace(tzinfo=timezone.utc)
    if review_at is not None and review_at.tzinfo is None:
        review_at = review_at.replace(tzinfo=timezone.utc)
    return StorySnapshot(
        id=row.id,
        source_type=SourceType(row.source_type),
        stage=StoryStage(row.stage),
        chapters=chapters,
        gates=gates,
        artifacts=artifacts,
        production_ready_at=ready_at,
        review_decision_at=review_at,
        planned_chapters=row.planned_chapters,
        has_story_bible=row.has_story_bible,
        has_hook_contract=row.has_hook_contract,
    )


class StoryRepository:
    def __init__(self, sessions: sessionmaker[Session]):
        self.sessions = sessions

    def create_campaign(self, name: str, source_type: SourceType, target_count: int = 60) -> UUID:
        if not name.strip() or target_count <= 0:
            raise DomainError("A campaign needs a name and positive target.")
        with self.sessions.begin() as session:
            campaign = CampaignRow(name=name.strip(), source_type=source_type.value, target_count=target_count)
            session.add(campaign)
            session.flush()
            session.add(AuditEventRow(entity_type="campaign", entity_id=campaign.id, action="created", outcome="ok"))
            return campaign.id

    def create_story(self, campaign_id: UUID, source_type: SourceType, idea: str | None) -> UUID:
        if source_type != SourceType.USER_IDEA:
            raise DomainError("This initial API slice accepts user_idea drafts only.")
        if not (idea or "").strip():
            raise DomainError("A user-idea story needs a premise.")
        with self.sessions.begin() as session:
            campaign = session.get(CampaignRow, campaign_id)
            if campaign is None:
                raise DomainError("Campaign does not exist.")
            if campaign.source_type != source_type.value:
                raise DomainError("The story source type must match its campaign.")
            story = StoryRow(campaign_id=campaign_id, source_type=source_type.value, idea=idea)
            session.add(story)
            session.flush()
            session.add(AuditEventRow(entity_type="story", entity_id=story.id, action="created", outcome="ok"))
            return story.id

    def health(self) -> bool:
        with self.sessions() as session:
            return session.scalar(select(1)) == 1

    def get_story(self, story_id: UUID) -> StorySnapshot:
        with self.sessions() as session:
            row = session.get(StoryRow, story_id)
            if row is None:
                raise DomainError("Story does not exist.")
            return snapshot_from_row(row)

    def get_story_idea(self, story_id: UUID) -> str:
        with self.sessions() as session:
            row = session.get(StoryRow, story_id)
            if row is None or row.source_type != SourceType.USER_IDEA.value or not row.idea:
                raise DomainError("A user-idea story premise is required.")
            return row.idea

    def list_mock_drafts(self, limit: int = 30) -> list[dict]:
        if not 1 <= limit <= 100:
            raise DomainError("Story list limit must be between 1 and 100.")
        with self.sessions() as session:
            rows = session.scalars(
                select(StoryRow)
                .where(StoryRow.source_type == SourceType.USER_IDEA.value)
                .order_by(StoryRow.created_at.desc(), StoryRow.id.desc())
                .limit(limit)
            ).all()
            return [
                {
                    "id": str(row.id),
                    "idea": row.idea or "",
                    "stage": row.stage,
                    "created_at": row.created_at.replace(tzinfo=timezone.utc).isoformat()
                    if row.created_at.tzinfo is None else row.created_at.isoformat(),
                }
                for row in rows
            ]

    def record_production_ready(self, story_id: UUID, at: datetime) -> StorySnapshot:
        with self.sessions.begin() as session:
            row = session.scalar(select(StoryRow).where(StoryRow.id == story_id).with_for_update())
            if row is None:
                raise DomainError("Story does not exist.")
            snapshot = mark_production_ready(snapshot_from_row(row), at)
            row.stage = snapshot.stage.value
            row.production_ready_at = snapshot.production_ready_at
            row.row_version += 1
            session.add(AuditEventRow(entity_type="story", entity_id=story_id, action="production_ready", outcome="ok"))
            return snapshot

    def record_final_review(self, story_id: UUID, approved: bool, at: datetime) -> StorySnapshot:
        with self.sessions.begin() as session:
            row = session.scalar(select(StoryRow).where(StoryRow.id == story_id).with_for_update())
            if row is None:
                raise DomainError("Story does not exist.")
            snapshot = decide_final_review(snapshot_from_row(row), approved=approved, at=at)
            row.stage = snapshot.stage.value
            row.review_decision_at = snapshot.review_decision_at
            row.row_version += 1
            session.add(AuditEventRow(entity_type="story", entity_id=story_id,
                                      action="final_approved" if approved else "human_rejected", outcome="ok"))
            return snapshot


class TaskRepository:
    """DB-controlled task claims. Queue delivery carries only task IDs."""

    def __init__(self, sessions: sessionmaker[Session]):
        self.sessions = sessions

    def create_task(
        self,
        story_id: UUID,
        task_type: str,
        idempotency_key: str,
        eligible_at: datetime,
        attempt_limit: int = 1,
    ) -> UUID:
        if eligible_at.tzinfo is None or attempt_limit <= 0 or not idempotency_key.strip():
            raise DomainError("A task needs a timezone, idempotency key, and positive attempt limit.")
        try:
            with self.sessions.begin() as session:
                existing = session.scalar(select(TaskRow).where(TaskRow.idempotency_key == idempotency_key))
                if existing is not None:
                    return self._same_task_or_error(existing, story_id, task_type)
                if session.get(StoryRow, story_id) is None:
                    raise DomainError("Story does not exist.")
                task = TaskRow(
                    story_id=story_id,
                    task_type=task_type,
                    idempotency_key=idempotency_key,
                    eligible_at=eligible_at.astimezone(timezone.utc),
                    attempt_limit=attempt_limit,
                )
                session.add(task)
                session.flush()
                return task.id
        except IntegrityError:
            # A competing request may have committed the same unique key.
            with self.sessions() as session:
                existing = session.scalar(select(TaskRow).where(TaskRow.idempotency_key == idempotency_key))
                if existing is None:
                    raise
                return self._same_task_or_error(existing, story_id, task_type)

    @staticmethod
    def _same_task_or_error(task: TaskRow, story_id: UUID, task_type: str) -> UUID:
        if task.story_id != story_id or task.task_type != task_type:
            raise DomainError("An idempotency key is already used by another task.")
        return task.id

    def claim_task(
        self,
        task_id: UUID,
        worker_id: str,
        at: datetime,
        lease_seconds: int = 60,
        *,
        max_active_tasks: int | None = None,
    ) -> bool:
        if at.tzinfo is None or lease_seconds <= 0 or not worker_id.strip():
            raise DomainError("A claim needs worker ID, timezone, and positive lease duration.")
        if max_active_tasks is not None and max_active_tasks <= 0:
            return False
        with self.sessions.begin() as session:
            claimed_at = at.astimezone(timezone.utc)
            statement = (
                update(TaskRow)
                .where(
                    TaskRow.id == task_id,
                    TaskRow.status == "queued",
                    TaskRow.eligible_at <= claimed_at,
                    TaskRow.attempt_no < TaskRow.attempt_limit,
                )
            )
            if max_active_tasks is not None:
                active_count = select(func.count(TaskRow.id)).where(TaskRow.status == "running").scalar_subquery()
                statement = statement.where(active_count < max_active_tasks)
            claim_result = session.execute(
                statement.values(
                    status="running",
                    attempt_no=TaskRow.attempt_no + 1,
                    lease_owner=worker_id,
                    lease_expires_at=claimed_at + timedelta(seconds=lease_seconds),
                )
                .returning(TaskRow.attempt_no)
            ).scalar_one_or_none()
            if claim_result is None:
                return False
            session.add(TaskAttemptRow(
                task_id=task_id,
                attempt_no=claim_result,
                worker_id=worker_id,
                started_at=claimed_at,
            ))
            return True

    def complete_task(self, task_id: UUID, worker_id: str, at: datetime, *, checkpoint: dict | None = None) -> None:
        if at.tzinfo is None:
            raise DomainError("A timezone-aware timestamp is required.")
        with self.sessions.begin() as session:
            completed_at = at.astimezone(timezone.utc)
            attempt_no = session.execute(
                update(TaskRow)
                .where(
                    TaskRow.id == task_id,
                    TaskRow.status == "running",
                    TaskRow.lease_owner == worker_id,
                    TaskRow.lease_expires_at >= completed_at,
                )
                .values(status="completed", checkpoint=checkpoint, lease_owner=None, lease_expires_at=None)
                .returning(TaskRow.attempt_no)
            ).scalar_one_or_none()
            if attempt_no is None:
                raise DomainError("This worker does not hold a valid active task lease.")
            attempt = session.scalar(select(TaskAttemptRow).where(
                TaskAttemptRow.task_id == task_id,
                TaskAttemptRow.attempt_no == attempt_no,
            ))
            if attempt is None:
                raise DomainError("The task attempt record is missing.")
            attempt.finished_at = completed_at
            attempt.outcome = "completed"

    def next_eligible_task_id(self, at: datetime, supported_types: tuple[str, ...]) -> UUID | None:
        if at.tzinfo is None:
            raise DomainError("A timezone-aware timestamp is required.")
        if not supported_types:
            return None
        with self.sessions() as session:
            return session.scalar(
                select(TaskRow.id)
                .where(
                    TaskRow.status == "queued",
                    TaskRow.eligible_at <= at.astimezone(timezone.utc),
                    TaskRow.task_type.in_(supported_types),
                )
                .order_by(TaskRow.eligible_at, TaskRow.created_at)
                .limit(1)
            )

    def get_task_type(self, task_id: UUID) -> str:
        with self.sessions() as session:
            task_type = session.scalar(select(TaskRow.task_type).where(TaskRow.id == task_id))
            if task_type is None:
                raise DomainError("Task does not exist.")
            return task_type

    def get_task_story_id(self, task_id: UUID) -> UUID:
        with self.sessions() as session:
            story_id = session.scalar(select(TaskRow.story_id).where(TaskRow.id == task_id))
            if story_id is None:
                raise DomainError("Task does not exist.")
            return story_id

    def get_task_created_at(self, task_id: UUID) -> datetime:
        with self.sessions() as session:
            created_at = session.scalar(select(TaskRow.created_at).where(TaskRow.id == task_id))
            if created_at is None:
                raise DomainError("Task does not exist.")
            return created_at if created_at.tzinfo is not None else created_at.replace(tzinfo=timezone.utc)

    def list_mock_task_statuses(self, story_ids: tuple[UUID, ...]) -> dict[str, dict]:
        if not story_ids:
            return {}
        task_types = ("mock_blueprint", "mock_chapters", "mock_package")
        with self.sessions() as session:
            rows = session.scalars(select(TaskRow).where(
                TaskRow.story_id.in_(story_ids), TaskRow.task_type.in_(task_types),
            )).all()
            result: dict[str, dict] = {}
            for row in rows:
                result.setdefault(str(row.story_id), {})[row.task_type] = {
                    "task_id": str(row.id),
                    "status": row.status,
                    "attempt_no": row.attempt_no,
                    "attempt_limit": row.attempt_limit,
                    "directory": row.checkpoint.get("directory")
                    if row.task_type == "mock_package" and row.status == "completed" and row.checkpoint else None,
                }
            return result

    def get_task_result(self, task_id: UUID, story_id: UUID, *, expected_type: str) -> dict:
        """Read a story-scoped task result without exposing worker lease details."""
        with self.sessions() as session:
            task = session.get(TaskRow, task_id)
            if task is None or task.story_id != story_id or task.task_type != expected_type:
                raise DomainError("Task does not belong to this story or operation.")
            return {
                "task_id": str(task.id),
                "status": task.status,
                "checkpoint": task.checkpoint if task.status == "completed" else None,
            }

    def get_task_result_by_key(self, story_id: UUID, key: str, *, expected_type: str) -> dict:
        with self.sessions() as session:
            task = session.scalar(select(TaskRow).where(TaskRow.idempotency_key == key))
            if task is None or task.story_id != story_id or task.task_type != expected_type:
                raise DomainError("Required task result does not belong to this story or operation.")
            return {
                "task_id": str(task.id),
                "status": task.status,
                "checkpoint": task.checkpoint if task.status == "completed" else None,
            }

    def fail_task(self, task_id: UUID, worker_id: str, at: datetime, reason_code: str) -> None:
        if at.tzinfo is None or not reason_code.strip():
            raise DomainError("Task failure needs a timezone and reason code.")
        with self.sessions.begin() as session:
            attempt_no = session.execute(
                update(TaskRow)
                .where(
                    TaskRow.id == task_id,
                    TaskRow.status == "running",
                    TaskRow.lease_owner == worker_id,
                    TaskRow.lease_expires_at >= at.astimezone(timezone.utc),
                )
                .values(status="technical_failure", lease_owner=None, lease_expires_at=None)
                .returning(TaskRow.attempt_no)
            ).scalar_one_or_none()
            if attempt_no is None:
                raise DomainError("This worker does not hold a valid active task lease.")
            attempt = session.scalar(select(TaskAttemptRow).where(
                TaskAttemptRow.task_id == task_id,
                TaskAttemptRow.attempt_no == attempt_no,
            ))
            if attempt is None:
                raise DomainError("The task attempt record is missing.")
            attempt.finished_at = at.astimezone(timezone.utc)
            attempt.outcome = "technical_failure"
            attempt.failure_class = "technical_failure"
            session.add(AuditEventRow(
                entity_type="task", entity_id=task_id, action="technical_failure",
                outcome="failed", details={"reason_code": reason_code},
            ))

    def retry_failed_mock_package(self, task_id: UUID, at: datetime) -> None:
        """Operator-requested retry; never resets attempts or touches other task types."""
        if at.tzinfo is None:
            raise DomainError("A timezone-aware timestamp is required.")
        with self.sessions.begin() as session:
            task = session.scalar(select(TaskRow).where(TaskRow.id == task_id).with_for_update())
            if task is None or task.task_type != "mock_package":
                raise DomainError("Only a mock package task can be retried here.")
            if task.status != "technical_failure" or task.attempt_no >= task.attempt_limit:
                raise DomainError("This mock package has no eligible technical-failure retry.")
            task.status = "queued"
            task.eligible_at = at.astimezone(timezone.utc)
            task.lease_owner = None
            task.lease_expires_at = None
            session.add(AuditEventRow(
                entity_type="task", entity_id=task_id,
                action="mock_package_retry_requested", outcome="queued",
                details={"attempt_no": task.attempt_no, "attempt_limit": task.attempt_limit},
            ))

    def hold_interrupted_tasks(self, at: datetime, *, force_all: bool = False) -> int:
        """Hold interrupted tasks; startup uses force_all before workers start."""
        if at.tzinfo is None:
            raise DomainError("A timezone-aware timestamp is required.")
        held = 0
        with self.sessions.begin() as session:
            candidates = session.scalars(select(TaskRow).where(TaskRow.status == "running").with_for_update()).all()
            for task in candidates:
                expiry = task.lease_expires_at
                if expiry is None:
                    continue
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                if force_all or expiry <= at:
                    task.status = "awaiting_recovery_confirmation"
                    attempt = session.scalar(select(TaskAttemptRow).where(
                        TaskAttemptRow.task_id == task.id,
                        TaskAttemptRow.attempt_no == task.attempt_no,
                    ))
                    if attempt is not None and attempt.finished_at is None:
                        attempt.finished_at = at.astimezone(timezone.utc)
                        attempt.outcome = "interrupted"
                    held += 1
        return held

    def list_recovery_tasks(self) -> tuple[UUID, ...]:
        with self.sessions() as session:
            return tuple(session.scalars(
                select(TaskRow.id)
                .where(TaskRow.status == "awaiting_recovery_confirmation")
                .order_by(TaskRow.created_at)
            ).all())

    def confirm_recovery(self, task_id: UUID) -> None:
        with self.sessions.begin() as session:
            task = session.scalar(select(TaskRow).where(TaskRow.id == task_id).with_for_update())
            if task is None or task.status != "awaiting_recovery_confirmation":
                raise DomainError("This task is not awaiting recovery confirmation.")
            task.status = "queued" if task.attempt_no < task.attempt_limit else "technical_failure"
            task.lease_owner = None
            task.lease_expires_at = None
            session.add(AuditEventRow(
                entity_type="task", entity_id=task_id,
                action="recovery_confirmed", outcome=task.status,
            ))

