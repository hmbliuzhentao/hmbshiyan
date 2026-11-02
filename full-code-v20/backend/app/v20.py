"""V2.0 identity, tenant workspace and audit foundation.

The module is intentionally additive to the V1.5 domain model. V2.0 uses a
separate database and volume; do not point it at the V1.5 production database
until a reviewed migration has been prepared.
"""
import json
import os
import secrets
import smtplib
import uuid
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from urllib.parse import urlencode
from urllib.request import Request as URLRequest, urlopen

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, mapped_column, Session

from . import main as core

router = APIRouter(prefix="/api")
Base = core.Base
User = core.User
Merchant = core.Merchant
MerchantAccount = core.MerchantAccount
db_session = core.db_session
current_user = core.current_user
PASSWORD = core.PASSWORD
JWT_SECRET = core.JWT_SECRET
COOKIE_NAME = core.COOKIE_NAME
COOKIE_SECURE = core.COOKIE_SECURE
UTC = timezone.utc

OTP_TTL_MINUTES = 5
OTP_KINDS = {"register", "password_reset", "bind"}
WORKSPACE_KINDS = {"product", "brief", "script", "storyboard", "prompt", "asset", "note"}


class UserSession(Base):
    __tablename__ = "user_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    ip: Mapped[str] = mapped_column(String(80), default="")
    user_agent: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OTPChallenge(Base):
    __tablename__ = "otp_challenges"
    id: Mapped[int] = mapped_column(primary_key=True)
    destination: Mapped[str] = mapped_column(String(255), index=True)
    channel: Mapped[str] = mapped_column(String(16))
    purpose: Mapped[str] = mapped_column(String(32), index=True)
    code_hash: Mapped[str] = mapped_column(String(255))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OAuthIdentity(Base):
    __tablename__ = "oauth_identities"
    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), index=True)
    subject: Mapped[str] = mapped_column(String(255))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    display_name: Mapped[str] = mapped_column(String(160), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("provider", "subject", name="uq_oauth_provider_subject"),)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    target_type: Mapped[str] = mapped_column(String(50), default="")
    target_id: Mapped[str] = mapped_column(String(100), default="")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    ip: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class WorkspaceItem(Base):
    __tablename__ = "workspace_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    merchant_id: Mapped[int | None] = mapped_column(ForeignKey("merchants.id", ondelete="CASCADE"), nullable=True, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    updated_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class OTPRequestIn(BaseModel):
    destination: str = Field(min_length=5, max_length=255)
    purpose: str = "register"


class RegisterIn(BaseModel):
    destination: str = Field(min_length=5, max_length=255)
    code: str = Field(min_length=6, max_length=8)
    password: str = Field(min_length=12, max_length=128)
    name: str = Field(min_length=1, max_length=80)
    merchant_name: str | None = Field(default=None, max_length=160)


class PasswordResetIn(BaseModel):
    destination: str = Field(min_length=5, max_length=255)
    code: str = Field(min_length=6, max_length=8)
    new_password: str = Field(min_length=12, max_length=128)

class ContactBindIn(BaseModel):
    destination: str = Field(min_length=5, max_length=255)
    code: str = Field(min_length=6, max_length=8)


class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class PasswordSetIn(BaseModel):
    new_password: str = Field(min_length=12, max_length=128)


class WorkspaceCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(default="", max_length=20000)
    status: str = Field(default="draft", max_length=32)
    merchant_id: int | None = None
    metadata: dict = Field(default_factory=dict)


class WorkspacePatchIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = Field(default=None, max_length=20000)
    status: str | None = Field(default=None, max_length=32)
    metadata: dict | None = None


def now_utc():
    return datetime.now(UTC)


def audit(db: Session, actor_id: int | None, action: str, target_type="", target_id="", detail=None, ip=""):
    db.add(AuditLog(actor_id=actor_id, action=action, target_type=target_type,
                    target_id=str(target_id or ""), detail=detail or {}, ip=ip or ""))


def normalize_destination(value: str):
    value = value.strip()
    if "@" in value:
        return value.lower(), "email"
    digits = "".join(ch for ch in value if ch.isdigit() or ch == "+")
    if len(digits) < 8:
        raise HTTPException(422, "手机号格式不正确")
    return digits, "sms"


def send_email_code(destination: str, code: str):
    host = os.getenv("SMTP_HOST")
    sender = os.getenv("SMTP_FROM")
    if not host or not sender:
        raise RuntimeError("邮件服务尚未配置 SMTP_HOST / SMTP_FROM")
    msg = EmailMessage()
    msg["Subject"] = "黑曼波工作台验证码"
    msg["From"] = sender
    msg["To"] = destination
    msg.set_content(f"你的黑曼波验证码是：{code}。有效期 5 分钟，请勿转发。")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME", "")
    password = os.getenv("SMTP_PASSWORD", "")
    if os.getenv("SMTP_SSL", "false").lower() == "true":
        with smtplib.SMTP_SSL(host, port, timeout=15) as smtp:
            if username:
                smtp.login(username, password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            smtp.starttls()
            if username:
                smtp.login(username, password)
            smtp.send_message(msg)


def send_sms_code(destination: str, code: str):
    endpoint = os.getenv("SMS_GATEWAY_URL")
    if not endpoint:
        raise RuntimeError("短信服务尚未配置 SMS_GATEWAY_URL")
    payload = json.dumps({
        "phone": destination,
        "code": code,
        "template_id": os.getenv("SMS_TEMPLATE_ID", ""),
        "ttl_minutes": OTP_TTL_MINUTES,
    }).encode()
    headers = {"Content-Type": "application/json"}
    token = os.getenv("SMS_GATEWAY_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = URLRequest(endpoint, data=payload, headers=headers, method="POST")
    with urlopen(req, timeout=15) as response:
        if response.status < 200 or response.status >= 300:
            raise RuntimeError("短信服务返回失败")


def verify_otp(db: Session, destination: str, code: str, purpose: str):
    row = db.scalar(
        select(OTPChallenge)
        .where(OTPChallenge.destination == destination,
               OTPChallenge.purpose == purpose,
               OTPChallenge.consumed_at.is_(None),
               OTPChallenge.expires_at > now_utc())
        .order_by(OTPChallenge.id.desc())
    )
    if not row or row.attempts >= 5:
        raise HTTPException(400, "验证码无效或已过期")
    if not PASSWORD.verify(code, row.code_hash):
        row.attempts += 1
        db.commit()
        raise HTTPException(400, "验证码错误")
    row.consumed_at = now_utc()
    db.commit()


def session_cookie(response, user: User, request: Request, db: Session):
    jti = str(uuid.uuid4())
    expires = now_utc() + timedelta(hours=12)
    db.add(UserSession(jti=jti, user_id=user.id,
                       ip=request.client.host if request.client else "",
                       user_agent=request.headers.get("user-agent", "")[:500],
                       expires_at=expires))
    db.commit()
    token = jwt.encode({"sub": str(user.id), "jti": jti, "exp": expires}, JWT_SECRET, algorithm="HS256")
    response.set_cookie(
        COOKIE_NAME, token, httponly=True, secure=COOKIE_SECURE,
        samesite=os.getenv("COOKIE_SAMESITE", "lax"), max_age=43200, path="/",
        domain=os.getenv("COOKIE_DOMAIN") or None,
    )


def role_home(user: User):
    if user.role == "merchant":
        return os.getenv("MERCHANT_URL", "https://merchant.heimanbo.com")
    if user.role in ("super_admin", "admin"):
        return os.getenv("WORK_URL", "https://work.heimanbo.com")
    return os.getenv("VIDEO_URL", "https://video.heimanbo.com")


@router.get("/auth/providers")
def auth_providers():
    return {
        "email_otp": bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_FROM")),
        "sms_otp": bool(os.getenv("SMS_GATEWAY_URL")),
        "wechat": bool(os.getenv("WECHAT_APP_ID") and os.getenv("WECHAT_APP_SECRET")),
        "password": True,
    }


@router.post("/auth/otp/request")
def request_otp(payload: OTPRequestIn, request: Request, db: Session = Depends(db_session)):
    if payload.purpose not in OTP_KINDS:
        raise HTTPException(422, "验证码用途不支持")
    destination, channel = normalize_destination(payload.destination)
    recent = db.scalar(select(func.count(OTPChallenge.id)).where(
        OTPChallenge.destination == destination,
        OTPChallenge.created_at >= now_utc() - timedelta(minutes=10)
    )) or 0
    if recent >= 3:
        raise HTTPException(429, "验证码发送过于频繁，请稍后再试")
    code = f"{secrets.randbelow(1_000_000):06d}"
    row = OTPChallenge(destination=destination, channel=channel, purpose=payload.purpose,
                       code_hash=PASSWORD.hash(code), expires_at=now_utc() + timedelta(minutes=OTP_TTL_MINUTES))
    db.add(row)
    try:
        if channel == "email":
            send_email_code(destination, code)
        else:
            send_sms_code(destination, code)
    except Exception as exc:
        db.rollback()
        if os.getenv("APP_ENV") == "development" and os.getenv("OTP_DEBUG") == "true":
            db.add(row)
            db.commit()
            return {"ok": True, "debug_code": code, "expires_in": OTP_TTL_MINUTES * 60}
        raise HTTPException(503, f"验证码服务暂不可用：{str(exc)[:160]}")
    db.commit()
    return {"ok": True, "expires_in": OTP_TTL_MINUTES * 60}


@router.post("/auth/register", status_code=201)
def register(payload: RegisterIn, request: Request, response: Response, db: Session = Depends(db_session)):
    destination, channel = normalize_destination(payload.destination)
    verify_otp(db, destination, payload.code, "register")
    if channel == "email":
        if db.scalar(select(User).where(User.email == destination)):
            raise HTTPException(409, "邮箱已注册")
        email, phone = destination, None
    else:
        if db.scalar(select(User).where(User.phone == destination)):
            raise HTTPException(409, "手机号已注册")
        email, phone = None, destination
    user = User(email=email, phone=phone, name=payload.name.strip(), role="merchant",
                password_hash=PASSWORD.hash(payload.password), is_active=True)
    user.password_changed_at = now_utc()
    if channel == "email":
        user.email_verified_at = now_utc()
    else:
        user.phone_verified_at = now_utc()
    db.add(user)
    db.flush()
    merchant = Merchant(name=(payload.merchant_name or payload.name).strip(),
                        contact_name=payload.name.strip(), phone=phone or "",
                        status="pending")
    db.add(merchant)
    db.flush()
    db.add(MerchantAccount(merchant_id=merchant.id, user_id=user.id))
    audit(db, user.id, "merchant.register", "merchant", merchant.id,
          {"channel": channel, "destination": destination},
          request.client.host if request.client else "")
    db.commit()
    session_cookie(response, user, request, db)
    return {"user": core.user_out(user), "merchant_status": "pending"}


@router.post("/auth/password/reset")
def reset_password(payload: PasswordResetIn, request: Request, db: Session = Depends(db_session)):
    destination, channel = normalize_destination(payload.destination)
    verify_otp(db, destination, payload.code, "password_reset")
    user = db.scalar(select(User).where(User.email == destination if channel == "email" else User.phone == destination))
    if not user:
        raise HTTPException(404, "账号不存在")
    user.password_hash = PASSWORD.hash(payload.new_password)
    user.password_changed_at = now_utc()
    sessions = list(db.scalars(select(UserSession).where(UserSession.user_id == user.id,
                                                         UserSession.revoked_at.is_(None))).all())
    for s in sessions:
        s.revoked_at = now_utc()
    audit(db, user.id, "auth.password_reset", "user", user.id, {"channel": channel},
          request.client.host if request.client else "")
    db.commit()
    return {"ok": True, "message": "密码已重置，请重新登录"}


def wechat_configured():
    return bool(os.getenv("WECHAT_APP_ID") and os.getenv("WECHAT_APP_SECRET"))


@router.get("/auth/wechat/start")
def wechat_start(request: Request, mode: str = "login", db: Session = Depends(db_session)):
    if not wechat_configured():
        raise HTTPException(503, "微信开放平台网站应用尚未配置")
    if mode not in ("login", "bind"):
        raise HTTPException(422, "微信授权模式不正确")
    uid = None
    if mode == "bind":
        if request is None:
            raise HTTPException(401, "请先登录")
        user = core.current_user(request, db)
        uid = user.id
    state = jwt.encode({"nonce": secrets.token_urlsafe(18), "mode": mode, "uid": uid,
                        "exp": now_utc() + timedelta(minutes=5)}, JWT_SECRET, algorithm="HS256")
    callback = os.getenv("WECHAT_REDIRECT_URI", "https://auth.heimanbo.com/api/auth/wechat/callback")
    params = {
        "appid": os.environ["WECHAT_APP_ID"],
        "redirect_uri": callback,
        "response_type": "code",
        "scope": "snsapi_login",
        "state": state,
    }
    url = "https://open.weixin.qq.com/connect/qrconnect?" + urlencode(params) + "#wechat_redirect"
    return RedirectResponse(url, status_code=302)


def wechat_json(url: str):
    with urlopen(url, timeout=15) as response:
        data = json.loads(response.read().decode("utf-8"))
    if data.get("errcode"):
        raise RuntimeError(data.get("errmsg", "微信授权失败"))
    return data


@router.get("/auth/wechat/callback")
def wechat_callback(code: str, state: str, request: Request, db: Session = Depends(db_session)):
    if not wechat_configured():
        raise HTTPException(503, "微信开放平台网站应用尚未配置")
    try:
        state_data = jwt.decode(state, JWT_SECRET, algorithms=["HS256"])
        token_data = wechat_json(
            "https://api.weixin.qq.com/sns/oauth2/access_token?" + urlencode({
                "appid": os.environ["WECHAT_APP_ID"],
                "secret": os.environ["WECHAT_APP_SECRET"],
                "code": code,
                "grant_type": "authorization_code",
            })
        )
        openid = token_data["openid"]
        profile = wechat_json(
            "https://api.weixin.qq.com/sns/userinfo?" + urlencode({
                "access_token": token_data["access_token"], "openid": openid, "lang": "zh_CN"
            })
        )
    except Exception:
        return RedirectResponse(os.getenv("AUTH_URL", "https://auth.heimanbo.com") + "/?error=wechat_authorization_failed")
    identity = db.scalar(select(OAuthIdentity).where(OAuthIdentity.provider == "wechat",
                                                      OAuthIdentity.subject == openid))
    mode = state_data.get("mode", "login")
    if mode == "bind":
        try:
            current = core.current_user(request, db)
        except HTTPException:
            return RedirectResponse(os.getenv("AUTH_URL", "https://auth.heimanbo.com") + "/?error=login_required")
        if state_data.get("uid") != current.id:
            return RedirectResponse(os.getenv("AUTH_URL", "https://auth.heimanbo.com") + "/?error=wechat_state_mismatch")
        if identity and identity.user_id != current.id:
            return RedirectResponse(os.getenv("AUTH_URL", "https://auth.heimanbo.com") + "/?error=wechat_already_bound")
        if not identity:
            db.add(OAuthIdentity(provider="wechat", subject=openid, user_id=current.id,
                                 display_name=profile.get("nickname", "")[:160]))
            audit(db, current.id, "auth.wechat_bind", "user", current.id, {})
            db.commit()
        return RedirectResponse(os.getenv("ACCOUNT_URL", "https://auth.heimanbo.com") + "/?wechat=bound")
    if identity:
        user = db.get(User, identity.user_id)
    else:
        nickname = (profile.get("nickname") or "微信商家").strip()[:80]
        user = User(email=None, phone=None, name=nickname, role="merchant",
                    password_hash=PASSWORD.hash(secrets.token_urlsafe(32)), is_active=True)
        db.add(user)
        db.flush()
        merchant = Merchant(name=nickname, contact_name=nickname, status="pending")
        db.add(merchant)
        db.flush()
        db.add(MerchantAccount(merchant_id=merchant.id, user_id=user.id))
        db.add(OAuthIdentity(provider="wechat", subject=openid, user_id=user.id,
                             display_name=nickname[:160]))
        audit(db, user.id, "auth.wechat_register", "merchant", merchant.id, {})
        db.commit()
    if not user or not user.is_active:
        return RedirectResponse(os.getenv("AUTH_URL", "https://auth.heimanbo.com") + "/?error=account_disabled")
    response = RedirectResponse(role_home(user), status_code=302)
    session_cookie(response, user, request, db)
    return response


@router.get("/auth/sessions")
def list_sessions(request: Request, user: User = Depends(current_user), db: Session = Depends(db_session)):
    token = request.cookies.get(COOKIE_NAME)
    current_jti = None
    if token:
        try:
            current_jti = jwt.decode(token, JWT_SECRET, algorithms=["HS256"]).get("jti")
        except jwt.PyJWTError:
            pass
    rows = list(db.scalars(select(UserSession).where(UserSession.user_id == user.id)
                           .order_by(UserSession.created_at.desc()).limit(50)).all())
    return [{"id": s.id, "ip": s.ip, "user_agent": s.user_agent, "created_at": s.created_at.isoformat(),
             "expires_at": s.expires_at.isoformat(), "revoked": bool(s.revoked_at),
             "current": s.jti == current_jti} for s in rows]


@router.delete("/auth/sessions/{session_id}")
def revoke_session(session_id: int, user: User = Depends(current_user), db: Session = Depends(db_session)):
    session = db.scalar(select(UserSession).where(UserSession.id == session_id, UserSession.user_id == user.id))
    if not session:
        raise HTTPException(404, "会话不存在")
    session.revoked_at = now_utc()
    db.commit()
    return {"ok": True}


@router.get("/auth/identities")
def auth_identities(user: User = Depends(current_user), db: Session = Depends(db_session)):
    links = list(db.scalars(select(OAuthIdentity).where(OAuthIdentity.user_id == user.id)).all())
    return {
        "email": user.email or "",
        "phone": user.phone or "",
        "email_verified": bool(user.email_verified_at),
        "phone_verified": bool(user.phone_verified_at),
        "wechat_bound": any(x.provider == "wechat" for x in links),
        "has_password": bool(user.password_changed_at),
    }


@router.post("/auth/contact/bind")
def bind_contact(payload: ContactBindIn, request: Request,
                 user: User = Depends(current_user), db: Session = Depends(db_session)):
    destination, channel = normalize_destination(payload.destination)
    verify_otp(db, destination, payload.code, "bind")
    if channel == "email":
        exists = db.scalar(select(User).where(User.email == destination, User.id != user.id))
        if exists:
            raise HTTPException(409, "该邮箱已绑定其他账号")
        user.email = destination
        user.email_verified_at = now_utc()
    else:
        exists = db.scalar(select(User).where(User.phone == destination, User.id != user.id))
        if exists:
            raise HTTPException(409, "该手机号已绑定其他账号")
        user.phone = destination
        user.phone_verified_at = now_utc()
        if user.role == "merchant":
            merchant = core.get_merchant_of_user(db, user)
            merchant.phone = destination
    audit(db, user.id, "auth.contact_bind", "user", user.id, {"channel": channel},
          request.client.host if request.client else "")
    db.commit()
    return {"ok": True, "email": user.email or "", "phone": user.phone or ""}


@router.post("/auth/password/set")
def set_password(payload: PasswordSetIn, request: Request,
                 user: User = Depends(current_user), db: Session = Depends(db_session)):
    if user.password_changed_at is not None or (user.email and not user.email_verified_at) or (user.phone and not user.phone_verified_at):
        raise HTTPException(409, "当前账号已有密码，请使用修改密码功能")
    if not (user.email_verified_at or user.phone_verified_at):
        raise HTTPException(400, "请先绑定并验证手机号或邮箱")
    user.password_hash = PASSWORD.hash(payload.new_password)
    user.password_changed_at = now_utc()
    audit(db, user.id, "auth.password_set", "user", user.id, {},
          request.client.host if request.client else "")
    db.commit()
    return {"ok": True}


@router.post("/auth/password/change")
def change_password(payload: PasswordChangeIn, request: Request,
                    user: User = Depends(current_user), db: Session = Depends(db_session)):
    if not PASSWORD.verify(payload.current_password, user.password_hash):
        raise HTTPException(400, "当前密码不正确")
    user.password_hash = PASSWORD.hash(payload.new_password)
    user.password_changed_at = now_utc()
    audit(db, user.id, "auth.password_change", "user", user.id, {},
          request.client.host if request.client else "")
    db.commit()
    return {"ok": True}


@router.post("/auth/wechat/unbind")
def unbind_wechat(payload: ContactBindIn, request: Request,
                  user: User = Depends(current_user), db: Session = Depends(db_session)):
    destination, channel = normalize_destination(payload.destination)
    verify_otp(db, destination, payload.code, "bind")
    bound_value = user.email if channel == "email" else user.phone
    if not bound_value or bound_value != destination:
        raise HTTPException(403, "验证码必须发送到当前账号已绑定的联系方式")
    identity = db.scalar(select(OAuthIdentity).where(OAuthIdentity.user_id == user.id,
                                                      OAuthIdentity.provider == "wechat"))
    if not identity:
        raise HTTPException(404, "当前账号未绑定微信")
    db.delete(identity)
    audit(db, user.id, "auth.wechat_unbind", "user", user.id, {"channel": channel},
          request.client.host if request.client else "")
    db.commit()
    return {"ok": True}


def workspace_item_out(item: WorkspaceItem):
    return {"id": item.id, "kind": item.kind, "title": item.title, "body": item.body,
            "status": item.status, "merchant_id": item.merchant_id, "metadata": item.metadata_json or {},
            "created_by": item.created_by, "updated_by": item.updated_by,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None}


def workspace_scope(db: Session, user: User, kind: str):
    if kind not in WORKSPACE_KINDS:
        raise HTTPException(404, "功能分类不存在")
    stmt = select(WorkspaceItem).where(WorkspaceItem.kind == kind)
    if user.role == "merchant":
        merchant = core.get_merchant_of_user(db, user)
        if merchant.status != "approved":
            raise HTTPException(403, "商家账号尚未审核通过")
        stmt = stmt.where(WorkspaceItem.merchant_id == merchant.id)
    return stmt


@router.get("/workspace/{kind}")
def list_workspace(kind: str, q: str = "", page: int = 1, limit: int = 50,
                   user: User = Depends(current_user), db: Session = Depends(db_session)):
    stmt = workspace_scope(db, user, kind)
    if q.strip():
        stmt = stmt.where(WorkspaceItem.title.ilike(f"%{q.strip()[:100]}%"))
    page, limit = max(1, page), min(100, max(1, limit))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(db.scalars(stmt.order_by(WorkspaceItem.updated_at.desc(), WorkspaceItem.id.desc())
                           .offset((page - 1) * limit).limit(limit)).all())
    return {"items": [workspace_item_out(x) for x in rows], "total": total, "page": page, "limit": limit}


@router.post("/workspace/{kind}", status_code=201)
def create_workspace(kind: str, payload: WorkspaceCreateIn, request: Request,
                     user: User = Depends(current_user), db: Session = Depends(db_session)):
    if kind not in WORKSPACE_KINDS:
        raise HTTPException(404, "功能分类不存在")
    merchant_id = payload.merchant_id
    if user.role == "merchant":
        if kind not in {"product", "brief", "asset"}:
            raise HTTPException(403, "商家不能创建此类内部资料")
        merchant = core.get_merchant_of_user(db, user)
        if merchant.status != "approved":
            raise HTTPException(403, "商家账号尚未审核通过")
        merchant_id = merchant.id
    elif user.role not in {"super_admin", "admin", "manager", "producer", "editor"}:
        raise HTTPException(403, "当前角色仅可查看资料")
    if merchant_id is not None and not db.get(Merchant, merchant_id):
        raise HTTPException(404, "关联商家不存在")
    item = WorkspaceItem(kind=kind, title=payload.title.strip(), body=payload.body,
                         status=payload.status, merchant_id=merchant_id,
                         metadata_json=payload.metadata, created_by=user.id, updated_by=user.id)
    db.add(item)
    db.flush()
    audit(db, user.id, f"workspace.{kind}.create", kind, item.id, {}, request.client.host if request.client else "")
    db.commit()
    db.refresh(item)
    return workspace_item_out(item)


@router.patch("/workspace/{kind}/{item_id}")
def update_workspace(kind: str, item_id: int, payload: WorkspacePatchIn, request: Request,
                     user: User = Depends(current_user), db: Session = Depends(db_session)):
    if user.role == "viewer":
        raise HTTPException(403, "只读账号不能修改资料")
    stmt = workspace_scope(db, user, kind).where(WorkspaceItem.id == item_id)
    item = db.scalar(stmt)
    if not item:
        raise HTTPException(404, "资料不存在")
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(item, "metadata_json" if key == "metadata" else key, value)
    item.updated_by = user.id
    audit(db, user.id, f"workspace.{kind}.update", kind, item.id, {"fields": list(changes)},
          request.client.host if request.client else "")
    db.commit()
    db.refresh(item)
    return workspace_item_out(item)


@router.delete("/workspace/{kind}/{item_id}")
def delete_workspace(kind: str, item_id: int, request: Request,
                     user: User = Depends(current_user), db: Session = Depends(db_session)):
    if user.role == "viewer":
        raise HTTPException(403, "只读账号不能删除资料")
    item = db.scalar(workspace_scope(db, user, kind).where(WorkspaceItem.id == item_id))
    if not item:
        raise HTTPException(404, "资料不存在")
    if user.role == "merchant" and item.created_by != user.id:
        raise HTTPException(403, "只能删除自己创建的资料")
    db.delete(item)
    audit(db, user.id, f"workspace.{kind}.delete", kind, item.id, {},
          request.client.host if request.client else "")
    db.commit()
    return {"ok": True}


@router.get("/system/audit-logs")
def list_audit_logs(page: int = 1, limit: int = 50,
                    user: User = Depends(core.require_admin), db: Session = Depends(db_session)):
    page, limit = max(1, page), min(200, max(1, limit))
    stmt = select(AuditLog).order_by(AuditLog.id.desc())
    total = db.scalar(select(func.count()).select_from(AuditLog)) or 0
    rows = list(db.scalars(stmt.offset((page - 1) * limit).limit(limit)).all())
    return {"items": [{"id": x.id, "actor_id": x.actor_id, "action": x.action,
                       "target_type": x.target_type, "target_id": x.target_id,
                       "detail": x.detail or {}, "ip": x.ip,
                       "created_at": x.created_at.isoformat() if x.created_at else None}
                      for x in rows], "total": total}


@router.get("/system/overview")
def system_overview(user: User = Depends(core.require_admin), db: Session = Depends(db_session)):
    return {
        "users": db.scalar(select(func.count(User.id))) or 0,
        "merchants": db.scalar(select(func.count(Merchant.id))) or 0,
        "pending_merchants": db.scalar(select(func.count(Merchant.id)).where(Merchant.status == "pending")) or 0,
        "workspace_items": db.scalar(select(func.count(WorkspaceItem.id))) or 0,
        "active_sessions": db.scalar(select(func.count(UserSession.id)).where(
            UserSession.revoked_at.is_(None), UserSession.expires_at > now_utc())) or 0,
    }
