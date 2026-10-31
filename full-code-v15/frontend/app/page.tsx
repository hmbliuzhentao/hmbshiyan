"use client";
import { useEffect, useState, type FormEvent } from "react";
import OrdersPanel, { OrdersSummary } from "./orders";
import {MerchantsPanelV14, MerchantPortalV14} from "./merchants-v14";
import {StaffPublishTasksV14} from "./publish-tasks-v14";
import {StaffProjectsV13} from "./merchant-projects-v13";

type User = { id: number; name: string; email: string; role: string; created_at: string };
type Video = { id: string; filename: string; size_bytes: number; status: string; created_at: string; stream_url: string; created_by: number };
type Task = { id: number; type: string; status: string; detail: string; created_at: string };
type Dashboard = { total_videos: number; total_bytes: number; today_uploads: number; history: { date: string; count: number }[] };
type Section = "dashboard" | "merchants" | "orders" | "publish" | "videos" | "upload" | "tasks" | "users" | "client_projects";
type NavGroup = {title:string; items:{id:Section;label:string;icon:string;adminOnly?:boolean}[]};
const navGroups:NavGroup[]=[
  {title:"运营总览",items:[{id:"dashboard",label:"数据概览",icon:"▦"}]},
  {title:"订单与发布",items:[{id:"orders",label:"订单台账与收款",icon:"▤"},{id:"publish",label:"商家任务 · 上传成品",icon:"✓"}]},
  {title:"视频制作",items:[{id:"client_projects",label:"商家订单处理",icon:"◎"},{id:"videos",label:"视频素材库",icon:"▶"},{id:"upload",label:"上传视频",icon:"⇧"}]},
  {title:"商家协作",items:[{id:"merchants",label:"商家与账号",icon:"▣"}]},
  {title:"系统管理",items:[{id:"tasks",label:"上传记录",icon:"☷"},{id:"users",label:"员工账号",icon:"♙",adminOnly:true}]},
];
const menu=navGroups.flatMap(g=>g.items);
async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, { credentials: "include", ...options });
  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error(error.detail || `请求失败：${res.status}`);
  }
  return res.json();
}
const bytes = (n: number) => n >= 1024**3 ? (n/1024**3).toFixed(2)+" GB" : n >= 1024**2 ? (n/1024**2).toFixed(2)+" MB" : (n/1024).toFixed(1)+" KB";
const day = (date: string) => date ? new Date(date).toLocaleString("zh-CN") : "—";

export default function Home() {
  const [user, setUser] = useState<User|null>(null);
  const [checked, setChecked] = useState(false);
  const [section, setSection] = useState<Section>("dashboard");
  const [email, setEmail] = useState(""); const [password, setPassword] = useState("");
  const [error, setError] = useState(""); const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);
  const [dashboard, setDashboard] = useState<Dashboard|null>(null);
  const [videos, setVideos] = useState<Video[]>([]);
  const [totalVideos, setTotalVideos] = useState(0);
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [uploadFile, setUploadFile] = useState<File|null>(null);
  const [uploadToTask,setUploadToTask]=useState("");
  const [publishChoices,setPublishChoices]=useState<{id:number;title:string;order_no:string;status:string}[]>([]);
  const [newUser, setNewUser] = useState({ name: "", email: "", password: "", role: "viewer" });
  const [activeVideo, setActiveVideo] = useState<Video|null>(null);

  useEffect(() => { api<User>("/auth/me").then(setUser).catch(() => {}).finally(() => setChecked(true)); }, []);
  useEffect(() => {
    if (!user || user.role === "merchant") return;
    setError(""); setNotice("");
    if (section === "dashboard") api<Dashboard>("/dashboard").then(setDashboard).catch(e => setError(e.message));
    if (section === "videos") api<{items: Video[], total: number}>(`/videos?page=${page}&q=${encodeURIComponent(query)}`).then(r => {setVideos(r.items); setTotalVideos(r.total);}).catch(e => setError(e.message));
    if (section === "tasks") api<Task[]>("/tasks").then(setTasks).catch(e => setError(e.message));
    if (section === "upload") api<{id:number;title:string;order_no:string;status:string}[]>("/staff/publish-tasks").then(setPublishChoices).catch(e=>setError(e.message));
    if (section === "users" && user.role === "admin") api<User[]>("/users").then(setUsers).catch(e => setError(e.message));
  }, [user, section, page, query]);

  async function login(e: FormEvent) {
    e.preventDefault(); setLoading(true); setError("");
    try { const u = await api<User>("/auth/login", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({email,password}) }); setUser(u); setPassword(""); }
    catch (e) { setError((e as Error).message); } finally { setLoading(false); }
  }
  async function logout() { await api("/auth/logout", {method:"POST"}); setUser(null); setSection("dashboard"); }
  async function upload(e: FormEvent) {
    e.preventDefault(); if (!uploadFile) return;
    setLoading(true); setError(""); setNotice("");
    const body = new FormData(); body.append("file", uploadFile);
    try {
      const endpoint=uploadToTask?`/staff/publish-tasks/${uploadToTask}/upload`:"/videos";
      await api(endpoint,{method:"POST",body});
      setNotice(uploadToTask?`已上传到发布任务，商家可以审核：${uploadFile.name}`:`视频已存入素材库：${uploadFile.name}`);
      setUploadFile(null);
    }
    catch (e) { setError((e as Error).message); } finally { setLoading(false); }
  }
  async function remove(v: Video) {
    if (!confirm(`确定删除“${v.filename}”？此操作不可撤销。`)) return;
    try { await api(`/videos/${v.id}`, {method:"DELETE"}); setVideos(old => old.filter(x => x.id !== v.id)); setTotalVideos(n=>n-1); setNotice("已删除视频"); }
    catch(e) {setError((e as Error).message);}
  }
  async function addUser(e: FormEvent) {
    e.preventDefault(); setError("");
    try { await api("/users", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(newUser)}); setUsers(await api<User[]>("/users")); setNewUser({name:"",email:"",password:"",role:"viewer"}); setNotice("用户创建成功"); }
    catch(e) {setError((e as Error).message);}
  }

  if (!checked) return <div className="center">正在加载工作台…</div>;
  if (!user) return <main className="login-bg"><form className="login-card" onSubmit={login}>
    <img className="bm-login-logo" src="/brand-logo.png" alt="黑曼波猫咪 Logo" /><h1>黑曼波工作台</h1><p className="muted">视频拍摄 · 制作 · 剪辑 · 接单管理</p>
    <label>邮箱账号<input type="email" required placeholder="admin@example.com" value={email} onChange={e=>setEmail(e.target.value)}/></label>
    <label>登录密码<input type="password" required value={password} onChange={e=>setPassword(e.target.value)} /></label>
    {error && <div className="error">{error}</div>}<button className="primary full" disabled={loading}>{loading?"登录中…":"登录工作台"}</button>
    <p className="help">管理员与商家使用各自的账号登录，数据和页面权限互相隔离。</p>
  </form></main>;

  if (user.role === "merchant") return <MerchantPortalV14 name={user.name} onLogout={logout}/>;

  return <div className="shell">
    <aside className="sidebar"><div className="brand"><img className="bm-sidebar-logo" src="/brand-logo.png" alt="黑曼波 Logo" /><span>黑曼波工作台<small>视频与接单管理</small></span></div>
      <nav>{navGroups.map(g=><div key={g.title} className="nav-group"><div className="nav-group-title">{g.title}</div>{g.items.filter(m=>!m.adminOnly||user.role==="admin").map(m=><button key={m.id} onClick={()=>{setSection(m.id);setPage(1);setNotice("");}} className={section===m.id?"nav active":"nav"}><span>{m.icon}</span>{m.label}</button>)}</div>)}</nav>
      <div className="sidebar-foot">工作台 V1.4 · 商家审核成品<br/><small>数据与文件仅在你的服务器保存</small></div>
    </aside>
    <main className="main"><header className="topbar"><div><strong>{menu.find(m=>m.id===section)?.label}</strong><span className="muted"> / 黑曼波工作台</span></div><div className="user">{user.name} <span className="role">{user.role}</span> <button className="textbtn" onClick={logout}>退出</button></div></header>
      <div className="content">{error && <div className="error">{error}</div>}{notice && <div className="success">{notice}</div>}
        {section==="dashboard" && <><div className="heading"><h1>数据总览</h1><p>查看当前系统真实上传的视频统计</p></div><div className="metrics">
          {[{label:"视频总数",value:dashboard?.total_videos??"—"},{label:"今日上传",value:dashboard?.today_uploads??"—"},{label:"存储占用",value:dashboard?bytes(dashboard.total_bytes):"—"},{label:"管理权限",value:user.role==="admin"?"管理员":"普通用户"}].map(m=><div className="panel metric" key={m.label}><span className="muted">{m.label}</span><strong>{m.value}</strong></div>)}</div>
          <div className="panel"><h3>近七天上传趋势</h3><div className="bars">{(dashboard?.history||[]).map(h=><div className="barcol" key={h.date}><strong>{h.count}</strong><div className="bar" style={{height:`${Math.max(8,(h.count/Math.max(1,...(dashboard?.history.map(x=>x.count)||[1])))*145)}px`}}></div><small>{h.date.slice(5)}</small></div>)}</div></div>
          <OrdersSummary onOpen={()=>setSection("orders")}/><div className="panel"><h3>快速开始</h3><p className="muted">上传一个视频，即可在视频列表中预览，并更新数据总览。</p><button className="primary" onClick={()=>setSection("upload")}>开始上传视频</button></div>
        </>}
        {section==="merchants" && <MerchantsPanelV14 admin={user.role==="admin"}/>}
        {section==="publish" && <StaffPublishTasksV14 admin={user.role==="admin"}/>}
        {section==="orders" && <OrdersPanel user={user}/>}
        {section==="client_projects" && <StaffProjectsV13 admin={user.role==="admin"}/>}
        {section==="videos" && <><div className="heading"><h1>视频管理</h1><p>在线预览、搜索和管理已上传视频</p></div><div className="toolbar"><input placeholder="搜索视频文件名" value={query} onChange={e=>{setPage(1);setQuery(e.target.value);}}/><button className="primary" onClick={()=>setSection("upload")}>＋ 上传视频</button></div>
          <div className="panel tablewrap"><table><thead><tr><th>文件名称</th><th>大小</th><th>上传时间</th><th>状态</th><th>操作</th></tr></thead><tbody>{videos.map(v=><tr key={v.id}><td>{v.filename}</td><td>{bytes(v.size_bytes)}</td><td>{day(v.created_at)}</td><td><span className="status">已保存</span></td><td><button className="textbtn" onClick={()=>setActiveVideo(v)}>预览</button><button className="textbtn danger" onClick={()=>remove(v)}>删除</button></td></tr>)}{videos.length===0&&<tr><td colSpan={5} className="empty">暂无视频，先上传一个试试</td></tr>}</tbody></table></div>
          <div className="pager"><span>共 {totalVideos} 条</span><button disabled={page<=1} onClick={()=>setPage(p=>p-1)}>上一页</button><span>第 {page} 页</span><button disabled={page*20>=totalVideos} onClick={()=>setPage(p=>p+1)}>下一页</button></div>
        </>}
        {section==="upload" && <><div className="heading"><h1>上传制作视频</h1><p>可直接关联对应发布任务，商家登录后即可看到并审核；或仅保存到内部视频库。</p></div><form className="panel upload" onSubmit={upload}><div className="upload-icon">⇧</div><h3>选择制作好的视频</h3><label className="upload-destination">视频用途<select value={uploadToTask} onChange={e=>setUploadToTask(e.target.value)}><option value="">仅保存在内部素材库（商家不可见）</option>{publishChoices.filter(t=>t.status!=="published").map(t=><option value={t.id} key={t.id}>{t.order_no} · {t.title}（发布任务 #{t.id}）</option>)}</select></label><p className="muted">要让商家看到，必须选择已经关联订单和对应商家的发布任务。</p><input type="file" accept=".mp4,.mov,.webm,video/mp4,video/webm,video/quicktime" required onChange={e=>setUploadFile(e.target.files?.[0]||null)}/><button disabled={!uploadFile || loading || (!!uploadToTask && user.role!=="admin")} className="primary">{loading?"上传中…":uploadToTask?"上传并提交商家审核":"上传到视频库"}</button><small className="muted">单文件最大 100 MB。此版本不自动转码。</small></form></>}
        {section==="tasks" && <><div className="heading"><h1>任务中心</h1><p>查看最近 100 条上传任务记录</p></div><div className="panel tablewrap"><table><thead><tr><th>任务编号</th><th>类型</th><th>状态</th><th>详细信息</th><th>时间</th></tr></thead><tbody>{tasks.map(t=><tr key={t.id}><td>#{t.id}</td><td>{t.type}</td><td><span className="status">{t.status==="completed"?"已完成":t.status}</span></td><td>{t.detail}</td><td>{day(t.created_at)}</td></tr>)}{tasks.length===0&&<tr><td colSpan={5} className="empty">暂无任务记录</td></tr>}</tbody></table></div></>}
        {section==="users" && user.role==="admin" && <><div className="heading"><h1>用户管理</h1><p>仅管理员可以创建账号；不开放自行注册</p></div><div className="panel"><h3>新增用户</h3><form className="user-form" onSubmit={addUser}><input placeholder="姓名" required value={newUser.name} onChange={e=>setNewUser({...newUser,name:e.target.value})}/><input type="email" placeholder="邮箱" required value={newUser.email} onChange={e=>setNewUser({...newUser,email:e.target.value})}/><input type="password" minLength={12} placeholder="初始密码（至少12位）" required value={newUser.password} onChange={e=>setNewUser({...newUser,password:e.target.value})}/><select value={newUser.role} onChange={e=>setNewUser({...newUser,role:e.target.value})}><option value="viewer">普通用户</option><option value="admin">管理员</option></select><button className="primary">创建用户</button></form></div><div className="panel tablewrap"><table><thead><tr><th>姓名</th><th>邮箱</th><th>角色</th><th>创建时间</th></tr></thead><tbody>{users.map(u=><tr key={u.id}><td>{u.name}</td><td>{u.email}</td><td>{u.role}</td><td>{day(u.created_at)}</td></tr>)}</tbody></table></div></>}
      </div>
    </main>
    {activeVideo && <div className="modal-bg" onClick={()=>setActiveVideo(null)}><div className="modal" onClick={e=>e.stopPropagation()}><div className="modal-title"><strong>{activeVideo.filename}</strong><button onClick={()=>setActiveVideo(null)}>✕</button></div><video controls playsInline autoPlay src={activeVideo.stream_url} /><p className="muted">该视频需要使用支持对应编码的浏览器播放。</p></div></div>}
  </div>;
}
