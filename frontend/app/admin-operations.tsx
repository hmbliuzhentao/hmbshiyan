"use client";
import {useEffect,useState} from "react";

type Overview = {users:number;merchants:number;active_sessions:number};
type Work = {total:number;draft:number;assigned:number;in_progress:number;pending_review:number;changes_requested:number;approved:number;published:number};
type Target = "orders"|"publish"|"merchants"|"users"|"videos"|"system";
const quickActions: {title:string;detail:string;target:Target}[] = [
  {title:"处理订单",detail:"订单台账、收款、交付进度",target:"orders"},
  {title:"分配任务",detail:"拍摄剪辑接单与制作状态",target:"publish"},
  {title:"管理商家",detail:"新建商家、合作状态、资料",target:"merchants"},
  {title:"管理账号",detail:"创建管理员及员工、停用账号",target:"users"},
  {title:"管理视频",detail:"预览上传记录与视频文件",target:"videos"},
  {title:"操作审计",detail:"查看业务操作历史",target:"system"},
];
async function get<T>(path:string):Promise<T>{const r=await fetch(`/api${path}`,{credentials:"include",cache:"no-store"});if(!r.ok)throw Error(`读取失败 ${r.status}`);return r.json()}
export function AdminOperations({onNavigate}:{onNavigate:(target:Target)=>void}) {
  const [overview,setOverview]=useState<Overview|null>(null);
  const [work,setWork]=useState<Work|null>(null);
  useEffect(()=>{
    get<Overview>("/system/overview").then(setOverview).catch(()=>{});
    get<Work>("/staff/publish-tasks/summary").then(setWork).catch(()=>{});
  },[]);
  return <section className="admin-operations" aria-label="管理员总控制台">
    <div className="admin-ops-title"><div><h1>管理员总控制台</h1><p>所有账号、商家订单、任务分配和视频交付，统一从这里管理。</p></div><span className="admin-ops-tag">全站权限</span></div>
    <div className="admin-ops-metrics">
      <button onClick={()=>onNavigate("merchants")}><small>合作商家</small><strong>{overview?.merchants??"—"}</strong><span>查看商家</span></button>
      <button onClick={()=>onNavigate("users")}><small>全站账号</small><strong>{overview?.users??"—"}</strong><span>账号管理</span></button>
      <button onClick={()=>onNavigate("publish")}><small>待分配任务</small><strong>{work?.draft??"—"}</strong><span>立即分配</span></button>
      <button onClick={()=>onNavigate("publish")}><small>待审核视频</small><strong>{work?.pending_review??"—"}</strong><span>跟踪审核</span></button>
      <button onClick={()=>onNavigate("publish")}><small>退回修改</small><strong>{work?.changes_requested??"—"}</strong><span>处理修改</span></button>
    </div>
    <h3>常用管理入口</h3>
    <div className="admin-ops-actions">{quickActions.map(action=><button type="button" key={action.target} onClick={()=>onNavigate(action.target)}><strong>{action.title}</strong><small>{action.detail}</small><span>进入管理 →</span></button>)}</div>
  </section>
}
