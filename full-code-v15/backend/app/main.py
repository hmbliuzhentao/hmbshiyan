"""VideoHub MVP API. Local-volume storage; replace with object storage in production."""
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal, ROUND_HALF_UP
import csv
import io
from pathlib import Path
from typing import Annotated

import jwt
from fastapi import FastAPI, Depends, HTTPException, Request, Response, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from pwdlib import PasswordHash
from sqlalchemy import create_engine, String, Integer, DateTime, ForeignKey, func, select, text, Date, Boolean, or_
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session, sessionmaker
from sqlalchemy.engine import URL

# URL.create correctly escapes special characters in the database password.
if all(os.environ.get(key) for key in ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB")):
    DATABASE_URL = URL.create("postgresql+psycopg", username=os.environ["POSTGRES_USER"],
                              password=os.environ["POSTGRES_PASSWORD"], host="db", port=5432,
                              database=os.environ["POSTGRES_DB"])
else:
    DATABASE_URL = os.environ["DATABASE_URL"]
JWT_SECRET = os.environ["JWT_SECRET"]
SITE_ORIGIN = os.environ.get("SITE_ORIGIN", "http://localhost:8080").rstrip("/")
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"
DATA_DIR = Path(os.environ.get("VIDEO_DIR", "/data/videos"))
MAX_UPLOAD = 100 * 1024 * 1024
COOKIE_NAME = "videohub_session"
PASSWORD = PasswordHash.recommended()
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="viewer")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Video(Base):
    __tablename__ = "videos"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(100), unique=True)
    mime: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="ready")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(20))
    detail: Mapped[str] = mapped_column(String(255))
    video_id: Mapped[str | None] = mapped_column(ForeignKey("videos.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())




# Order tables are additive; create_all preserves the existing users/videos/tasks data.
class BusinessOrder(Base):
    __tablename__ = "business_orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_no: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    client_name: Mapped[str] = mapped_column(String(120), index=True)
    merchant_id: Mapped[int | None] = mapped_column(ForeignKey("merchants.id", ondelete="SET NULL"), nullable=True, index=True)
    contact: Mapped[str] = mapped_column(String(120), default="")
    title: Mapped[str] = mapped_column(String(200))
    service_type: Mapped[str] = mapped_column(String(80), default="视频剪辑")
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    amount_cents: Mapped[int] = mapped_column(Integer)
    cost_cents: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="confirmed", index=True)
    order_date: Mapped[date] = mapped_column(Date, index=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str] = mapped_column(String(2000), default="")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class OrderPayment(Base):
    __tablename__ = "order_payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("business_orders.id", ondelete="RESTRICT"), index=True)
    amount_cents: Mapped[int] = mapped_column(Integer)
    received_on: Mapped[date] = mapped_column(Date, index=True)
    method: Mapped[str] = mapped_column(String(40), default="银行转账")
    remark: Mapped[str] = mapped_column(String(300), default="")
    is_void: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OrderEvent(Base):
    __tablename__ = "order_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("business_orders.id", ondelete="RESTRICT"), index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(40))
    detail: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

# Merchant categories and applications. Merchant accounts are scoped to ONE merchant.
class MerchantCategory(Base):
    __tablename__ = "merchant_categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("merchant_categories.id"), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Merchant(Base):
    __tablename__ = "merchants"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("merchant_categories.id"), nullable=True)
    contact_name: Mapped[str] = mapped_column(String(80), default="")
    phone: Mapped[str] = mapped_column(String(60), default="")
    address: Mapped[str] = mapped_column(String(250), default="")
    platform_url: Mapped[str] = mapped_column(String(400), default="")
    introduction: Mapped[str] = mapped_column(String(1500), default="")
    status: Mapped[str] = mapped_column(String(32), default="approved", index=True)
    review_reason: Mapped[str] = mapped_column(String(500), default="")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class MerchantAccount(Base):
    __tablename__ = "merchant_accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)


class MerchantReviewEvent(Base):
    __tablename__ = "merchant_review_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    old_status: Mapped[str] = mapped_column(String(32))
    new_status: Mapped[str] = mapped_column(String(32))
    note: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def iso(value):
    return value.isoformat() if value else None


def video_out(v: Video):
    return {"id": v.id, "filename": v.filename, "mime": v.mime, "size_bytes": v.size_bytes,
            "status": v.status, "created_by": v.created_by, "created_at": iso(v.created_at),
            "stream_url": f"/api/videos/{v.id}/stream"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # MVP only: for long-term production use Alembic versioned migrations.
    Base.metadata.create_all(engine)
    # Existing business_orders tables need an additive, repeatable migration.
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE business_orders ADD COLUMN IF NOT EXISTS merchant_id INTEGER REFERENCES merchants(id) ON DELETE SET NULL"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_business_orders_merchant_id ON business_orders (merchant_id)"))
    email = os.environ["ADMIN_EMAIL"].lower().strip()
    pwd = os.environ["ADMIN_PASSWORD"]
    if len(pwd) < 12 or len(JWT_SECRET) < 32:
        raise RuntimeError("ADMIN_PASSWORD must have >=12 characters and JWT_SECRET >=32 characters")
    with SessionLocal() as db:
        for category_name in CATEGORY_DEFAULTS:
            if not db.scalar(select(MerchantCategory).where(MerchantCategory.name == category_name)):
                db.add(MerchantCategory(name=category_name))
        db.commit()
        exists = db.scalar(select(User).where(User.email == email))
        if not exists:
            db.add(User(email=email, name="系统管理员", role="admin", password_hash=PASSWORD.hash(pwd)))
            db.commit()
    yield


app = FastAPI(title="VideoHub API", version="1.0", lifespan=lifespan, docs_url=None, redoc_url=None)


@app.middleware("http")
async def check_origin(request: Request, call_next):
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        fetch_site = request.headers.get("sec-fetch-site")
        if (origin and origin.rstrip("/") != SITE_ORIGIN) or (not origin and fetch_site == "cross-site"):
            return Response("Forbidden origin", status_code=403)
    return await call_next(request)


def db_session():
    with SessionLocal() as db:
        yield db


def current_user(request: Request, db: Session = Depends(db_session)) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(401, "请先登录")
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=["HS256"], options={"require": ["exp", "sub"]})
        user_id = int(data["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(401, "登录已过期")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(401, "用户不存在")
    return user


def require_staff(user: User = Depends(current_user)) -> User:
    if user.role not in ("admin", "viewer"):
        raise HTTPException(403, "商家账号不能访问内部工作台")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, "需要管理员权限")
    return user


class LoginIn(BaseModel):
    email: str
    password: str


class UserIn(BaseModel):
    email: str
    name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=12, max_length=128)
    role: str = "viewer"


def user_out(u: User):
    return {"id": u.id, "email": u.email, "name": u.name, "role": u.role, "created_at": iso(u.created_at)}


@app.get("/api/health")
def health(db: Session = Depends(db_session)):
    db.execute(text("SELECT 1"))
    return {"ok": True}


@app.post("/api/auth/login")
def login(payload: LoginIn, response: Response, db: Session = Depends(db_session)):
    u = db.scalar(select(User).where(User.email == payload.email.lower().strip()))
    if not u or not PASSWORD.verify(payload.password, u.password_hash):
        raise HTTPException(401, "账号或密码错误")
    token = jwt.encode({"sub": str(u.id), "exp": datetime.now(timezone.utc) + timedelta(hours=12)}, JWT_SECRET, algorithm="HS256")
    response.set_cookie(COOKIE_NAME, token, httponly=True, secure=COOKIE_SECURE,
                        samesite="strict", max_age=43200, path="/")
    return user_out(u)


@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@app.get("/api/auth/me")
def me(user: User = Depends(current_user)):
    return user_out(user)


@app.get("/api/dashboard")
def dashboard(user: User = Depends(require_staff), db: Session = Depends(db_session)):
    total = db.scalar(select(func.count(Video.id))) or 0
    size = db.scalar(select(func.coalesce(func.sum(Video.size_bytes), 0))) or 0
    today_start = datetime.combine(datetime.now(timezone.utc).date(), datetime.min.time(), tzinfo=timezone.utc)
    today = db.scalar(select(func.count(Video.id)).where(Video.created_at >= today_start)) or 0
    seven_start = today_start - timedelta(days=6)
    rows = db.execute(select(func.date(Video.created_at), func.count(Video.id))
        .where(Video.created_at >= seven_start).group_by(func.date(Video.created_at))).all()
    values = {str(d): c for d, c in rows}
    history = [{"date": str((datetime.now(timezone.utc).date() - timedelta(days=6-i))),
                "count": values.get(str(datetime.now(timezone.utc).date() - timedelta(days=6-i)), 0)} for i in range(7)]
    return {"total_videos": total, "total_bytes": int(size), "today_uploads": today, "history": history}


@app.get("/api/videos")
def list_videos(q: str = "", page: int = 1, limit: int = 20,
                user: User = Depends(require_staff), db: Session = Depends(db_session)):
    page = max(1, page)
    limit = min(50, max(1, limit))
    stmt = select(Video)
    if q.strip():
        stmt = stmt.where(Video.filename.ilike(f"%{q.strip()}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(stmt.order_by(Video.created_at.desc()).offset((page-1)*limit).limit(limit)).all()
    return {"items": [video_out(v) for v in items], "total": total, "page": page, "limit": limit}


@app.post("/api/videos", status_code=201)
async def upload_video(file: Annotated[UploadFile, File()],
                       user: User = Depends(require_staff), db: Session = Depends(db_session)):
    allowed = {".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm"}
    filename = Path(file.filename or "video.mp4").name[:255]
    ext = Path(filename).suffix.lower()
    if ext not in allowed:
        raise HTTPException(400, "仅支持 MP4/MOV/WebM")
    vid = str(uuid.uuid4())
    storage_key = vid + ext
    target = DATA_DIR / storage_key
    size = 0
    try:
        first = True
        with open(target, "wb") as output:
            while chunk := await file.read(1024 * 1024):
                if first:
                    valid = (ext in (".mp4", ".mov") and len(chunk) >= 12 and chunk[4:8] == b"ftyp") or (
                        ext == ".webm" and chunk[:4] == b"\x1a\x45\xdf\xa3")
                    if not valid:
                        raise HTTPException(400, "文件格式与扩展名不一致")
                    first = False
                size += len(chunk)
                if size > MAX_UPLOAD:
                    raise HTTPException(413, "单文件最大 100 MB")
                output.write(chunk)
        if size == 0:
            raise HTTPException(400, "文件为空")
        video = Video(id=vid, filename=filename, storage_key=storage_key, mime=allowed[ext],
                      size_bytes=size, status="ready", created_by=user.id)
        db.add(video)
        db.flush()
        db.add(Task(type="upload", status="completed", detail=f"上传完成：{filename}", video_id=vid))
        db.commit()
        db.refresh(video)
        return video_out(video)
    except Exception:
        db.rollback()
        target.unlink(missing_ok=True)
        raise
    finally:
        await file.close()


@app.get("/api/videos/{video_id}/stream")
def stream_video(video_id: str, user: User = Depends(require_staff), db: Session = Depends(db_session)):
    v = db.get(Video, video_id)
    if not v:
        raise HTTPException(404, "视频不存在")
    target = DATA_DIR / v.storage_key
    if not target.is_file():
        raise HTTPException(404, "原始文件不存在")
    return FileResponse(target, media_type=v.mime, content_disposition_type="inline")


@app.delete("/api/videos/{video_id}")
def delete_video(video_id: str, user: User = Depends(require_staff), db: Session = Depends(db_session)):
    v = db.get(Video, video_id)
    if not v:
        raise HTTPException(404, "视频不存在")
    if user.role != "admin" and v.created_by != user.id:
        raise HTTPException(403, "没有权限删除此视频")
    from .publish_tasks_v14 import PublishVideo
    if db.scalar(select(PublishVideo.id).where(PublishVideo.video_id == v.id)):
        raise HTTPException(409, "视频已绑定发布任务，需保留审核历史，不能删除")
    key = v.storage_key
    db.delete(v)
    db.flush()
    # Existing task history remains after deletion.
    db.commit()
    (DATA_DIR / key).unlink(missing_ok=True)
    return {"ok": True}


@app.get("/api/tasks")
def list_tasks(user: User = Depends(require_staff), db: Session = Depends(db_session)):
    tasks = db.scalars(select(Task).order_by(Task.created_at.desc()).limit(100)).all()
    return [{"id": t.id, "type": t.type, "status": t.status, "detail": t.detail,
             "created_at": iso(t.created_at)} for t in tasks]


@app.get("/api/users")
def list_users(admin: User = Depends(require_admin), db: Session = Depends(db_session)):
    return [user_out(u) for u in db.scalars(select(User).order_by(User.id)).all()]


@app.post("/api/users", status_code=201)
def create_user(payload: UserIn, admin: User = Depends(require_admin), db: Session = Depends(db_session)):
    email = payload.email.lower().strip()
    if "@" not in email or payload.role not in ("admin", "viewer"):
        raise HTTPException(400, "邮箱或角色不合法")
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "邮箱已存在")
    u = User(email=email, name=payload.name.strip(), role=payload.role,
             password_hash=PASSWORD.hash(payload.password))
    db.add(u)
    db.commit()
    db.refresh(u)
    return user_out(u)


# ===== Order management V1.1: order ledger, payments, aggregate stats and CSV =====
ORDER_STATUSES = {"confirmed", "in_progress", "delivered", "closed", "cancelled"}


def yuan_to_cents(value: Decimal) -> int:
    cents = (value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    if cents < 0 or cents > 2_000_000_000:
        raise HTTPException(400, "金额须在 0 到 2000 万元之间")
    return int(cents)


class OrderIn(BaseModel):
    merchant_id: int | None = None
    client_name: str = Field(min_length=1, max_length=120)
    contact: str = Field(default="", max_length=120)
    title: str = Field(min_length=1, max_length=200)
    service_type: str = Field(default="视频剪辑", min_length=1, max_length=80)
    owner_id: int | None = None
    amount: Decimal = Field(ge=0, le=20000000, decimal_places=2)
    cost: Decimal = Field(default=Decimal("0"), ge=0, le=20000000, decimal_places=2)
    status: str = "confirmed"
    order_date: date = Field(default_factory=date.today)
    due_date: date | None = None
    notes: str = Field(default="", max_length=2000)


class OrderPatch(BaseModel):
    merchant_id: int | None = None
    client_name: str | None = Field(default=None, min_length=1, max_length=120)
    contact: str | None = Field(default=None, max_length=120)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    service_type: str | None = Field(default=None, min_length=1, max_length=80)
    owner_id: int | None = None
    amount: Decimal | None = Field(default=None, ge=0, le=20000000, decimal_places=2)
    cost: Decimal | None = Field(default=None, ge=0, le=20000000, decimal_places=2)
    status: str | None = None
    order_date: date | None = None
    due_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)


class PaymentIn(BaseModel):
    amount: Decimal = Field(gt=0, le=20000000, decimal_places=2)
    received_on: date = Field(default_factory=date.today)
    method: str = Field(default="银行转账", min_length=1, max_length=40)
    remark: str = Field(default="", max_length=300)


def require_valid_owner(db: Session, owner_id: int | None):
    if owner_id is not None and not db.get(User, owner_id):
        raise HTTPException(400, "负责人账号不存在")


def require_valid_merchant(db: Session, merchant_id: int | None):
    if merchant_id is not None:
        m = db.get(Merchant, merchant_id)
        if not m or m.status == "suspended":
            raise HTTPException(400, "商家不存在或合作已暂停")


def payment_total(db: Session, order_id: int) -> int:
    return int(db.scalar(select(func.coalesce(func.sum(OrderPayment.amount_cents), 0))
               .where(OrderPayment.order_id == order_id, OrderPayment.is_void.is_(False))) or 0)


def payment_totals(db: Session, order_ids: list[int]) -> dict[int, int]:
    if not order_ids:
        return {}
    rows = db.execute(select(OrderPayment.order_id, func.sum(OrderPayment.amount_cents))
        .where(OrderPayment.order_id.in_(order_ids), OrderPayment.is_void.is_(False))
        .group_by(OrderPayment.order_id)).all()
    return {int(k): int(v) for k, v in rows}


def order_out(o: BusinessOrder, paid: int, owner_name: str = ""):
    return {"id": o.id, "order_no": o.order_no, "merchant_id": o.merchant_id, "client_name": o.client_name,
            "contact": o.contact, "title": o.title, "service_type": o.service_type,
            "owner_id": o.owner_id, "owner_name": owner_name,
            "amount_cents": o.amount_cents, "cost_cents": o.cost_cents,
            "paid_cents": paid, "outstanding_cents": max(0, o.amount_cents - paid),
            "estimated_profit_cents": o.amount_cents - o.cost_cents,
            "status": o.status, "order_date": iso(o.order_date), "due_date": iso(o.due_date),
            "notes": o.notes, "created_at": iso(o.created_at), "updated_at": iso(o.updated_at)}


def order_stmt(q: str = "", status: str = "", from_date: date | None = None,
               to_date: date | None = None):
    stmt = select(BusinessOrder)
    if q.strip():
        v = f"%{q.strip()[:100]}%"
        stmt = stmt.where(or_(BusinessOrder.order_no.ilike(v), BusinessOrder.client_name.ilike(v),
                              BusinessOrder.title.ilike(v), BusinessOrder.service_type.ilike(v)))
    if status:
        if status not in ORDER_STATUSES:
            raise HTTPException(400, "订单状态不合法")
        stmt = stmt.where(BusinessOrder.status == status)
    if from_date:
        stmt = stmt.where(BusinessOrder.order_date >= from_date)
    if to_date:
        stmt = stmt.where(BusinessOrder.order_date <= to_date)
    return stmt


def order_event(db: Session, o: BusinessOrder, user: User, action: str, detail: str):
    db.add(OrderEvent(order_id=o.id, actor_id=user.id, action=action, detail=detail[:500]))


@app.get("/api/orders/stats")
def orders_stats(from_date: date | None = None, to_date: date | None = None,
                 user: User = Depends(require_staff), db: Session = Depends(db_session)):
    if from_date and to_date and from_date > to_date:
        raise HTTPException(400, "起始日期不能晚于结束日期")
    stmt = order_stmt(from_date=from_date, to_date=to_date)
    orders = list(db.scalars(stmt).all())
    active = [o for o in orders if o.status != "cancelled"]
    paid = payment_totals(db, [o.id for o in active])
    total = sum(o.amount_cents for o in active)
    cost = sum(o.cost_cents for o in active)
    cash = sum(paid.values())
    by_status = {s: sum(1 for o in orders if o.status == s) for s in sorted(ORDER_STATUSES)}
    overdue = sum(1 for o in active if o.due_date and o.due_date < date.today() and o.status not in ("delivered", "closed"))
    # Cashflow chart: receipt month, across all orders, independent of the order-date filter.
    today = date.today()
    months = []
    for shift in range(5, -1, -1):
        index = (today.year * 12 + today.month - 1) - shift
        months.append(f"{index // 12:04d}-{index % 12 + 1:02d}")
    receipts = db.execute(select(OrderPayment.received_on, OrderPayment.amount_cents)
        .where(OrderPayment.is_void.is_(False), OrderPayment.received_on >= date.fromisoformat(months[0] + "-01"))).all()
    monthly_cash = {m: 0 for m in months}
    for received_on, amount in receipts:
        key = received_on.strftime("%Y-%m")
        if key in monthly_cash:
            monthly_cash[key] += amount
    return {"order_count": len(active), "cancelled_count": by_status["cancelled"],
            "contract_cents": total, "cost_cents": cost, "estimated_profit_cents": total-cost,
            "received_cents": cash, "outstanding_cents": max(0, total-cash),
            "overdue_count": overdue, "status_counts": by_status,
            "monthly_receipts": [{"month": m, "received_cents": monthly_cash[m]} for m in months]}


@app.get("/api/orders")
def list_orders(q: str = "", status: str = "", from_date: date | None = None,
                to_date: date | None = None, page: int = 1, limit: int = 20,
                user: User = Depends(require_staff), db: Session = Depends(db_session)):
    page = max(1, page)
    limit = max(1, min(100, limit))
    if from_date and to_date and from_date > to_date:
        raise HTTPException(400, "起始日期不能晚于结束日期")
    stmt = order_stmt(q, status, from_date, to_date)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    orders = list(db.scalars(stmt.order_by(BusinessOrder.order_date.desc(), BusinessOrder.id.desc())
                             .offset((page-1)*limit).limit(limit)).all())
    paid = payment_totals(db, [o.id for o in orders])
    owners = {u.id: u.name for u in db.scalars(select(User)).all()}
    return {"items": [order_out(o, paid.get(o.id, 0), owners.get(o.owner_id, "")) for o in orders],
            "total": total, "page": page, "limit": limit}


@app.post("/api/orders", status_code=201)
def create_order(payload: OrderIn, admin: User = Depends(require_admin), db: Session = Depends(db_session)):
    # V1.5: only merchants initiate new orders, via /api/portal/project-requests.
    # Staff accept/quote requests using /api/staff/project-requests/{id}/convert.
    raise HTTPException(403, "订单须由商家工作台发布；内部只负责报价、处理和收款")


@app.get("/api/orders/export")
def export_orders(q: str = "", status: str = "", from_date: date | None = None,
                  to_date: date | None = None,
                  user: User = Depends(require_admin), db: Session = Depends(db_session)):
    if from_date and to_date and from_date > to_date:
        raise HTTPException(400, "起始日期不能晚于结束日期")
    orders = list(db.scalars(order_stmt(q, status, from_date, to_date)
                             .order_by(BusinessOrder.order_date.desc(), BusinessOrder.id.desc())).all())
    paid = payment_totals(db, [o.id for o in orders])
    owners = {u.id: u.name for u in db.scalars(select(User)).all()}
    file = io.StringIO()
    writer = csv.writer(file)
    writer.writerow(["订单编号", "接单日期", "客户", "联系方式", "项目", "业务类型", "负责人", "状态", "订单金额(元)",
                     "成本(元)", "预估毛利(元)", "已收款(元)", "待收款(元)", "交付日期", "备注"])
    def safe(value):
        s = str(value or "")
        return "'" + s if s.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else s
    for o in orders:
        p = paid.get(o.id, 0)
        writer.writerow([safe(o.order_no), iso(o.order_date), safe(o.client_name), safe(o.contact),
                         safe(o.title), safe(o.service_type), safe(owners.get(o.owner_id, "")), o.status,
                         f"{o.amount_cents/100:.2f}", f"{o.cost_cents/100:.2f}",
                         f"{(o.amount_cents-o.cost_cents)/100:.2f}", f"{p/100:.2f}",
                         f"{(o.amount_cents-p)/100:.2f}", iso(o.due_date), safe(o.notes)])
    content = ("\ufeff" + file.getvalue()).encode("utf-8")
    return Response(content, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=videohub-orders.csv", "Cache-Control": "no-store"})


@app.get("/api/orders/{order_id}")
def order_detail(order_id: int, user: User = Depends(require_staff), db: Session = Depends(db_session)):
    o = db.get(BusinessOrder, order_id)
    if not o:
        raise HTTPException(404, "订单不存在")
    payments = list(db.scalars(select(OrderPayment).where(OrderPayment.order_id == order_id)
                               .order_by(OrderPayment.received_on.desc(), OrderPayment.id.desc())).all())
    history = list(db.scalars(select(OrderEvent).where(OrderEvent.order_id == order_id)
                              .order_by(OrderEvent.created_at.desc()).limit(50)).all())
    result = order_out(o, sum(p.amount_cents for p in payments if not p.is_void),
                       db.get(User, o.owner_id).name if o.owner_id and db.get(User, o.owner_id) else "")
    result["payments"] = [{"id": p.id, "amount_cents": p.amount_cents, "received_on": iso(p.received_on),
                           "method": p.method, "remark": p.remark, "is_void": p.is_void} for p in payments]
    result["history"] = [{"id": e.id, "action": e.action, "detail": e.detail,
                          "created_at": iso(e.created_at)} for e in history]
    return result


@app.patch("/api/orders/{order_id}")
def update_order(order_id: int, payload: OrderPatch, admin: User = Depends(require_admin), db: Session = Depends(db_session)):
    o = db.get(BusinessOrder, order_id)
    if not o:
        raise HTTPException(404, "订单不存在")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return order_out(o, payment_total(db, o.id))
    forbidden_null = {"client_name", "title", "service_type", "amount", "cost", "status", "order_date", "contact", "notes"}
    if any(k in changes and changes[k] is None for k in forbidden_null):
        raise HTTPException(400, "必填字段不能为空")
    if "status" in changes and changes["status"] not in ORDER_STATUSES:
        raise HTTPException(400, "订单状态不合法")
    if "owner_id" in changes:
        require_valid_owner(db, changes["owner_id"])
    if "merchant_id" in changes:
        require_valid_merchant(db, changes["merchant_id"])
        if changes["merchant_id"] != o.merchant_id:
            from .publish_tasks_v14 import PublishTask
            if db.scalar(select(PublishTask.id).where(PublishTask.order_id == o.id)):
                raise HTTPException(409, "此订单已分配发布任务，不能更换商家")
    if changes.get("status") == "cancelled" and payment_total(db, o.id) > 0:
        raise HTTPException(400, "此订单已有收款，请先核对并作废收款记录后再取消")
    if "amount" in changes:
        amount = yuan_to_cents(changes.pop("amount"))
        if amount < payment_total(db, o.id):
            raise HTTPException(400, "订单金额不能低于已收款金额")
        changes["amount_cents"] = amount
    if "cost" in changes:
        changes["cost_cents"] = yuan_to_cents(changes.pop("cost"))
    for key, value in changes.items():
        if isinstance(value, str):
            value = value.strip()
        setattr(o, key, value)
    order_event(db, o, admin, "update", "修改订单：" + ", ".join(changes.keys()))
    db.commit()
    db.refresh(o)
    return order_out(o, payment_total(db, o.id))


@app.post("/api/orders/{order_id}/payments", status_code=201)
def add_payment(order_id: int, payload: PaymentIn, admin: User = Depends(require_admin), db: Session = Depends(db_session)):
    # Lock the order row to serialize concurrent payment additions.
    o = db.scalar(select(BusinessOrder).where(BusinessOrder.id == order_id).with_for_update())
    if not o:
        raise HTTPException(404, "订单不存在")
    if o.status == "cancelled":
        raise HTTPException(400, "已取消订单不能新增收款")
    cents = yuan_to_cents(payload.amount)
    if cents + payment_total(db, order_id) > o.amount_cents:
        raise HTTPException(400, "收款金额不能超过剩余应收款")
    p = OrderPayment(order_id=o.id, amount_cents=cents, received_on=payload.received_on,
                     method=payload.method.strip(), remark=payload.remark.strip(), created_by=admin.id)
    db.add(p)
    db.flush()
    order_event(db, o, admin, "payment", f"登记收款 {cents/100:.2f} 元")
    db.commit()
    return {"id": p.id, "ok": True}


@app.post("/api/orders/{order_id}/payments/{payment_id}/void")
def void_payment(order_id: int, payment_id: int, admin: User = Depends(require_admin),
                 db: Session = Depends(db_session)):
    o = db.get(BusinessOrder, order_id)
    p = db.scalar(select(OrderPayment).where(OrderPayment.order_id == order_id,
                                           OrderPayment.id == payment_id).with_for_update())
    if not o or not p:
        raise HTTPException(404, "收款记录不存在")
    if p.is_void:
        raise HTTPException(409, "收款记录已作废")
    p.is_void = True
    order_event(db, o, admin, "void_payment", f"作废收款记录 #{payment_id}，金额 {p.amount_cents/100:.2f} 元")
    db.commit()
    return {"ok": True}


# ===== V1.2 Merchant management: separate staff and merchant workspaces =====
MERCHANT_STATUSES = {"draft", "pending", "changes_requested", "approved", "rejected", "suspended"}
CATEGORY_DEFAULTS = ["餐饮美食", "服饰鞋包", "美妆个护", "家居家装", "数码家电", "汽车服务", "旅游文娱", "本地生活", "教育培训", "其他"]


class MerchantIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    category_id: int | None = None
    contact_name: str = Field(default="", max_length=80)
    phone: str = Field(default="", max_length=60)
    address: str = Field(default="", max_length=250)
    platform_url: str = Field(default="", max_length=400)
    introduction: str = Field(default="", max_length=1500)


class MerchantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    category_id: int | None = None
    contact_name: str | None = Field(default=None, max_length=80)
    phone: str | None = Field(default=None, max_length=60)
    address: str | None = Field(default=None, max_length=250)
    platform_url: str | None = Field(default=None, max_length=400)
    introduction: str | None = Field(default=None, max_length=1500)


class MerchantReviewIn(BaseModel):
    decision: str  # approved / changes_requested / rejected / suspended
    reason: str = Field(default="", max_length=500)


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    parent_id: int | None = None


class MerchantAccountIn(BaseModel):
    email: str
    name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=12, max_length=128)


def validate_category(db: Session, category_id: int | None):
    if category_id is not None:
        c = db.get(MerchantCategory, category_id)
        if not c or not c.active:
            raise HTTPException(400, "商家分类不存在或已停用")


def merchant_to_dict(m: Merchant, db: Session, *, staff: bool = False):
    c = db.get(MerchantCategory, m.category_id) if m.category_id else None
    v = {"id": m.id, "name": m.name, "category_id": m.category_id,
         "category_name": c.name if c else "未分类", "contact_name": m.contact_name,
         "phone": m.phone, "address": m.address, "platform_url": m.platform_url,
         "introduction": m.introduction, "status": m.status, "review_reason": m.review_reason,
         "submitted_at": iso(m.submitted_at), "reviewed_at": iso(m.reviewed_at),
         "created_at": iso(m.created_at), "updated_at": iso(m.updated_at)}
    if staff:
        v["reviewed_by"] = m.reviewed_by
    return v


def get_merchant_of_user(db: Session, user: User) -> Merchant:
    if user.role != "merchant":
        raise HTTPException(403, "仅商家账号可以访问")
    membership = db.scalar(select(MerchantAccount).where(MerchantAccount.user_id == user.id))
    if not membership:
        raise HTTPException(403, "尚未关联商家，请联系管理员")
    m = db.get(Merchant, membership.merchant_id)
    if not m:
        raise HTTPException(404, "商家档案不存在")
    return m


def review_event(db: Session, m: Merchant, actor: User, new_status: str, note: str = ""):
    db.add(MerchantReviewEvent(merchant_id=m.id, actor_id=actor.id,
                               old_status=m.status, new_status=new_status, note=note[:500]))
    m.status = new_status
    if new_status == "pending":
        m.submitted_at = datetime.now(timezone.utc)
        m.review_reason = ""
    else:
        m.reviewed_at = datetime.now(timezone.utc)
        m.reviewed_by = actor.id
        m.review_reason = note.strip()


@app.get("/api/merchant-categories")
def merchant_categories(user: User = Depends(current_user), db: Session = Depends(db_session)):
    if user.role not in ("admin", "viewer", "merchant"):
        raise HTTPException(403, "无权限")
    cats = list(db.scalars(select(MerchantCategory).where(MerchantCategory.active.is_(True))
                           .order_by(MerchantCategory.id)).all())
    return [{"id": c.id, "name": c.name, "parent_id": c.parent_id} for c in cats]


@app.post("/api/merchant-categories", status_code=201)
def add_category(payload: CategoryIn, user: User = Depends(require_admin), db: Session = Depends(db_session)):
    name = payload.name.strip()
    if not name:
        raise HTTPException(400, "分类名称不能为空")
    if db.scalar(select(MerchantCategory).where(MerchantCategory.name == name)):
        raise HTTPException(409, "分类名称已存在")
    validate_category(db, payload.parent_id)
    c = MerchantCategory(name=name, parent_id=payload.parent_id)
    db.add(c); db.commit(); db.refresh(c)
    return {"id": c.id, "name": c.name, "parent_id": c.parent_id}


@app.get("/api/merchants/stats")
def merchant_stats(user: User = Depends(require_staff), db: Session = Depends(db_session)):
    merchants = list(db.scalars(select(Merchant)).all())
    categories = {c.id: c.name for c in db.scalars(select(MerchantCategory)).all()}
    status_counts = {s: sum(1 for m in merchants if m.status == s) for s in MERCHANT_STATUSES}
    category_counts = []
    for category_id, name in categories.items():
        count = sum(1 for m in merchants if m.category_id == category_id)
        if count:
            category_counts.append({"category": name, "count": count})
    category_counts.sort(key=lambda x: x["count"], reverse=True)
    return {"total": len(merchants), "status_counts": status_counts, "categories": category_counts}


@app.get("/api/merchants")
def list_merchants(q: str = "", status: str = "", category_id: int | None = None,
                   page: int = 1, limit: int = 30, user: User = Depends(require_staff),
                   db: Session = Depends(db_session)):
    if status and status not in MERCHANT_STATUSES:
        raise HTTPException(400, "审核状态不合法")
    stmt = select(Merchant)
    if q.strip():
        key = f"%{q.strip()[:100]}%"
        stmt = stmt.where(or_(Merchant.name.ilike(key), Merchant.contact_name.ilike(key)))
    if status:
        stmt = stmt.where(Merchant.status == status)
    if category_id is not None:
        stmt = stmt.where(Merchant.category_id == category_id)
    page, limit = max(1, page), min(100, max(1, limit))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = list(db.scalars(stmt.order_by(Merchant.created_at.desc(), Merchant.id.desc())
                            .offset((page-1)*limit).limit(limit)).all())
    return {"items": [merchant_to_dict(m, db, staff=True) for m in items],
            "total": total, "page": page, "limit": limit}


@app.post("/api/merchants", status_code=201)
def create_merchant(payload: MerchantIn, user: User = Depends(require_admin), db: Session = Depends(db_session)):
    validate_category(db, payload.category_id)
    values = payload.model_dump()
    values["name"] = values["name"].strip()
    m = Merchant(**values, status="approved")
    db.add(m); db.commit(); db.refresh(m)
    return merchant_to_dict(m, db, staff=True)


@app.get("/api/merchants/{merchant_id}")
def merchant_detail(merchant_id: int, user: User = Depends(require_staff), db: Session = Depends(db_session)):
    m = db.get(Merchant, merchant_id)
    if not m:
        raise HTTPException(404, "商家不存在")
    out = merchant_to_dict(m, db, staff=True)
    out["reviews"] = [{"id": x.id, "old_status": x.old_status, "new_status": x.new_status,
                       "note": x.note, "created_at": iso(x.created_at)} for x in
                      db.scalars(select(MerchantReviewEvent).where(MerchantReviewEvent.merchant_id == m.id)
                                 .order_by(MerchantReviewEvent.id.desc()).limit(30)).all()]
    out["accounts"] = [{"id": a.user_id, "email": db.get(User, a.user_id).email}
                       for a in db.scalars(select(MerchantAccount).where(MerchantAccount.merchant_id == m.id)).all()
                       if db.get(User, a.user_id)]
    return out


@app.patch("/api/merchants/{merchant_id}")
def edit_merchant(merchant_id: int, payload: MerchantUpdate,
                  user: User = Depends(require_admin), db: Session = Depends(db_session)):
    m = db.get(Merchant, merchant_id)
    if not m:
        raise HTTPException(404, "商家不存在")
    changes = payload.model_dump(exclude_unset=True)
    if "category_id" in changes:
        validate_category(db, changes["category_id"])
    if "name" in changes and (not changes["name"] or not changes["name"].strip()):
        raise HTTPException(400, "商家名称不能为空")
    for k, v in changes.items():
        if v is None and k != "category_id":
            raise HTTPException(400, "资料不能为空")
        setattr(m, k, v.strip() if isinstance(v, str) else v)
    db.commit(); db.refresh(m)
    return merchant_to_dict(m, db, staff=True)


@app.post("/api/merchants/{merchant_id}/submit")
def legacy_submit_disabled(merchant_id: int, user: User = Depends(require_admin)):
    raise HTTPException(410, "V1.4 已取消商家资质审核，商家负责审核视频成品")


@app.post("/api/merchants/{merchant_id}/review")
def legacy_review_disabled(merchant_id: int, user: User = Depends(require_admin)):
    raise HTTPException(410, "V1.4 已取消商家资质审核，请使用合作账号管理")


class MerchantAccessIn(BaseModel):
    suspended: bool


@app.post("/api/merchants/{merchant_id}/access")
def set_merchant_access(merchant_id: int, payload: MerchantAccessIn,
                        user: User = Depends(require_admin), db: Session = Depends(db_session)):
    m = db.get(Merchant, merchant_id)
    if not m:
        raise HTTPException(404, "商家不存在")
    m.status = "suspended" if payload.suspended else "approved"
    db.commit()
    return merchant_to_dict(m, db, staff=True)


@app.post("/api/merchants/{merchant_id}/accounts", status_code=201)
def create_merchant_account(merchant_id: int, payload: MerchantAccountIn,
                            admin: User = Depends(require_admin), db: Session = Depends(db_session)):
    m = db.get(Merchant, merchant_id)
    if not m:
        raise HTTPException(404, "商家不存在")
    email = payload.email.lower().strip()
    if "@" not in email or db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "邮箱格式错误或已存在")
    account = User(email=email, name=payload.name.strip(), role="merchant",
                   password_hash=PASSWORD.hash(payload.password))
    db.add(account); db.flush()
    db.add(MerchantAccount(merchant_id=m.id, user_id=account.id))
    db.commit()
    return {"id": account.id, "email": account.email, "merchant_id": m.id}


@app.get("/api/portal/me")
def portal_me(user: User = Depends(current_user), db: Session = Depends(db_session)):
    return merchant_to_dict(get_merchant_of_user(db, user), db)


@app.patch("/api/portal/profile")
def portal_update(payload: MerchantUpdate, user: User = Depends(current_user),
                  db: Session = Depends(db_session)):
    m = get_merchant_of_user(db, user)
    if m.status == "suspended":
        raise HTTPException(403, "商家已暂停，不能修改资料")
    changes = payload.model_dump(exclude_unset=True)
    if "category_id" in changes:
        validate_category(db, changes["category_id"])
    if "name" in changes and (not changes["name"] or not changes["name"].strip()):
        raise HTTPException(400, "商家名称不能为空")
    for k, v in changes.items():
        if v is None and k != "category_id":
            raise HTTPException(400, "商家资料不能为空")
        setattr(m, k, v.strip() if isinstance(v, str) else v)
    db.commit(); db.refresh(m)
    return merchant_to_dict(m, db)


@app.post("/api/portal/submit")
def legacy_portal_submit_disabled(user: User = Depends(current_user)):
    raise HTTPException(410, "V1.4 不再需要商家资质审核；请直接查看待审核视频")


def portal_order_out(o: BusinessOrder, paid: int):
    # Never include internal costs, profit, owner, contact, notes or staff histories.
    return {"id": o.id, "order_no": o.order_no, "title": o.title, "service_type": o.service_type,
            "status": o.status, "order_date": iso(o.order_date), "due_date": iso(o.due_date),
            "amount_cents": o.amount_cents, "paid_cents": paid,
            "outstanding_cents": max(0, o.amount_cents-paid)}


@app.get("/api/portal/orders")
def portal_orders(user: User = Depends(current_user), db: Session = Depends(db_session)):
    m = get_merchant_of_user(db, user)
    orders = list(db.scalars(select(BusinessOrder).where(BusinessOrder.merchant_id == m.id)
                             .order_by(BusinessOrder.order_date.desc(), BusinessOrder.id.desc())
                             .limit(100)).all())
    paid = payment_totals(db, [o.id for o in orders])
    return [portal_order_out(o, paid.get(o.id, 0)) for o in orders]


@app.get("/api/portal/orders/{order_id}")
def portal_order_detail(order_id: int, user: User = Depends(current_user), db: Session = Depends(db_session)):
    m = get_merchant_of_user(db, user)
    o = db.scalar(select(BusinessOrder).where(BusinessOrder.id == order_id,
                                             BusinessOrder.merchant_id == m.id))
    if not o:
        raise HTTPException(404, "订单不存在")
    return portal_order_out(o, payment_total(db, o.id))


# BLACKMAMBO_V13_PROJECTS
from .merchant_portal_v13 import router as merchant_portal_v13_router
app.include_router(merchant_portal_v13_router)

# BLACKMAMBO_V14_PUBLISH_TASKS
from .publish_tasks_v14 import router as publish_tasks_v14_router
app.include_router(publish_tasks_v14_router)
