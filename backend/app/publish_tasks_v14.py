"""BlackMambo V1.5: merchant-initiated publishing tasks + video review.

Merchants initiate orders and tasks; staff quote and deliver videos to the tasks.
Only the related merchant may access or approve/reject each video.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import os
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .main import (
    Base, BusinessOrder, Merchant, User, Video, DATA_DIR, current_user,
    db_session, get_merchant_of_user, require_staff, require_admin, iso,
    upload_video,
)

router = APIRouter(prefix="/api")


class PublishTask(Base):
    __tablename__ = "publish_tasks_v14"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("business_orders.id", ondelete="RESTRICT"), index=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id", ondelete="RESTRICT"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    platform: Mapped[str] = mapped_column(String(40), default="TikTok")
    account_label: Mapped[str] = mapped_column(String(120), default="")
    publish_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    instructions: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    published_url: Mapped[str] = mapped_column(String(500), default="")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    assigned_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PublishVideo(Base):
    __tablename__ = "publish_task_videos_v14"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("publish_tasks_v14.id", ondelete="RESTRICT"), index=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="RESTRICT"), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    review_status: Mapped[str] = mapped_column(String(32), default="pending_review")
    review_note: Mapped[str] = mapped_column(String(2000), default="")
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PublishReviewEvent(Base):
    __tablename__ = "publish_review_events_v14"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("publish_tasks_v14.id"), index=True)
    link_id: Mapped[int] = mapped_column(ForeignKey("publish_task_videos_v14.id"), index=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(32))
    note: Mapped[str] = mapped_column(String(2000), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PublishTaskIn(BaseModel):
    order_id: int
    title: str = Field(min_length=2, max_length=200)
    platform: str = Field(default="TikTok", min_length=2, max_length=40)
    account_label: str = Field(default="", max_length=120)
    publish_date: date | None = None
    instructions: str = Field(default="", max_length=3000)


class AssignmentIn(BaseModel):
    assigned_user_id: int | None = None


class AttachVideoIn(BaseModel):
    video_id: str


class ReviewIn(BaseModel):
    decision: Literal["approved", "changes_requested"]
    note: str = Field(default="", max_length=2000)


class PublishedIn(BaseModel):
    published_url: str = Field(default="", max_length=500)


def merchant_task(db: Session, task_id: int, user: User) -> PublishTask:
    if user.role != "merchant":
        raise HTTPException(403, "仅关联商家账号可操作")
    merchant = get_merchant_of_user(db, user)
    if merchant.status == "suspended":
        raise HTTPException(403, "商家账号已暂停")
    task = db.scalar(select(PublishTask).where(PublishTask.id == task_id, PublishTask.merchant_id == merchant.id))
    if task is None:
        raise HTTPException(404, "发布任务不存在")
    return task


def staff_task(db: Session, task_id: int, user: User) -> PublishTask:
    t = db.get(PublishTask, task_id)
    if t is None:
        raise HTTPException(404, "发布任务不存在")
    if user.role == "producer" and t.assigned_user_id != user.id:
        # Hide unassigned and other producers' work from task IDs and URL guessing.
        raise HTTPException(404, "发布任务不存在")
    if user.role not in ("admin", "producer"):
        raise HTTPException(403, "当前账号无权访问制作任务")
    return t


def current_links(db: Session, task_id: int):
    return list(db.scalars(select(PublishVideo).where(PublishVideo.task_id == task_id,
        PublishVideo.active.is_(True)).order_by(PublishVideo.id.desc())).all())


def status_sync(db: Session, task: PublishTask):
    statuses = [v.review_status for v in current_links(db, task.id)]
    if not statuses:
        if task.assigned_user_id:
            task.status = "in_progress" if task.accepted_at else "assigned"
        else:
            task.status = "draft"
    elif "changes_requested" in statuses:
        task.status = "changes_requested"
    elif all(s == "approved" for s in statuses):
        task.status = "approved"
    else:
        task.status = "pending_review"


def task_out(db: Session, task: PublishTask, *, merchant_view: bool):
    order = db.get(BusinessOrder, task.order_id)
    videos = []
    for link in current_links(db, task.id):
        v = db.get(Video, link.video_id)
        if v is None:
            continue
        videos.append({
            "id": link.id, "video_id": v.id, "filename": v.filename,
            "mime": v.mime, "size_bytes": v.size_bytes,
            "review_status": link.review_status, "review_note": link.review_note,
            "reviewed_at": iso(link.reviewed_at),
            "file_deleted": v.status == "deleted",
            "url": "" if v.status == "deleted" else f"/api/{'portal' if merchant_view else 'staff'}/publish-tasks/{task.id}/videos/{link.id}/stream",
        })
    out = {
        "id": task.id, "order_id": task.order_id,
        "order_no": order.order_no if order else "",
        "order_title": order.title if order else "",
        "title": task.title, "platform": task.platform,
        "account_label": task.account_label, "publish_date": iso(task.publish_date),
        "instructions": task.instructions, "status": task.status,
        "published_url": task.published_url,
        "created_at": iso(task.created_at), "videos": videos,
    }
    if not merchant_view:
        m = db.get(Merchant, task.merchant_id)
        assigned_user = db.get(User, task.assigned_user_id) if task.assigned_user_id else None
        out["merchant_id"] = task.merchant_id
        out["merchant_name"] = m.name if m else ""
        out["assigned_user_id"] = task.assigned_user_id
        out["assigned_user_name"] = assigned_user.name if assigned_user else ""
        out["assigned_at"] = iso(task.assigned_at)
        out["accepted_at"] = iso(task.accepted_at)
    return out


def require_mutable(task: PublishTask):
    if task.status == "published":
        raise HTTPException(409, "已发布任务不可修改视频，请新建任务")
    if task.status == "cancelled":
        raise HTTPException(409, "已取消任务不可修改")


def attach(db: Session, task: PublishTask, video_id: str, actor: User):
    require_mutable(task)
    if actor.role == "producer" and not task.accepted_at:
        raise HTTPException(409, "请先接单，再提交制作视频")
    if actor.role == "producer" and any(v.review_status == "changes_requested" for v in current_links(db, task.id)):
        raise HTTPException(409, "存在被退回的视频，请使用对应视频的提交新版功能")
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(404, "视频库中不存在该文件")
    if actor.role == "producer" and video.created_by != actor.id:
        raise HTTPException(403, "拍摄剪辑只能关联自己上传的视频")
    if db.scalar(select(PublishVideo.id).where(PublishVideo.task_id == task.id,
            PublishVideo.video_id == video_id, PublishVideo.active.is_(True))):
        raise HTTPException(409, "该视频已加入本任务")
    link = PublishVideo(task_id=task.id, video_id=video_id,
                        review_status="pending_review", submitted_by=actor.id)
    db.add(link)
    db.flush()
    status_sync(db, task)
    db.commit()
    return task_out(db, task, merchant_view=False)


@router.get("/staff/publish-tasks")
def list_staff_tasks(order_id: int | None = None, status: str = "",
                     user: User = Depends(require_staff), db: Session = Depends(db_session)):
    stmt = select(PublishTask)
    if user.role == "producer":
        stmt = stmt.where(PublishTask.assigned_user_id == user.id)
    if order_id is not None:
        stmt = stmt.where(PublishTask.order_id == order_id)
    if status:
        if status not in {"draft", "assigned", "in_progress", "pending_review", "changes_requested", "approved", "published"}:
            raise HTTPException(400, "状态不合法")
        stmt = stmt.where(PublishTask.status == status)
    tasks = db.scalars(stmt.order_by(PublishTask.id.desc()).limit(300)).all()
    return [task_out(db, x, merchant_view=False) for x in tasks]


@router.get("/staff/publish-tasks/summary")
def summary(user: User = Depends(require_staff), db: Session = Depends(db_session)):
    stmt = select(PublishTask.status, func.count(PublishTask.id))
    if user.role == "producer":
        stmt = stmt.where(PublishTask.assigned_user_id == user.id)
    rows = db.execute(stmt.group_by(PublishTask.status)).all()
    counts = dict(rows)
    return {"total": sum(counts.values()), "draft": counts.get("draft", 0),
            "assigned": counts.get("assigned", 0), "in_progress": counts.get("in_progress", 0),
            "pending_review": counts.get("pending_review", 0),
            "changes_requested": counts.get("changes_requested", 0),
            "approved": counts.get("approved", 0), "published": counts.get("published", 0)}


@router.post("/staff/publish-tasks", status_code=201)
def create_publish_task(payload: PublishTaskIn, user: User = Depends(require_staff), db: Session = Depends(db_session)):
    raise HTTPException(403, "发布任务须由商家在商家工作台发起")


@router.post("/portal/publish-tasks", status_code=201)
def merchant_create_publish_task(payload: PublishTaskIn, user: User = Depends(current_user), db: Session = Depends(db_session)):
    merchant = get_merchant_of_user(db, user)
    if merchant.status == "suspended":
        raise HTTPException(403, "商家账号已暂停")
    # Critical authorization: request order must belong to logged-in merchant.
    order = db.scalar(select(BusinessOrder).where(BusinessOrder.id == payload.order_id,
                                                 BusinessOrder.merchant_id == merchant.id))
    if order is None:
        raise HTTPException(404, "订单不存在或不属于当前商家")
    if order.status == "cancelled":
        raise HTTPException(409, "已取消订单不能创建发布任务")
    if not payload.title.strip() or not payload.platform.strip():
        raise HTTPException(400, "任务名称和发布平台不能为空")
    task = PublishTask(order_id=order.id, merchant_id=merchant.id,
                       title=payload.title.strip(), platform=payload.platform.strip(),
                       account_label=payload.account_label.strip(), publish_date=payload.publish_date,
                       instructions=payload.instructions.strip(), created_by=user.id)
    db.add(task); db.commit(); db.refresh(task)
    return task_out(db, task, merchant_view=True)


@router.post("/staff/publish-tasks/{task_id}/assign")
def assign_publish_task(task_id: int, payload: AssignmentIn,
                        user: User = Depends(require_admin), db: Session = Depends(db_session)):
    task = db.scalar(select(PublishTask).where(PublishTask.id == task_id).with_for_update())
    if not task:
        raise HTTPException(404, "发布任务不存在")
    if task.status in ("published", "cancelled") or current_links(db, task.id):
        raise HTTPException(409, "已有视频交付或任务已结束，不能重新分配")
    if payload.assigned_user_id is None:
        task.assigned_user_id = None
        task.assigned_at = None
        task.accepted_at = None
        task.status = "draft"
    else:
        producer = db.get(User, payload.assigned_user_id)
        if not producer or producer.role != "producer" or not producer.is_active:
            raise HTTPException(400, "请选择有效的拍摄剪辑账号")
        task.assigned_user_id = producer.id
        task.assigned_at = datetime.now(timezone.utc)
        task.accepted_at = None
        task.status = "assigned"
    db.commit()
    return task_out(db, task, merchant_view=False)


@router.post("/staff/publish-tasks/{task_id}/accept")
def accept_publish_task(task_id: int, user: User = Depends(require_staff), db: Session = Depends(db_session)):
    if user.role != "producer":
        raise HTTPException(403, "仅拍摄剪辑账号需要接单")
    task = staff_task(db, task_id, user)
    if task.status != "assigned":
        raise HTTPException(409, "当前任务不是待接单状态")
    task.accepted_at = datetime.now(timezone.utc)
    task.status = "in_progress"
    db.commit()
    return task_out(db, task, merchant_view=False)


@router.post("/staff/publish-tasks/{task_id}/decline")
def decline_publish_task(task_id: int, user: User = Depends(require_staff), db: Session = Depends(db_session)):
    if user.role != "producer":
        raise HTTPException(403, "仅拍摄剪辑账号可以退回待接任务")
    task = staff_task(db, task_id, user)
    if task.status != "assigned" or current_links(db, task.id):
        raise HTTPException(409, "任务已接单或已有制作文件，不能退回")
    task.assigned_user_id = None
    task.assigned_at = None
    task.accepted_at = None
    task.status = "draft"
    db.commit()
    return task_out(db, task, merchant_view=False)


@router.get("/staff/publish-tasks/{task_id}")
def staff_detail(task_id: int, user: User = Depends(require_staff), db: Session = Depends(db_session)):
    return task_out(db, staff_task(db, task_id, user), merchant_view=False)


@router.get("/staff/publish-tasks/{task_id}/review-history")
def review_history(task_id: int, user: User = Depends(require_staff), db: Session = Depends(db_session)):
    staff_task(db, task_id, user)
    rows = db.scalars(select(PublishReviewEvent).where(PublishReviewEvent.task_id == task_id)
                      .order_by(PublishReviewEvent.id.desc()).limit(200)).all()
    out = []
    for r in rows:
        link = db.get(PublishVideo, r.link_id)
        video = db.get(Video, link.video_id) if link else None
        reviewer = db.get(User, r.reviewer_id)
        out.append({"decision": r.decision, "note": r.note,
                    "filename": video.filename if video else "已移除文件",
                    "reviewer": reviewer.name if reviewer else "商家",
                    "created_at": iso(r.created_at)})
    return out


@router.post("/staff/publish-tasks/{task_id}/videos", status_code=201)
def attach_library_video(task_id: int, payload: AttachVideoIn,
                         user: User = Depends(require_staff), db: Session = Depends(db_session)):
    return attach(db, staff_task(db, task_id, user), payload.video_id, user)


@router.post("/staff/publish-tasks/{task_id}/upload", status_code=201)
async def upload_and_attach(task_id: int, file: UploadFile = File(...),
                            user: User = Depends(require_staff), db: Session = Depends(db_session)):
    task = staff_task(db, task_id, user)
    require_mutable(task)
    if user.role == "producer" and not task.accepted_at:
        raise HTTPException(409, "请先接单，再上传制作视频")
    if user.role == "producer" and any(v.review_status == "changes_requested" for v in current_links(db, task.id)):
        raise HTTPException(409, "存在被退回的视频，请使用该视频下方的‘提交新版’功能")
    created = await upload_video(file=file, user=user, db=db)
    return attach(db, task, created["id"], user)


@router.post("/staff/publish-tasks/{task_id}/videos/{link_id}/replace")
async def replace_video(task_id: int, link_id: int, file: UploadFile = File(...),
                        user: User = Depends(require_staff), db: Session = Depends(db_session)):
    task = staff_task(db, task_id, user)
    require_mutable(task)
    if user.role == "producer" and not task.accepted_at:
        raise HTTPException(409, "请先接单，再提交修改版本")
    old = db.scalar(select(PublishVideo).where(PublishVideo.id == link_id,
        PublishVideo.task_id == task_id, PublishVideo.active.is_(True)).with_for_update())
    if old is None:
        raise HTTPException(404, "原视频不存在")
    if user.role == "producer" and old.review_status != "changes_requested":
        raise HTTPException(409, "拍摄剪辑只能替换商家已退回的视频")
    created = await upload_video(file=file, user=user, db=db)
    old.active = False  # keep prior merchant review & original file for audit
    db.add(PublishVideo(task_id=task_id, video_id=created["id"],
                        review_status="pending_review", submitted_by=user.id))
    db.flush()
    status_sync(db, task)
    db.commit()
    return task_out(db, task, merchant_view=False)


@router.post("/staff/publish-tasks/{task_id}/published")
def mark_published_by_staff(task_id: int, payload: PublishedIn,
                            user: User = Depends(require_staff), db: Session = Depends(db_session)):
    raise HTTPException(403, "视频发布情况由商家自行登记")


@router.post("/portal/publish-tasks/{task_id}/published")
def merchant_mark_published(task_id: int, payload: PublishedIn,
                            user: User = Depends(current_user), db: Session = Depends(db_session)):
    # Enforce both ownership and state transition server-side.
    task = merchant_task(db, task_id, user)
    task = db.scalar(select(PublishTask).where(PublishTask.id == task.id,
                                                 PublishTask.merchant_id == task.merchant_id).with_for_update())
    if task.status != "approved":
        raise HTTPException(409, "必须先审核通过全部视频才能登记已发布")
    if payload.published_url and not payload.published_url.startswith(("https://", "http://")):
        raise HTTPException(400, "发布链接必须是 http(s) 地址")
    task.status = "published"
    task.published_url = payload.published_url.strip()
    db.commit()
    # User's storage policy: after the merchant explicitly confirms publication,
    # keep database metadata/review history but remove the original media files.
    if os.getenv("DELETE_MEDIA_AFTER_MERCHANT_CONFIRMATION", "true").lower() in ("1", "true", "yes", "on"):
        videos_to_remove = []
        for link in current_links(db, task.id):
            video = db.get(Video, link.video_id)
            if video and video.status != "deleted":
                video.status = "deleted"  # block all stream routes before touching disk
                videos_to_remove.append(video)
        db.commit()
        for video in videos_to_remove:
            target = DATA_DIR / video.storage_key
            try:
                target.unlink(missing_ok=True)
            except OSError:
                # Metadata remains marked unavailable; a later storage cleanup can retry.
                pass
    return task_out(db, task, merchant_view=True)


@router.get("/portal/publish-tasks")
def list_merchant_tasks(user: User = Depends(current_user), db: Session = Depends(db_session)):
    if user.role != "merchant":
        raise HTTPException(403, "仅商家可访问")
    merchant = get_merchant_of_user(db, user)
    if merchant.status == "suspended":
        raise HTTPException(403, "商家账号已暂停")
    tasks = db.scalars(select(PublishTask).where(PublishTask.merchant_id == merchant.id)
        .order_by(PublishTask.id.desc()).limit(300)).all()
    return [task_out(db, x, merchant_view=True) for x in tasks]


@router.get("/portal/publish-tasks/{task_id}")
def merchant_detail(task_id: int, user: User = Depends(current_user), db: Session = Depends(db_session)):
    task = merchant_task(db, task_id, user)
    return task_out(db, task, merchant_view=True)


@router.post("/portal/publish-tasks/{task_id}/videos/{link_id}/review")
def review_video(task_id: int, link_id: int, payload: ReviewIn,
                 user: User = Depends(current_user), db: Session = Depends(db_session)):
    task = merchant_task(db, task_id, user)
    if task.status in ("draft", "published", "cancelled"):
        raise HTTPException(409, "当前任务不可审核")
    link = db.scalar(select(PublishVideo).where(PublishVideo.task_id == task_id,
        PublishVideo.id == link_id, PublishVideo.active.is_(True)).with_for_update())
    if not link:
        raise HTTPException(404, "视频不存在")
    if link.review_status != "pending_review":
        raise HTTPException(409, "该视频已审核或退回，请由工作人员重新提交新版本")
    if payload.decision == "changes_requested" and len(payload.note.strip()) < 3:
        raise HTTPException(400, "退回修改需填写至少3个字的修改意见")
    link.review_status = payload.decision
    link.review_note = payload.note.strip()
    link.reviewed_by = user.id
    link.reviewed_at = datetime.now(timezone.utc)
    db.add(PublishReviewEvent(task_id=task_id, link_id=link_id,
                              reviewer_id=user.id, decision=payload.decision,
                              note=payload.note.strip()))
    db.flush()
    status_sync(db, task)
    db.commit()
    return task_out(db, task, merchant_view=True)


def serve_video(task_id: int, link_id: int, db: Session):
    link = db.scalar(select(PublishVideo).where(PublishVideo.task_id == task_id,
        PublishVideo.id == link_id, PublishVideo.active.is_(True)))
    if not link:
        raise HTTPException(404, "视频不存在")
    video = db.get(Video, link.video_id)
    if not video or video.status == "deleted":
        raise HTTPException(404, "视频文件不存在或已按商家确认清理")
    target = DATA_DIR / video.storage_key
    if not target.is_file():
        raise HTTPException(404, "原始文件不存在")
    return FileResponse(target, media_type=video.mime, filename=video.filename,
                        content_disposition_type="inline",
                        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/portal/publish-tasks/{task_id}/videos/{link_id}/stream")
def merchant_video_stream(task_id: int, link_id: int, user: User = Depends(current_user),
                          db: Session = Depends(db_session)):
    t = merchant_task(db, task_id, user)
    if t.status == "draft":
        raise HTTPException(404, "视频不存在")
    return serve_video(task_id, link_id, db)


@router.get("/staff/publish-tasks/{task_id}/videos/{link_id}/stream")
def staff_video_stream(task_id: int, link_id: int, user: User = Depends(require_staff),
                       db: Session = Depends(db_session)):
    staff_task(db, task_id, user)
    return serve_video(task_id, link_id, db)
