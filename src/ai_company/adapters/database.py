"""Shared persistence for lite SQLite and standard PostgreSQL profiles."""

from __future__ import annotations

import re
from threading import RLock
from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
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
    ApprovalMode,
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
LITE_SCHEMA_VERSION = 6


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
    approval_mode: Mapped[str] = mapped_column(String(16), default=ApprovalMode.MANUAL.value)
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
    request_payload: Mapped[dict | None] = mapped_column(JSON_DOCUMENT, nullable=True)
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


class PolicyVersionRow(Base):
    __tablename__ = "policy_versions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    version: Mapped[str] = mapped_column(String(100), unique=True)
    status: Mapped[str] = mapped_column(String(24), default="draft")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON_DOCUMENT)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ModelAssignmentVersionRow(Base):
    __tablename__ = "model_assignment_versions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    version: Mapped[str] = mapped_column(String(100), unique=True)
    status: Mapped[str] = mapped_column(String(24), default="draft")
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    assignments: Mapped[dict] = mapped_column(JSON_DOCUMENT)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProviderCallRow(Base):
    __tablename__ = "provider_call_ledger"
    __table_args__ = (Index("ix_provider_call_task_attempt", "task_attempt_id", "requested_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_attempt_id: Mapped[UUID] = mapped_column(ForeignKey("task_attempts.id"))
    assignment_version_id: Mapped[UUID] = mapped_column(ForeignKey("model_assignment_versions.id"))
    policy_version_id: Mapped[UUID] = mapped_column(ForeignKey("policy_versions.id"))
    provider_key: Mapped[str] = mapped_column(String(100))
    model_key: Mapped[str] = mapped_column(String(200))
    workload: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(32), default="started")
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    usage: Mapped[dict] = mapped_column(JSON_DOCUMENT, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    used_fallback: Mapped[bool] = mapped_column(Boolean, default=False)
    route_reason: Mapped[str] = mapped_column(String(100))


class CostLedgerRow(Base):
    __tablename__ = "cost_ledger"
    __table_args__ = (
        UniqueConstraint("provider_call_id"),
        CheckConstraint("estimated_minor >= 0"),
        CheckConstraint("actual_minor IS NULL OR actual_minor >= 0"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    provider_call_id: Mapped[UUID] = mapped_column(ForeignKey("provider_call_ledger.id"))
    currency: Mapped[str] = mapped_column(String(3))
    estimated_minor: Mapped[int] = mapped_column(Integer)
    actual_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rate_card_version: Mapped[str] = mapped_column(String(100))
    budget_decision_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BudgetPolicyRow(Base):
    __tablename__ = "budget_policies"
    __table_args__ = (CheckConstraint("daily_limit_minor > 0"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    version: Mapped[str] = mapped_column(String(100), unique=True)
    status: Mapped[str] = mapped_column(String(24), default="draft")
    currency: Mapped[str] = mapped_column(String(3))
    daily_limit_minor: Mapped[int] = mapped_column(Integer)
    timezone_name: Mapped[str] = mapped_column(String(64), default="Asia/Ho_Chi_Minh")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DailyBudgetRow(Base):
    __tablename__ = "daily_budgets"
    __table_args__ = (
        UniqueConstraint("policy_id", "local_day"),
        CheckConstraint("reserved_minor >= 0"),
        CheckConstraint("spent_minor >= 0"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    policy_id: Mapped[UUID] = mapped_column(ForeignKey("budget_policies.id"))
    local_day: Mapped[date] = mapped_column(Date)
    reserved_minor: Mapped[int] = mapped_column(Integer, default=0)
    spent_minor: Mapped[int] = mapped_column(Integer, default=0)


class BudgetReservationRow(Base):
    __tablename__ = "budget_reservations"
    __table_args__ = (
        CheckConstraint("estimated_minor >= 0"),
        CheckConstraint("actual_minor IS NULL OR actual_minor >= 0"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    daily_budget_id: Mapped[UUID] = mapped_column(ForeignKey("daily_budgets.id"), index=True)
    task_attempt_id: Mapped[UUID] = mapped_column(ForeignKey("task_attempts.id"), index=True)
    workload: Mapped[str] = mapped_column(String(100))
    estimated_minor: Mapped[int] = mapped_column(Integer)
    actual_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="reserved")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NovelWorkspaceRow(Base):
    __tablename__ = "novel_workspaces"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    story_id: Mapped[UUID] = mapped_column(ForeignKey("stories.id"), unique=True, index=True)
    document: Mapped[dict] = mapped_column(JSON_DOCUMENT)
    row_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


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
    """Initialize or upgrade the local schema; reject unknown future versions."""
    engine = sessions.kw["bind"]
    if engine.dialect.name != "sqlite":
        raise DomainError("Lite schema initialization requires SQLite.")
    with engine.connect() as connection:
        version = connection.exec_driver_sql("PRAGMA user_version").scalar()
    if version == 0:
        Base.metadata.create_all(engine)
        with engine.begin() as connection:
            connection.exec_driver_sql(f"PRAGMA user_version={LITE_SCHEMA_VERSION}")
        return
    if version == 1:
        for table in (
            PolicyVersionRow.__table__,
            ModelAssignmentVersionRow.__table__,
            ProviderCallRow.__table__,
            CostLedgerRow.__table__,
        ):
            table.create(engine, checkfirst=True)
        with engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA user_version=2")
        version = 2
    if version == 2:
        for table in (
            BudgetPolicyRow.__table__,
            DailyBudgetRow.__table__,
            BudgetReservationRow.__table__,
        ):
            table.create(engine, checkfirst=True)
        with engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA user_version=3")
        version = 3
    if version == 3:
        NovelWorkspaceRow.__table__.create(engine, checkfirst=True)
        with engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA user_version=4")
        version = 4
    if version == 4:
        with engine.begin() as connection:
            task_columns = {
                row[1] for row in connection.exec_driver_sql("PRAGMA table_info(tasks)").all()
            }
            if "request_payload" not in task_columns:
                connection.exec_driver_sql("ALTER TABLE tasks ADD COLUMN request_payload JSON")
            connection.exec_driver_sql("PRAGMA user_version=5")
        version = 5
    if version == 5:
        with engine.begin() as connection:
            campaign_columns = {
                row[1] for row in connection.exec_driver_sql("PRAGMA table_info(campaigns)").all()
            }
            if "approval_mode" not in campaign_columns:
                connection.exec_driver_sql(
                    "ALTER TABLE campaigns ADD COLUMN approval_mode VARCHAR(16) NOT NULL DEFAULT 'manual'"
                )
            connection.exec_driver_sql(f"PRAGMA user_version={LITE_SCHEMA_VERSION}")
        version = LITE_SCHEMA_VERSION
    if version != LITE_SCHEMA_VERSION:
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

    def create_campaign(
        self, name: str, source_type: SourceType, target_count: int = 60,
        approval_mode: ApprovalMode = ApprovalMode.MANUAL,
    ) -> UUID:
        if not name.strip() or target_count <= 0:
            raise DomainError("A campaign needs a name and positive target.")
        with self.sessions.begin() as session:
            campaign = CampaignRow(
                name=name.strip(), source_type=source_type.value, target_count=target_count,
                approval_mode=approval_mode.value,
            )
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
                    "approval_mode": row.campaign.approval_mode,
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
            auto_approved = row.campaign.approval_mode == ApprovalMode.AUTO.value
            if auto_approved:
                snapshot = decide_final_review(snapshot, approved=True, at=at)
                row.stage = snapshot.stage.value
                row.review_decision_at = snapshot.review_decision_at
            row.row_version += 1
            session.add(AuditEventRow(entity_type="story", entity_id=story_id, action="production_ready", outcome="ok"))
            if auto_approved:
                session.add(AuditEventRow(
                    entity_type="story", entity_id=story_id,
                    action="auto_final_approved", outcome="ok",
                    details={"approval_mode": ApprovalMode.AUTO.value},
                ))
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


class NovelWorkspaceRepository:
    """Durable local novel workspace with optimistic concurrency and audit events."""

    def __init__(self, sessions: sessionmaker[Session]):
        self.sessions = sessions

    @staticmethod
    def _view(row: NovelWorkspaceRow) -> dict:
        return {
            "workspace_id": str(row.id),
            "story_id": str(row.story_id),
            "row_version": row.row_version,
            "workspace": dict(row.document),
        }

    def create_or_get(self, story_id: UUID, document: dict) -> dict:
        if not isinstance(document, dict) or not document:
            raise DomainError("A novel workspace needs a non-empty document.")
        try:
            with self.sessions.begin() as session:
                if session.get(StoryRow, story_id) is None:
                    raise DomainError("Story does not exist.")
                existing = session.scalar(select(NovelWorkspaceRow).where(
                    NovelWorkspaceRow.story_id == story_id,
                ))
                if existing is not None:
                    return self._view(existing)
                row = NovelWorkspaceRow(story_id=story_id, document=document)
                session.add(row)
                session.flush()
                session.add(AuditEventRow(
                    entity_type="novel_workspace", entity_id=row.id,
                    action="materialized", outcome="ok", details={"story_id": str(story_id)},
                ))
                return self._view(row)
        except IntegrityError:
            # A repeated local click may race with the first materialization.
            return self.get(story_id)

    def get(self, story_id: UUID) -> dict:
        with self.sessions() as session:
            row = session.scalar(select(NovelWorkspaceRow).where(
                NovelWorkspaceRow.story_id == story_id,
            ))
            if row is None:
                raise DomainError("Novel workspace does not exist.")
            return self._view(row)

    def summaries(self, story_ids: tuple[UUID, ...]) -> dict[str, dict]:
        if not story_ids:
            return {}
        with self.sessions() as session:
            rows = session.scalars(select(NovelWorkspaceRow).where(
                NovelWorkspaceRow.story_id.in_(story_ids),
            )).all()
            return {
                str(row.story_id): {
                    "workspace_id": str(row.id),
                    "row_version": row.row_version,
                    "chapter_count": len((row.document or {}).get("chapters", [])),
                    "status": (row.document or {}).get("status", "planning"),
                }
                for row in rows
            }

    def save(
        self, story_id: UUID, expected_version: int, document: dict,
        *, action: str, details: dict | None = None,
    ) -> dict:
        if expected_version <= 0 or not isinstance(document, dict) or not document:
            raise DomainError("Workspace update needs a positive version and document.")
        if not re.fullmatch(r"[a-z0-9_.-]{1,100}", action):
            raise DomainError("Workspace audit action is invalid.")
        now = datetime.now(timezone.utc)
        with self.sessions.begin() as session:
            updated_version = session.execute(
                update(NovelWorkspaceRow)
                .where(
                    NovelWorkspaceRow.story_id == story_id,
                    NovelWorkspaceRow.row_version == expected_version,
                )
                .values(
                    document=document,
                    row_version=NovelWorkspaceRow.row_version + 1,
                    updated_at=now,
                )
                .returning(NovelWorkspaceRow.row_version)
            ).scalar_one_or_none()
            if updated_version is None:
                exists = session.scalar(select(NovelWorkspaceRow.id).where(
                    NovelWorkspaceRow.story_id == story_id,
                ))
                if exists is None:
                    raise DomainError("Novel workspace does not exist.")
                raise DomainError("Novel workspace changed; reload it before saving.")
            row = session.scalar(select(NovelWorkspaceRow).where(
                NovelWorkspaceRow.story_id == story_id,
            ))
            session.add(AuditEventRow(
                entity_type="novel_workspace", entity_id=row.id,
                action=action, outcome="ok", details=details or {},
            ))
            return self._view(row)


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
        request_payload: dict | None = None,
    ) -> UUID:
        if eligible_at.tzinfo is None or attempt_limit <= 0 or not idempotency_key.strip():
            raise DomainError("A task needs a timezone, idempotency key, and positive attempt limit.")
        if request_payload is not None:
            if not isinstance(request_payload, dict):
                raise DomainError("Task request payload must be an object.")
            _assert_safe_ledger_document(request_payload)
        try:
            with self.sessions.begin() as session:
                existing = session.scalar(select(TaskRow).where(TaskRow.idempotency_key == idempotency_key))
                if existing is not None:
                    return self._same_task_or_error(existing, story_id, task_type, request_payload)
                if session.get(StoryRow, story_id) is None:
                    raise DomainError("Story does not exist.")
                task = TaskRow(
                    story_id=story_id,
                    task_type=task_type,
                    idempotency_key=idempotency_key,
                    eligible_at=eligible_at.astimezone(timezone.utc),
                    attempt_limit=attempt_limit,
                    request_payload=request_payload,
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
                return self._same_task_or_error(existing, story_id, task_type, request_payload)

    @staticmethod
    def _same_task_or_error(
        task: TaskRow, story_id: UUID, task_type: str, request_payload: dict | None,
    ) -> UUID:
        if (
            task.story_id != story_id
            or task.task_type != task_type
            or task.request_payload != request_payload
        ):
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

    def get_task_request(self, task_id: UUID) -> dict:
        with self.sessions() as session:
            task = session.get(TaskRow, task_id)
            if task is None:
                raise DomainError("Task does not exist.")
            return dict(task.request_payload or {})

    def get_task_created_at(self, task_id: UUID) -> datetime:
        with self.sessions() as session:
            created_at = session.scalar(select(TaskRow.created_at).where(TaskRow.id == task_id))
            if created_at is None:
                raise DomainError("Task does not exist.")
            return created_at if created_at.tzinfo is not None else created_at.replace(tzinfo=timezone.utc)

    def get_active_attempt_id(self, task_id: UUID, worker_id: str) -> UUID:
        with self.sessions() as session:
            task = session.get(TaskRow, task_id)
            if task is None or task.status != "running" or task.lease_owner != worker_id:
                raise DomainError("This worker does not hold the active task attempt.")
            attempt_id = session.scalar(select(TaskAttemptRow.id).where(
                TaskAttemptRow.task_id == task_id,
                TaskAttemptRow.attempt_no == task.attempt_no,
            ))
            if attempt_id is None:
                raise DomainError("The active task attempt record is missing.")
            return attempt_id

    def list_mock_task_statuses(self, story_ids: tuple[UUID, ...]) -> dict[str, dict]:
        if not story_ids:
            return {}
        task_types = (
            "mock_blueprint", "mock_chapters", "mock_package", "real_blueprint",
            "real_chapter_pipeline",
        )
        with self.sessions() as session:
            rows = session.scalars(select(TaskRow).where(
                TaskRow.story_id.in_(story_ids), TaskRow.task_type.in_(task_types),
            ).order_by(TaskRow.created_at)).all()
            result: dict[str, dict] = {}
            for row in rows:
                status = {
                    "task_id": str(row.id),
                    "status": row.status,
                    "attempt_no": row.attempt_no,
                    "attempt_limit": row.attempt_limit,
                    "directory": row.checkpoint.get("directory")
                    if row.task_type == "mock_package" and row.status == "completed" and row.checkpoint else None,
                }
                if row.task_type == "real_blueprint" and row.status == "completed" and row.checkpoint:
                    status["title"] = row.checkpoint.get("title")
                if row.task_type == "real_chapter_pipeline":
                    status["chapter_number"] = (row.request_payload or {}).get("chapter_number")
                    if row.status == "completed" and row.checkpoint:
                        status["state"] = row.checkpoint.get("state")
                result.setdefault(str(row.story_id), {})[row.task_type] = status
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


def _require_aware(at: datetime) -> datetime:
    if at.tzinfo is None:
        raise DomainError("A timezone-aware timestamp is required.")
    return at.astimezone(timezone.utc)


def _assert_safe_ledger_document(value: object) -> None:
    """Reject obvious credential-shaped fields before durable ledger storage."""
    forbidden = {"secret", "password", "api_key", "apikey", "authorization", "credential", "token"}
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in forbidden or any(part in forbidden for part in normalized.split("_")):
                raise DomainError("Governance and provider ledgers cannot store credentials or tokens.")
            _assert_safe_ledger_document(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            _assert_safe_ledger_document(nested)


class GovernanceRepository:
    """Immutable approvals and append-oriented provider/cost accounting."""

    def __init__(self, sessions: sessionmaker[Session]):
        self.sessions = sessions

    def create_policy_version(self, version: str, payload: dict) -> UUID:
        return self._create_version(PolicyVersionRow, version, "payload", payload)

    def create_assignment_version(self, version: str, assignments: dict) -> UUID:
        return self._create_version(ModelAssignmentVersionRow, version, "assignments", assignments)

    def _create_version(self, row_type, version: str, document_field: str, document: dict) -> UUID:
        if not version.strip() or not isinstance(document, dict) or not document:
            raise DomainError("A version name and non-empty document are required.")
        _assert_safe_ledger_document(document)
        try:
            with self.sessions.begin() as session:
                row = row_type(version=version.strip(), **{document_field: document})
                session.add(row)
                session.flush()
                return row.id
        except IntegrityError as exc:
            raise DomainError(f"Version already exists: {version.strip()}.") from exc

    def approve_policy_version(self, version: str, approved_by: str, at: datetime) -> UUID:
        return self._approve_version(PolicyVersionRow, version, approved_by, at, activate=False)

    def activate_assignment_version(self, version: str, approved_by: str, at: datetime) -> UUID:
        return self._approve_version(ModelAssignmentVersionRow, version, approved_by, at, activate=True)

    def approved_context(self, policy_version: str, assignment_version: str) -> tuple[dict, dict]:
        with self.sessions() as session:
            policy = session.scalar(select(PolicyVersionRow).where(PolicyVersionRow.version == policy_version))
            assignment = session.scalar(
                select(ModelAssignmentVersionRow).where(ModelAssignmentVersionRow.version == assignment_version)
            )
            if policy is None or policy.status != "approved":
                raise DomainError("Provider calls require an approved policy snapshot.")
            if assignment is None or assignment.status != "active":
                raise DomainError("Provider calls require an active model-assignment snapshot.")
            return dict(policy.payload), dict(assignment.assignments)

    def _approve_version(self, row_type, version: str, approved_by: str, at: datetime, *, activate: bool) -> UUID:
        approved_at = _require_aware(at)
        if not approved_by.strip():
            raise DomainError("Approval requires an actor.")
        with self.sessions.begin() as session:
            row = session.scalar(select(row_type).where(row_type.version == version).with_for_update())
            if row is None:
                raise DomainError("The requested version does not exist.")
            if row.status != "draft":
                raise DomainError("An approved version is immutable and cannot be approved again.")
            row.status = "active" if activate else "approved"
            row.approved_at = approved_at
            row.approved_by = approved_by.strip()
            if activate:
                row.effective_at = approved_at
            session.add(AuditEventRow(
                entity_type="model_assignment_version" if activate else "policy_version",
                entity_id=row.id,
                action="activated" if activate else "approved",
                outcome="ok",
                details={"version": row.version},
            ))
            return row.id

    def start_provider_call(
        self,
        *,
        task_attempt_id: UUID,
        policy_version: str,
        assignment_version: str,
        provider_key: str,
        model_key: str,
        workload: str,
        requested_at: datetime,
        estimated_minor: int,
        currency: str,
        rate_card_version: str,
        used_fallback: bool = False,
        route_reason: str = "primary",
        budget_decision_id: UUID | None = None,
    ) -> UUID:
        requested = _require_aware(requested_at)
        required_text = (provider_key, model_key, workload, rate_card_version, route_reason)
        if any(not value.strip() for value in required_text):
            raise DomainError("Provider ledger fields cannot be blank.")
        if estimated_minor < 0 or not re.fullmatch(r"[A-Z]{3}", currency):
            raise DomainError("Cost must be non-negative and currency must be a three-letter uppercase code.")
        with self.sessions.begin() as session:
            attempt = session.get(TaskAttemptRow, task_attempt_id)
            policy = session.scalar(select(PolicyVersionRow).where(PolicyVersionRow.version == policy_version))
            assignment = session.scalar(
                select(ModelAssignmentVersionRow).where(ModelAssignmentVersionRow.version == assignment_version)
            )
            if attempt is None:
                raise DomainError("Provider calls must belong to a persisted task attempt.")
            if policy is None or policy.status != "approved":
                raise DomainError("Provider calls require an approved policy snapshot.")
            if assignment is None or assignment.status != "active":
                raise DomainError("Provider calls require an active model-assignment snapshot.")
            call = ProviderCallRow(
                task_attempt_id=task_attempt_id,
                assignment_version_id=assignment.id,
                policy_version_id=policy.id,
                provider_key=provider_key.strip(),
                model_key=model_key.strip(),
                workload=workload.strip(),
                requested_at=requested,
                used_fallback=used_fallback,
                route_reason=route_reason.strip(),
            )
            session.add(call)
            session.flush()
            session.add(CostLedgerRow(
                provider_call_id=call.id,
                currency=currency,
                estimated_minor=estimated_minor,
                rate_card_version=rate_card_version.strip(),
                budget_decision_id=budget_decision_id,
            ))
            return call.id

    def finish_provider_call(
        self,
        call_id: UUID,
        *,
        completed_at: datetime,
        usage: dict,
        actual_minor: int | None,
        error_code: str | None = None,
    ) -> None:
        completed = _require_aware(completed_at)
        if not isinstance(usage, dict):
            raise DomainError("Provider usage must be a structured document.")
        _assert_safe_ledger_document(usage)
        if actual_minor is not None and actual_minor < 0:
            raise DomainError("Actual cost cannot be negative.")
        if error_code is not None and not re.fullmatch(r"[a-z0-9_.-]{1,100}", error_code):
            raise DomainError("Provider failures must use a redacted machine-readable error code.")
        with self.sessions.begin() as session:
            call = session.scalar(select(ProviderCallRow).where(ProviderCallRow.id == call_id).with_for_update())
            if call is None:
                raise DomainError("Provider call does not exist.")
            if call.status != "started":
                raise DomainError("Provider call completion is recorded only once.")
            requested = call.requested_at
            if requested.tzinfo is None:
                requested = requested.replace(tzinfo=timezone.utc)
            if completed < requested:
                raise DomainError("Provider completion cannot precede its request.")
            call.status = "failed" if error_code else "completed"
            call.completed_at = completed
            call.latency_ms = int((completed - requested).total_seconds() * 1000)
            call.usage = usage
            call.error_code = error_code
            cost = session.scalar(select(CostLedgerRow).where(CostLedgerRow.provider_call_id == call_id))
            if cost is None:
                raise DomainError("Provider call cost reservation is missing.")
            cost.actual_minor = actual_minor


class BudgetRepository:
    """Reserve a conservative upper bound before any external provider call."""

    def __init__(self, sessions: sessionmaker[Session]):
        self.sessions = sessions
        # Lite workers share this repository in one process; serialize SQLite's
        # read-modify-write budget ledger while provider requests run concurrently.
        self._lock = RLock()

    def create_policy(
        self, version: str, currency: str, daily_limit_minor: int, timezone_name: str,
    ) -> UUID:
        if not version.strip() or not re.fullmatch(r"[A-Z]{3}", currency) or daily_limit_minor <= 0:
            raise DomainError("Budget policy needs a version, currency, and positive daily limit.")
        try:
            ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise DomainError("Budget policy timezone is unknown.") from exc
        try:
            with self.sessions.begin() as session:
                row = BudgetPolicyRow(
                    version=version.strip(), currency=currency,
                    daily_limit_minor=daily_limit_minor, timezone_name=timezone_name,
                )
                session.add(row)
                session.flush()
                return row.id
        except IntegrityError as exc:
            raise DomainError(f"Budget policy already exists: {version.strip()}.") from exc

    def activate_policy(self, version: str, approved_by: str, at: datetime) -> UUID:
        approved_at = _require_aware(at)
        if not approved_by.strip():
            raise DomainError("Budget approval requires an actor.")
        with self.sessions.begin() as session:
            row = session.scalar(select(BudgetPolicyRow).where(BudgetPolicyRow.version == version).with_for_update())
            if row is None:
                raise DomainError("Budget policy does not exist.")
            if row.status != "draft":
                raise DomainError("An active budget policy is immutable.")
            row.status = "active"
            row.approved_by = approved_by.strip()
            row.approved_at = approved_at
            session.add(AuditEventRow(
                entity_type="budget_policy", entity_id=row.id,
                action="activated", outcome="ok",
                details={"version": row.version, "currency": row.currency},
            ))
            return row.id

    def reserve(
        self, version: str, task_attempt_id: UUID, workload: str,
        estimated_minor: int, at: datetime,
    ) -> UUID:
        with self._lock:
            return self._reserve(version, task_attempt_id, workload, estimated_minor, at)

    def _reserve(
        self, version: str, task_attempt_id: UUID, workload: str,
        estimated_minor: int, at: datetime,
    ) -> UUID:
        instant = _require_aware(at)
        if not workload.strip() or estimated_minor < 0:
            raise DomainError("Budget reservation needs a workload and non-negative estimate.")
        with self.sessions.begin() as session:
            policy = session.scalar(select(BudgetPolicyRow).where(BudgetPolicyRow.version == version).with_for_update())
            if policy is None or policy.status != "active":
                raise DomainError("Provider calls require an active budget policy.")
            if session.get(TaskAttemptRow, task_attempt_id) is None:
                raise DomainError("Budget reservations must belong to a persisted task attempt.")
            local_day = instant.astimezone(ZoneInfo(policy.timezone_name)).date()
            daily = session.scalar(
                select(DailyBudgetRow)
                .where(DailyBudgetRow.policy_id == policy.id, DailyBudgetRow.local_day == local_day)
                .with_for_update()
            )
            if daily is None:
                daily = DailyBudgetRow(policy_id=policy.id, local_day=local_day)
                session.add(daily)
                session.flush()
            if daily.spent_minor + daily.reserved_minor + estimated_minor > policy.daily_limit_minor:
                raise DomainError("Daily provider budget would be exceeded.")
            daily.reserved_minor += estimated_minor
            reservation = BudgetReservationRow(
                daily_budget_id=daily.id,
                task_attempt_id=task_attempt_id,
                workload=workload.strip(),
                estimated_minor=estimated_minor,
            )
            session.add(reservation)
            session.flush()
            return reservation.id

    def settle(self, reservation_id: UUID, actual_minor: int, at: datetime) -> None:
        with self._lock:
            self._settle(reservation_id, actual_minor, at)

    def _settle(self, reservation_id: UUID, actual_minor: int, at: datetime) -> None:
        settled_at = _require_aware(at)
        if actual_minor < 0:
            raise DomainError("Actual provider cost cannot be negative.")
        with self.sessions.begin() as session:
            reservation = session.scalar(
                select(BudgetReservationRow).where(BudgetReservationRow.id == reservation_id).with_for_update()
            )
            if reservation is None or reservation.status != "reserved":
                raise DomainError("Budget reservation is not open.")
            if actual_minor > reservation.estimated_minor:
                raise DomainError("Actual provider cost exceeded the reserved upper bound.")
            daily = session.scalar(
                select(DailyBudgetRow).where(DailyBudgetRow.id == reservation.daily_budget_id).with_for_update()
            )
            if daily is None or daily.reserved_minor < reservation.estimated_minor:
                raise DomainError("Daily budget accounting is inconsistent.")
            daily.reserved_minor -= reservation.estimated_minor
            daily.spent_minor += actual_minor
            reservation.actual_minor = actual_minor
            reservation.status = "settled"
            reservation.settled_at = settled_at

    def release(self, reservation_id: UUID, at: datetime) -> None:
        with self._lock:
            self._release(reservation_id, at)

    def _release(self, reservation_id: UUID, at: datetime) -> None:
        released_at = _require_aware(at)
        with self.sessions.begin() as session:
            reservation = session.scalar(
                select(BudgetReservationRow).where(BudgetReservationRow.id == reservation_id).with_for_update()
            )
            if reservation is None or reservation.status != "reserved":
                raise DomainError("Budget reservation is not open.")
            daily = session.scalar(
                select(DailyBudgetRow).where(DailyBudgetRow.id == reservation.daily_budget_id).with_for_update()
            )
            if daily is None or daily.reserved_minor < reservation.estimated_minor:
                raise DomainError("Daily budget accounting is inconsistent.")
            daily.reserved_minor -= reservation.estimated_minor
            reservation.actual_minor = 0
            reservation.status = "released"
            reservation.settled_at = released_at

