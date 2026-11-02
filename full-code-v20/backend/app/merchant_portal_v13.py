"""BlackMambo V1.3: merchant video-production intake, deliverables and acceptance.

Imported from app.main at module bottom so Base.metadata.create_all includes these tables.
All client-facing routes query by the authenticated merchant id; no staff financial data
is returned. All project files are private and served only after access checks.
"""
from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .main import (
    Base, BusinessOrder, Merchant, User, current_user, db_session, get_merchant_of_user,
    require_staff, require_admin, payment_total, portal_order_out, yuan_to_cents, iso, order_event,
)

router = APIRouter(prefix="/api")
ASSET_ROOT = Path(os.environ.get("VIDEO_DIR", "/data/videos")) / "merchant_assets"
MAX_ASSET = 100 * 1024 * 1024
STAGES = {"planning", "shooting", "producing", "editing", "client_review", "delivered"}
REQUEST_STATUSES = {"pending", "accepted", "rejected"}
ALLOWED = {
    ".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm",
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".pdf": "application/pdf",
}


class ProjectRequest(Base):
    __tablename__ = "merchant_project_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200))
    brief: Mapped[str] = mapped_column(Text)
    video_count: Mapped[int] = mapped_column(Integer)
    aspect_ratio: Mapped[str] = mapped_column(String(20), default="9:16")
    duration_seconds: Mapped[int] = mapped_column(Integer, default=30)
    desired_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reference_url: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    staff_note: Mapped[str] = mapped_column(Text, default="")
    linked_order_id: Mapped[int | None] = mapped_column(ForeignKey("business_orders.id"), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProjectWorkflow(Base):
    __tablename__ = "merchant_project_workflows"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("business_orders.id"), unique=True, index=True)
    stage: Mapped[str] = mapped_column(String(30), default="planning")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    client_note: Mapped[str] = mapped_column(Text, default="")
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ProjectAsset(Base):
    __tablename__ = "merchant_project_assets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    request_id: Mapped[int | None] = mapped_column(ForeignKey("merchant_project_requests.id"), nullable=True, index=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("business_orders.id"), nullable=True, index=True)
    storage_key: Mapped[str] = mapped_column(String(100), unique=True)
    filename: Mapped[str] = mapped_column(String(255))
    mime: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20))  # material / draft / final
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProjectRevision(Base):
    __tablename__ = "merchant_project_revisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("business_orders.id"), index=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open")
    staff_reply: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProjectAcceptance(Base):
    __tablename__ = "merchant_project_acceptances"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("business_orders.id"), unique=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"))
    accepted_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    final_file_id: Mapped[str] = mapped_column(ForeignKey("merchant_project_assets.id"))
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProjectActivity(Base):
    __tablename__ = "merchant_project_activity"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("business_orders.id"), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    event: Mapped[str] = mapped_column(String(40))
    detail: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RequestIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    brief: str = Field(min_length=5, max_length=3000)
    video_count: int = Field(ge=1, le=1000)
    aspect_ratio: str = Field(default="9:16")
    duration_seconds: int = Field(default=30, ge=5, le=3600)
    desired_date: date | None = None
    reference_url: str = Field(default="", max_length=500)


class ConvertIn(BaseModel):
    amount: Decimal = Field(ge=0, le=20000000, decimal_places=2)
    cost: Decimal = Field(default=Decimal("0"), ge=0, le=20000000, decimal_places=2)
    owner_id: int | None = None
    due_date: date | None = None
    staff_note: str = Field(default="", max_length=1000)


class RejectIn(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class ProgressIn(BaseModel):
    stage: str
    progress: int = Field(ge=0, le=100)
    client_note: str = Field(default="", max_length=2000)


class RevisionIn(BaseModel):
    content: str = Field(min_length=3, max_length=2000)


class ResolveIn(BaseModel):
    reply: str = Field(min_length=2, max_length=2000)


def require_approved(m: Merchant):
    # V1.4: merchants are collaborators, not applicants awaiting approval.
    if m.status == "suspended":
        raise HTTPException(403, "商家账号已暂停")


def req_out(r: ProjectRequest):
    return {"id": r.id, "merchant_id": r.merchant_id, "title": r.title, "brief": r.brief,
            "video_count": r.video_count, "aspect_ratio": r.aspect_ratio,
            "duration_seconds": r.duration_seconds, "desired_date": iso(r.desired_date),
            "reference_url": r.reference_url, "status": r.status, "staff_note": r.staff_note,
            "linked_order_id": r.linked_order_id, "created_at": iso(r.created_at)}


def file_out(f: ProjectAsset):
    return {"id": f.id, "filename": f.filename, "mime": f.mime,
            "kind": f.kind, "size_bytes": f.size_bytes, "created_at": iso(f.created_at),
            "file_url": f"/api/project-files/{f.id}"}


def revision_out(r: ProjectRevision):
    return {"id": r.id, "content": r.content, "status": r.status,
            "staff_reply": r.staff_reply, "created_at": iso(r.created_at), "resolved_at": iso(r.resolved_at)}


def accessible_order(db: Session, order_id: int, user: User, *, write: bool = False):
    order = db.get(BusinessOrder, order_id)
    if not order or not order.merchant_id:
        raise HTTPException(404, "项目不存在")
    if user.role == "merchant":
        m = get_merchant_of_user(db, user)
        if order.merchant_id != m.id:
            raise HTTPException(404, "项目不存在")
        if m.status == "suspended":
            raise HTTPException(403, "商家账号已暂停")
        if write:
            require_approved(m)
    elif user.role not in ("admin", "viewer"):
        raise HTTPException(403, "无权限")
    return order


def project_files(db: Session, order_id: int):
    request_id = db.scalar(select(ProjectRequest.id).where(ProjectRequest.linked_order_id == order_id))
    if request_id is None:
        query = select(ProjectAsset).where(ProjectAsset.order_id == order_id)
    else:
        query = select(ProjectAsset).where((ProjectAsset.order_id == order_id) | (ProjectAsset.request_id == request_id))
    return list(db.scalars(query.order_by(ProjectAsset.created_at.desc(), ProjectAsset.id.desc())).all())


def project_out(db: Session, o: BusinessOrder):
    result = portal_order_out(o, payment_total(db, o.id))
    workflow = db.scalar(select(ProjectWorkflow).where(ProjectWorkflow.order_id == o.id))
    result["stage"] = workflow.stage if workflow else "planning"
    result["progress"] = workflow.progress if workflow else 0
    result["client_note"] = workflow.client_note if workflow else ""
    acceptance = db.scalar(select(ProjectAcceptance).where(ProjectAcceptance.order_id == o.id))
    result["accepted_at"] = iso(acceptance.accepted_at) if acceptance else None
    return result


def project_detail(db: Session, o: BusinessOrder):
    result = project_out(db, o)
    result["files"] = [file_out(x) for x in project_files(db, o.id)]
    result["revisions"] = [revision_out(r) for r in db.scalars(select(ProjectRevision)
        .where(ProjectRevision.order_id == o.id).order_by(ProjectRevision.id.desc())).all()]
    result["activity"] = [{"event": e.event, "detail": e.detail, "created_at": iso(e.created_at)} for e in
        db.scalars(select(ProjectActivity).where(ProjectActivity.order_id == o.id)
                   .order_by(ProjectActivity.id.desc()).limit(50)).all()]
    return result


def log_activity(db: Session, order_id: int, actor_id: int, event: str, detail: str):
    db.add(ProjectActivity(order_id=order_id, actor_id=actor_id, event=event, detail=detail[:500]))


def ensure_url_safe(value: str) -> bool:
    # Reference URLs are informational strings only; never automatically fetched server-side.
    return not value or value.startswith(("https://", "http://"))


@router.post("/portal/project-requests", status_code=201)
def submit_request(payload: RequestIn, user: User = Depends(current_user), db: Session = Depends(db_session)):
    m = get_merchant_of_user(db, user)
    require_approved(m)
    if payload.aspect_ratio not in ("9:16", "16:9", "1:1", "4:5") or not ensure_url_safe(payload.reference_url):
        raise HTTPException(400, "视频比例或参考链接不合法")
    r = ProjectRequest(merchant_id=m.id, created_by=user.id, title=payload.title.strip(),
        brief=payload.brief.strip(), video_count=payload.video_count, aspect_ratio=payload.aspect_ratio,
        duration_seconds=payload.duration_seconds, desired_date=payload.desired_date,
        reference_url=payload.reference_url.strip())
    db.add(r); db.commit(); db.refresh(r)
    return req_out(r)


@router.get("/portal/project-requests")
def portal_requests(user: User = Depends(current_user), db: Session = Depends(db_session)):
    m = get_merchant_of_user(db, user)
    return [req_out(r) for r in db.scalars(select(ProjectRequest).where(ProjectRequest.merchant_id == m.id)
        .order_by(ProjectRequest.id.desc()).limit(100)).all()]


@router.get("/staff/project-requests")
def staff_requests(status: str = "", user: User = Depends(require_staff), db: Session = Depends(db_session)):
    if status and status not in REQUEST_STATUSES:
        raise HTTPException(400, "状态不合法")
    stmt = select(ProjectRequest)
    if status:
        stmt = stmt.where(ProjectRequest.status == status)
    return [req_out(r) for r in db.scalars(stmt.order_by(ProjectRequest.id.desc()).limit(200)).all()]


@router.post("/staff/project-requests/{request_id}/reject")
def reject_request(request_id: int, payload: RejectIn, user: User = Depends(require_admin), db: Session = Depends(db_session)):
    r = db.scalar(select(ProjectRequest).where(ProjectRequest.id == request_id).with_for_update())
    if not r:
        raise HTTPException(404, "需求不存在")
    if r.status != "pending":
        raise HTTPException(409, "需求已处理")
    r.status = "rejected"
    r.staff_note = payload.reason.strip()
    db.commit()
    return req_out(r)


@router.post("/staff/project-requests/{request_id}/convert", status_code=201)
def convert_request(request_id: int, payload: ConvertIn, user: User = Depends(require_admin), db: Session = Depends(db_session)):
    r = db.scalar(select(ProjectRequest).where(ProjectRequest.id == request_id).with_for_update())
    if not r:
        raise HTTPException(404, "需求不存在")
    if r.status != "pending":
        raise HTTPException(409, "需求已经处理，不可重复建立订单")
    m = db.get(Merchant, r.merchant_id)
    if not m or m.status == "suspended":
        raise HTTPException(403, "商家不存在或合作已暂停")
    if payload.owner_id is not None:
        owner = db.get(User, payload.owner_id)
        if not owner or owner.role not in ("admin", "viewer"):
            raise HTTPException(400, "订单负责人必须是内部员工")
    now = datetime.now(timezone.utc)
    order = BusinessOrder(
        order_no="BM-" + now.strftime("%Y%m%d") + "-" + uuid.uuid4().hex[:8].upper(),
        client_name=m.name, merchant_id=m.id, contact=m.phone, title=r.title,
        service_type="拍摄+制作+剪辑", owner_id=payload.owner_id,
        amount_cents=yuan_to_cents(payload.amount), cost_cents=yuan_to_cents(payload.cost),
        status="confirmed", order_date=now.date(), due_date=payload.due_date or r.desired_date,
        notes=f"商家需求 #{r.id} · {r.video_count}条 · {r.aspect_ratio} · {r.duration_seconds}秒/条\n{r.brief}"[:2000],
        created_by=user.id)
    db.add(order); db.flush()
    db.add(ProjectWorkflow(order_id=order.id, stage="planning", progress=0, updated_by=user.id))
    r.linked_order_id = order.id
    r.status = "accepted"
    r.staff_note = payload.staff_note.strip()
    order_event(db, order, user, "create", f"商家需求 #{r.id} 报价转单")
    log_activity(db, order.id, user.id, "converted", "商家需求已确认并建立正式订单")
    db.commit()
    return {"order_id": order.id, "order_no": order.order_no, "request": req_out(r)}


@router.get("/portal/projects")
def merchant_projects(user: User = Depends(current_user), db: Session = Depends(db_session)):
    m = get_merchant_of_user(db, user)
    orders = db.scalars(select(BusinessOrder).where(BusinessOrder.merchant_id == m.id)
        .order_by(BusinessOrder.id.desc()).limit(100)).all()
    return [project_out(db, o) for o in orders]


@router.get("/staff/projects")
def staff_projects(user: User = Depends(require_staff), db: Session = Depends(db_session)):
    orders = db.scalars(select(BusinessOrder).where(BusinessOrder.merchant_id.is_not(None))
        .order_by(BusinessOrder.id.desc()).limit(200)).all()
    return [project_out(db, o) for o in orders]


@router.get("/portal/projects/{order_id}")
def merchant_project_detail(order_id: int, user: User = Depends(current_user), db: Session = Depends(db_session)):
    return project_detail(db, accessible_order(db, order_id, user))


@router.get("/staff/projects/{order_id}")
def staff_project_detail(order_id: int, user: User = Depends(require_staff), db: Session = Depends(db_session)):
    return project_detail(db, accessible_order(db, order_id, user))


@router.post("/staff/projects/{order_id}/progress")
def set_project_stage(order_id: int, payload: ProgressIn, user: User = Depends(require_admin), db: Session = Depends(db_session)):
    order = accessible_order(db, order_id, user)
    if order.status == "cancelled":
        raise HTTPException(409, "已取消订单不能修改进度")
    if payload.stage not in STAGES or payload.stage == "delivered":
        raise HTTPException(400, "交付状态只能由商家确认验收后产生")
    current = db.scalar(select(ProjectWorkflow).where(ProjectWorkflow.order_id == order.id).with_for_update())
    if not current:
        current = ProjectWorkflow(order_id=order.id)
        db.add(current)
    acceptance = db.scalar(select(ProjectAcceptance).where(ProjectAcceptance.order_id == order.id))
    if acceptance:
        raise HTTPException(409, "项目已经验收，不可再修改制作阶段")
    if payload.stage == "client_review":
        latest_final = db.scalar(select(ProjectAsset).where(
            ProjectAsset.order_id == order_id, ProjectAsset.kind == "final")
            .order_by(ProjectAsset.created_at.desc(), ProjectAsset.id.desc()))
        if not latest_final:
            raise HTTPException(400, "至少上传一个成品文件才能提交客户验收")
        latest_revision = db.scalar(select(ProjectRevision).where(
            ProjectRevision.order_id == order_id).order_by(ProjectRevision.created_at.desc(), ProjectRevision.id.desc()))
        if latest_revision and latest_final.created_at <= latest_revision.created_at:
            raise HTTPException(409, "客户要求修改后，需重新上传新的成品文件才能再次提交验收")
    current.stage = payload.stage
    current.progress = payload.progress
    current.client_note = payload.client_note.strip()
    current.updated_by = user.id
    if payload.stage in ("shooting", "producing", "editing", "client_review"):
        order.status = "in_progress"
    log_activity(db, order_id, user.id, "progress", f"阶段更新：{payload.stage}（{payload.progress}%）")
    db.commit()
    return project_out(db, order)


@router.post("/portal/projects/{order_id}/revisions", status_code=201)
def request_revision(order_id: int, payload: RevisionIn, user: User = Depends(current_user), db: Session = Depends(db_session)):
    order = accessible_order(db, order_id, user, write=True)
    if order.status == "cancelled":
        raise HTTPException(409, "已取消订单无法修改")
    if db.scalar(select(ProjectAcceptance).where(ProjectAcceptance.order_id == order_id)):
        raise HTTPException(409, "已验收项目不能再次提交修改")
    workflow = db.scalar(select(ProjectWorkflow).where(ProjectWorkflow.order_id == order_id).with_for_update())
    if not workflow or workflow.stage != "client_review":
        raise HTTPException(409, "当前项目尚未进入客户验收阶段")
    r = ProjectRevision(order_id=order_id, merchant_id=order.merchant_id,
        created_by=user.id, content=payload.content.strip(), created_at=datetime.now(timezone.utc))
    db.add(r)
    workflow.stage = "editing"
    workflow.progress = min(workflow.progress, 95)
    log_activity(db, order_id, user.id, "revision", "商家提出修改意见")
    db.commit(); db.refresh(r)
    return revision_out(r)


@router.post("/staff/projects/{order_id}/revisions/{revision_id}/resolve")
def resolve_revision(order_id: int, revision_id: int, payload: ResolveIn,
                     user: User = Depends(require_admin), db: Session = Depends(db_session)):
    accessible_order(db, order_id, user)
    r = db.scalar(select(ProjectRevision).where(ProjectRevision.id == revision_id,
        ProjectRevision.order_id == order_id).with_for_update())
    if not r:
        raise HTTPException(404, "修改请求不存在")
    if r.status != "open":
        raise HTTPException(409, "此修改请求已处理")
    r.status = "resolved"
    r.staff_reply = payload.reply.strip()
    r.resolved_at = datetime.now(timezone.utc)
    log_activity(db, order_id, user.id, "revision_resolved", "工作人员已完成修改回复")
    db.commit()
    return revision_out(r)


@router.post("/portal/projects/{order_id}/accept")
def accept_project(order_id: int, user: User = Depends(current_user), db: Session = Depends(db_session)):
    order = accessible_order(db, order_id, user, write=True)
    order = db.scalar(select(BusinessOrder).where(BusinessOrder.id == order.id).with_for_update())
    if db.scalar(select(ProjectAcceptance).where(ProjectAcceptance.order_id == order_id)):
        raise HTTPException(409, "已经验收，请勿重复操作")
    if order.status == "cancelled":
        raise HTTPException(409, "已取消订单不能验收")
    workflow = db.scalar(select(ProjectWorkflow).where(ProjectWorkflow.order_id == order_id).with_for_update())
    if not workflow or workflow.stage != "client_review":
        raise HTTPException(409, "工作人员尚未提交成品验收")
    if db.scalar(select(ProjectRevision.id).where(ProjectRevision.order_id == order_id,
        ProjectRevision.status == "open")):
        raise HTTPException(409, "存在未处理的修改意见")
    last_final = db.scalar(select(ProjectAsset).where(ProjectAsset.order_id == order_id,
        ProjectAsset.kind == "final").order_by(ProjectAsset.created_at.desc(), ProjectAsset.id.desc()))
    if not last_final:
        raise HTTPException(409, "尚未上传成品文件")
    db.add(ProjectAcceptance(order_id=order_id, merchant_id=order.merchant_id,
        accepted_by=user.id, final_file_id=last_final.id))
    order.status = "delivered"
    workflow.stage = "delivered"
    workflow.progress = 100
    log_activity(db, order_id, user.id, "accepted", f"商家确认成品交付 {last_final.filename[:150]}")
    db.commit()
    return {"ok": True, "order_id": order_id}


def _check_magic(ext: str, sample: bytes):
    if ext in (".mp4", ".mov"):
        return len(sample) >= 12 and sample[4:8] == b"ftyp"
    if ext == ".webm":
        return sample.startswith(b"\x1a\x45\xdf\xa3")
    if ext == ".png":
        return sample.startswith(b"\x89PNG\r\n\x1a\n")
    if ext in (".jpg", ".jpeg"):
        return sample.startswith(b"\xff\xd8\xff")
    if ext == ".pdf":
        return sample.startswith(b"%PDF-")
    return False


async def save_asset(file: UploadFile, *, merchant_id: int, request_id: int | None,
                     order_id: int | None, kind: str, user: User, db: Session):
    name = Path(file.filename or "").name[:255]
    ext = Path(name).suffix.lower()
    if not name or ext not in ALLOWED:
        raise HTTPException(400, "只支持 MP4/MOV/WebM/JPG/PNG/PDF")
    ASSET_ROOT.mkdir(parents=True, exist_ok=True)
    item_id = str(uuid.uuid4())
    key = item_id + ext
    target = ASSET_ROOT / key
    size = 0
    try:
        with open(target, "xb") as writer:
            first = True
            while block := await file.read(1024 * 1024):
                if first:
                    first = False
                    if not _check_magic(ext, block):
                        raise HTTPException(400, "文件格式验证失败")
                size += len(block)
                if size > MAX_ASSET:
                    raise HTTPException(413, "单文件大小不得超过 100 MB")
                writer.write(block)
        if size == 0:
            raise HTTPException(400, "文件不能为空")
        asset = ProjectAsset(id=item_id, merchant_id=merchant_id, request_id=request_id,
            order_id=order_id, storage_key=key, filename=name, mime=ALLOWED[ext],
            size_bytes=size, kind=kind, uploaded_by=user.id, created_at=datetime.now(timezone.utc))
        db.add(asset)
        if order_id:
            log_activity(db, order_id, user.id, "upload", f"上传{kind}：{name[:140]}")
        db.commit()
        return file_out(asset)
    except Exception:
        db.rollback()
        target.unlink(missing_ok=True)
        raise
    finally:
        await file.close()


@router.post("/portal/project-requests/{request_id}/files", status_code=201)
async def upload_request_material(request_id: int, file: UploadFile = File(...),
                                  user: User = Depends(current_user), db: Session = Depends(db_session)):
    m = get_merchant_of_user(db, user)
    require_approved(m)
    r = db.scalar(select(ProjectRequest).where(ProjectRequest.id == request_id,
        ProjectRequest.merchant_id == m.id))
    if not r:
        raise HTTPException(404, "需求不存在")
    if r.status == "rejected":
        raise HTTPException(409, "已拒绝的需求不可继续上传")
    return await save_asset(file, merchant_id=m.id, request_id=r.id, order_id=None,
                            kind="material", user=user, db=db)


@router.get("/portal/project-requests/{request_id}/files")
def request_materials(request_id: int, user: User = Depends(current_user), db: Session = Depends(db_session)):
    m = get_merchant_of_user(db, user)
    if not db.scalar(select(ProjectRequest.id).where(ProjectRequest.id == request_id,
        ProjectRequest.merchant_id == m.id)):
        raise HTTPException(404, "需求不存在")
    assets = db.scalars(select(ProjectAsset).where(ProjectAsset.request_id == request_id)
        .order_by(ProjectAsset.id.desc())).all()
    return [file_out(x) for x in assets]


@router.get("/staff/project-requests/{request_id}/files")
def staff_request_materials(request_id: int, user: User = Depends(require_staff), db: Session = Depends(db_session)):
    if not db.get(ProjectRequest, request_id):
        raise HTTPException(404, "需求不存在")
    assets = db.scalars(select(ProjectAsset).where(ProjectAsset.request_id == request_id)
        .order_by(ProjectAsset.id.desc())).all()
    return [file_out(x) for x in assets]


@router.post("/projects/{order_id}/files", status_code=201)
async def upload_project_file(order_id: int, kind: str = Form(...), file: UploadFile = File(...),
                              user: User = Depends(current_user), db: Session = Depends(db_session)):
    order = accessible_order(db, order_id, user, write=True)
    if order.status in ("cancelled", "closed", "delivered"):
        raise HTTPException(409, "已关闭、取消或交付项目不能上传新文件")
    if kind not in ("material", "draft", "final"):
        raise HTTPException(400, "文件类型不合法")
    if user.role == "merchant" and kind != "material":
        raise HTTPException(403, "商家只允许上传需求素材")
    if user.role == "viewer":
        raise HTTPException(403, "仅管理员可上传制作文件")
    return await save_asset(file, merchant_id=order.merchant_id, request_id=None,
                            order_id=order_id, kind=kind, user=user, db=db)


@router.get("/project-files/{file_id}")
def download_project_file(file_id: str, user: User = Depends(current_user), db: Session = Depends(db_session)):
    asset = db.get(ProjectAsset, file_id)
    if not asset:
        raise HTTPException(404, "文件不存在")
    if user.role == "merchant":
        m = get_merchant_of_user(db, user)
        if m.id != asset.merchant_id or m.status == "suspended":
            raise HTTPException(404, "文件不存在")
        # Membership alone isn't sufficient: validate the linked request/order too.
        if asset.order_id:
            accessible_order(db, asset.order_id, user)
        elif asset.request_id:
            if not db.scalar(select(ProjectRequest.id).where(ProjectRequest.id == asset.request_id,
                ProjectRequest.merchant_id == m.id)):
                raise HTTPException(404, "文件不存在")
        else:
            raise HTTPException(404, "文件不存在")
    elif user.role not in ("admin", "viewer"):
        raise HTTPException(403, "无权限")
    target = ASSET_ROOT / asset.storage_key
    if not target.is_file():
        raise HTTPException(404, "文件在存储中不存在")
    # Render videos/images inline for previews; PDF and other documents download.
    inline = asset.mime.startswith(("video/", "image/"))
    return FileResponse(target, media_type=asset.mime, filename=asset.filename,
                        content_disposition_type="inline" if inline else "attachment",
                        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})
