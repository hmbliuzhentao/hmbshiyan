"use client";
import {useCallback, useEffect, useState, type FormEvent} from "react";
import "./publish-tasks-v14.css";

type TaskStatus = "draft" | "pending_review" | "changes_requested" | "approved" | "published";
type ReviewStatus = "pending_review" | "changes_requested" | "approved";
type TaskVideo = {id:number;video_id:string;filename:string;mime:string;size_bytes:number;review_status:ReviewStatus;review_note:string;reviewed_at:string|null;url:string};
type PublishTask = {id:number;order_id:number;order_no:string;order_title:string;title:string;platform:string;account_label:string;
  publish_date:string|null;instructions:string;status:TaskStatus;published_url:string;merchant_name?:string;videos:TaskVideo[]};
type OrderItem = {id:number;merchant_id:number|null;order_no:string;title:string;client_name:string;status:string};
type LibraryVideo = {id:string;filename:string;created_at:string};
type Summary = {total:number;pending_review:number;changes_requested:number;approved:number;published:number};
const statusNames:Record<TaskStatus,string>={draft:"等待上传成品",pending_review:"待商家审核",changes_requested:"退回修改",approved:"商家已通过",published:"已发布"};
const reviewNames:Record<ReviewStatus,string>={pending_review:"待审核",changes_requested:"需修改",approved:"已通过"};
const fmt=(value:string|null)=>value||"未设置";
async function api<T>(path:string, init?:RequestInit):Promise<T>{
  const r=await fetch(`/api${path}`,{credentials:"include",cache:"no-store",...init});
  if(!r.ok){const err=await r.json().catch(()=>null);throw new Error(typeof err?.detail==="string"?err.detail:`请求失败：${r.status}`);}
  return r.json();
}
const json=(body:unknown):RequestInit=>({headers:{"Content-Type":"application/json"},body:JSON.stringify(body),method:"POST"});
function Pill({status}:{status:TaskStatus}){return <span className={`pub-pill ${status}`}>{statusNames[status]||status}</span>}

export function StaffPublishTasksV14({admin}:{admin:boolean}){
  const [tasks,setTasks]=useState<PublishTask[]>([]),[selected,setSelected]=useState<number|null>(null);
  const [summary,setSummary]=useState<Summary|null>(null);
  const [videos,setVideos]=useState<LibraryVideo[]>([]),[libVideo,setLibVideo]=useState("");
  const [upload,setUpload]=useState<File|null>(null),[replacement,setReplacement]=useState<Record<number,File|null>>({});
  const [history,setHistory]=useState<{decision:string;note:string;filename:string;reviewer:string;created_at:string}[]>([]);
  const [error,setError]=useState(""),[ok,setOk]=useState(""),[busy,setBusy]=useState(false);
  const refresh=useCallback(async()=>{
    const [ts,s]=await Promise.all([api<PublishTask[]>("/staff/publish-tasks"),api<Summary>("/staff/publish-tasks/summary")]);
    setTasks(ts);setSummary(s);
  },[]);
  useEffect(()=>{refresh().catch(e=>setError(e.message));api<{items:LibraryVideo[]}>("/videos?limit=50").then(r=>setVideos(r.items)).catch(()=>{});},[refresh]);
  useEffect(()=>{if(selected!==null)api<{decision:string;note:string;filename:string;reviewer:string;created_at:string}[]>(`/staff/publish-tasks/${selected}/review-history`).then(setHistory).catch(()=>setHistory([]));},[selected,tasks]);
  const active=tasks.find(t=>t.id===selected)||null;
  const run=async(fn:()=>Promise<unknown>,message:string)=>{setBusy(true);setError("");setOk("");try{await fn();await refresh();setOk(message);}catch(e){setError((e as Error).message);}finally{setBusy(false);}};
  const uploadFile=async(e:FormEvent)=>{e.preventDefault();if(!active||!upload)return;
    await run(async()=>{const data=new FormData();data.append("file",upload);await api(`/staff/publish-tasks/${active.id}/upload`,{method:"POST",body:data});setUpload(null);},"视频已提交给对应商家审核");};
  const attachFile=async()=>{if(!active||!libVideo)return;await run(async()=>{await api(`/staff/publish-tasks/${active.id}/videos`,json({video_id:libVideo}));setLibVideo("");},"视频库成品已关联到发布任务");};
  const replaceFile=async(linkId:number)=>{if(!active||!replacement[linkId])return;await run(async()=>{
    const data=new FormData();data.append("file",replacement[linkId]!);
    await api(`/staff/publish-tasks/${active.id}/videos/${linkId}/replace`,{method:"POST",body:data});
    setReplacement(x=>({...x,[linkId]:null}));},"新版视频已提交，等待商家重新审核");};
  return <div className="pub-root">
    <div className="heading"><h1>商家发布任务 · 视频交付</h1><p>商家发起订单和发布任务 → 内部上传成品 → 商家审核并登记发布。只有对应商家能看到视频。</p></div>
    {error&&<div className="error">{error}</div>}{ok&&<div className="success">{ok}</div>}
    <div className="pub-metrics">
      {([{label:"总任务",value:summary?.total},{label:"待商家审核",value:summary?.pending_review},{label:"退回修改",value:summary?.changes_requested},{label:"已审核通过",value:summary?.approved},{label:"已发布",value:summary?.published}]).map(m=><div key={m.label} className="panel"><small>{m.label}</small><strong>{m.value??"—"}</strong></div>)}
    </div>
    <div className="panel"><p className="muted">订单和发布任务均由商家工作台发起。内部负责确认报价、上传制作成品和跟进审核意见，不代商家发布任务。</p></div>
    <div className="pub-columns"><div className="panel"><h3>发布任务列表</h3><div className="pub-task-list">
      {tasks.map(t=><button type="button" key={t.id} onClick={()=>{setSelected(t.id);setOk("");}} className={`pub-task ${selected===t.id?"selected":""}`}>
        <strong>#{t.id} {t.title}</strong><small>{t.order_no} · {t.merchant_name}</small><span><Pill status={t.status}/>　{t.videos.length} 个视频</span>
      </button>)}{!tasks.length&&<p className="muted">暂无发布任务，等待商家在商家工作台发布。</p>}
    </div></div>
    <div className="panel pub-detail">{active?<>
      <h3>{active.title} <Pill status={active.status}/></h3>
      <p className="muted">{active.order_no} · {active.merchant_name} · {active.platform} {active.account_label&&`· ${active.account_label}`} · {fmt(active.publish_date)}</p>
      {active.instructions&&<p className="pub-note">任务说明：{active.instructions}</p>}
      {admin&&active.status!=="published"&&<><form className="pub-file-form" onSubmit={uploadFile}>
        <h4>上传制作完成的视频（直接提交商家审核）</h4>
        <input type="file" accept="video/mp4,video/quicktime,video/webm,.mp4,.mov,.webm" onChange={e=>setUpload(e.target.files?.[0]||null)} />
        <button className="primary" disabled={!upload||busy}>上传到任务</button><small>单文件 ≤100 MB。上传后只有关联商家可预览。</small>
      </form><div className="pub-library"><h4>或者关联视频库已有成品</h4><select value={libVideo} onChange={e=>setLibVideo(e.target.value)}><option value="">选择视频</option>{videos.map(v=><option value={v.id} key={v.id}>{v.filename}</option>)}</select><button className="secondary-btn" disabled={!libVideo||busy} onClick={attachFile}>关联到任务</button></div></>}
      <h4>本任务视频与审核结果</h4>{active.videos.map(v=><div className="pub-video" key={v.id}><div className="pub-video-head"><strong>{v.filename}</strong><span className={`pub-review ${v.review_status}`}>{reviewNames[v.review_status]}</span></div>
        <video controls playsInline preload="metadata" src={v.url}/>{v.review_note&&<p className="pub-note">商家意见：{v.review_note}</p>}
        {admin&&active.status!=="published"&&<div className="pub-replace"><label>上传修改后新版本<input type="file" accept="video/*" onChange={e=>setReplacement(x=>({...x,[v.id]:e.target.files?.[0]||null}))}/></label><button className="secondary-btn" disabled={!replacement[v.id]||busy} onClick={()=>replaceFile(v.id)}>提交新版重新审核</button></div>}
      </div>)}{!active.videos.length&&<p className="muted">还未上传视频；商家暂时看不到该任务。</p>}
      {active.status==="approved"&&<p className="success">商家已审核通过，等待商家登记实际发布链接。</p>}
      {active.status==="published"&&<p className="success">已发布{active.published_url&&<>：<a target="_blank" rel="noopener noreferrer" href={active.published_url}>查看视频链接</a></>}</p>}
      <details className="pub-history"><summary>查看商家审核历史（{history.length}）</summary>{history.map((h,i)=><p key={i}><strong>{h.filename}</strong> · {h.decision==="approved"?"通过":"退回修改"} · {h.reviewer} · {h.created_at?.slice(0,19).replace("T"," ")}{h.note&&<> · {h.note}</>}</p>)}</details>
    </>:<p className="muted">选择左侧任务查看视频、审核意见和发布状态。</p>}</div></div>
  </div>;
}

export function MerchantPublishTasksV14(){
  const [tasks,setTasks]=useState<PublishTask[]>([]),[error,setError]=useState(""),[message,setMessage]=useState(""),[busy,setBusy]=useState(false),[notes,setNotes]=useState<Record<number,string>>({});
  const [orders,setOrders]=useState<OrderItem[]>([]);
  const [newTask,setNewTask]=useState({order_id:"",title:"",platform:"TikTok",account_label:"",publish_date:"",instructions:""});
  const [publishLinks,setPublishLinks]=useState<Record<number,string>>({});
  const refresh=useCallback(async()=>setTasks(await api<PublishTask[]>("/portal/publish-tasks")),[]);
  useEffect(()=>{refresh().catch(e=>setError(e.message));api<OrderItem[]>("/portal/orders").then(setOrders).catch(e=>setError(e.message));},[refresh]);
  const createTask=async(e:FormEvent)=>{e.preventDefault();setBusy(true);setError("");setMessage("");try{
    await api("/portal/publish-tasks",json({...newTask,order_id:Number(newTask.order_id),publish_date:newTask.publish_date||null}));
    setNewTask({order_id:"",title:"",platform:"TikTok",account_label:"",publish_date:"",instructions:""});
    await refresh();setMessage("发布任务已提交给制作团队，待他们上传视频后即可审核");
  }catch(e){setError((e as Error).message);}finally{setBusy(false);}};
  const markPublished=async(taskId:number)=>{setBusy(true);setError("");setMessage("");try{
    await api(`/portal/publish-tasks/${taskId}/published`,json({published_url:publishLinks[taskId]||""}));
    await refresh();setMessage("发布完成情况已保存");
  }catch(e){setError((e as Error).message);}finally{setBusy(false);}};
  const review=async(taskId:number,linkId:number,decision:"approved"|"changes_requested")=>{setBusy(true);setError("");setMessage("");try{
    await api(`/portal/publish-tasks/${taskId}/videos/${linkId}/review`,json({decision,note:notes[linkId]||""}));
    await refresh();setMessage(decision==="approved"?"审核已通过，制作团队已收到结果":"修改意见已提交，等待制作团队上传新版视频");
  }catch(e){setError((e as Error).message);}finally{setBusy(false);}};
  const pending=tasks.filter(t=>t.videos.some(v=>v.review_status==="pending_review")).length;
  return <div className="pub-root"><div className="heading"><h1>发布任务与视频审核</h1><p>你可为已确认的制作订单发布任务，随后审核黑曼波团队交付的视频；内部不会替你发起发布任务。</p></div>
    {error&&<div className="error">{error}</div>}{message&&<div className="success">{message}</div>}
    <div className="panel pub-create"><h3>＋ 发布视频任务</h3>
      <form className="pub-grid" onSubmit={createTask}>
        <label className="pub-wide">关联我的正式订单
          <select required value={newTask.order_id} onChange={e=>setNewTask({...newTask,order_id:e.target.value})}>
            <option value="">请选择已确认订单</option>
            {orders.filter(o=>o.status!=="cancelled").map(o=><option value={o.id} key={o.id}>{o.order_no} · {o.title}</option>)}
          </select><small>还没有正式订单？先到「发布订单」提交制作需求，等待报价确认后即可选择。</small>
        </label>
        <label>任务名称<input minLength={2} required maxLength={200} value={newTask.title} onChange={e=>setNewTask({...newTask,title:e.target.value})}/></label>
        <label>发布平台<select value={newTask.platform} onChange={e=>setNewTask({...newTask,platform:e.target.value})}><option>TikTok</option><option>Instagram</option><option>YouTube</option><option>其他</option></select></label>
        <label>发布账号备注<input maxLength={120} value={newTask.account_label} onChange={e=>setNewTask({...newTask,account_label:e.target.value})}/></label>
        <label>计划发布日期<input type="date" value={newTask.publish_date} onChange={e=>setNewTask({...newTask,publish_date:e.target.value})}/></label>
        <label className="pub-wide">制作/发布要求<textarea rows={3} maxLength={3000} value={newTask.instructions} onChange={e=>setNewTask({...newTask,instructions:e.target.value})}/></label>
        <button className="primary" disabled={busy||!orders.some(o=>o.status!=="cancelled")}>发布任务</button>
      </form>
    </div>
    <div className="pub-merchant-summary panel"><strong>{pending}</strong><span>个任务有视频等待你审核</span></div>
    {tasks.map(t=><section key={t.id} className="panel pub-merchant-task">
      <div className="pub-video-head"><div><h3>#{t.id} {t.title}</h3><p className="muted">订单 {t.order_no} · {t.platform} · {fmt(t.publish_date)} · {t.account_label}</p></div><Pill status={t.status}/></div>
      {t.instructions&&<p className="pub-note">发布要求：{t.instructions}</p>}
      {t.videos.map(v=><div className="pub-video" key={v.id}><div className="pub-video-head"><strong>{v.filename}</strong><span className={`pub-review ${v.review_status}`}>{reviewNames[v.review_status]}</span></div>
        <video controls playsInline preload="metadata" src={v.url}/>
        {v.review_note&&<p className="pub-note">已提交意见：{v.review_note}</p>}
        {v.review_status==="pending_review"&&<div className="pub-review-form"><textarea rows={2} maxLength={2000} placeholder="如果需要修改，请说明具体画面、时长、产品卖点等（退回时必填）" value={notes[v.id]||""} onChange={e=>setNotes({...notes,[v.id]:e.target.value})}/><div><button className="primary" disabled={busy} onClick={()=>review(t.id,v.id,"approved")}>审核通过</button><button className="secondary-btn" disabled={busy||(notes[v.id]||"").trim().length<3} onClick={()=>review(t.id,v.id,"changes_requested")}>退回修改</button></div></div>}
      </div>)}
      {t.status==="draft"&&<p className="muted">任务已发布给黑曼波团队，等待制作视频上传。</p>}
      {t.status==="approved"&&<div className="pub-publish"><h4>全部视频审核通过 · 登记实际发布</h4>
        <input type="url" placeholder="已发布视频链接（选填）" maxLength={500} value={publishLinks[t.id]||""} onChange={e=>setPublishLinks(x=>({...x,[t.id]:e.target.value}))}/>
        <button className="primary" disabled={busy} onClick={()=>markPublished(t.id)}>确认已发布</button>
      </div>}
      {t.status==="published"&&<p className="success">已登记发布{t.published_url&&<> · <a href={t.published_url} target="_blank" rel="noopener noreferrer">查看视频链接</a></>}</p>}
    </section>)}{!tasks.length&&<div className="panel"><p className="muted">暂无发布任务。请选择已确认的订单并点击「发布任务」。</p></div>}
  </div>;
}
