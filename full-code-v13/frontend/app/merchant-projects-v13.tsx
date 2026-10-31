"use client";
import {useCallback, useEffect, useState, type FormEvent} from "react";

type RequestItem = {id:number; merchant_id:number; title:string; brief:string; video_count:number;
  aspect_ratio:string;duration_seconds:number;desired_date:string|null;reference_url:string;
  status:string;staff_note:string;linked_order_id:number|null;created_at:string};
type Project = {id:number;order_no:string;title:string;service_type:string;status:string;
  order_date:string;due_date:string|null; amount_cents:number;paid_cents:number;
  outstanding_cents:number;stage:string;progress:number;client_note:string;accepted_at:string|null};
type Asset={id:string;filename:string;mime:string;kind:string;size_bytes:number;file_url:string;created_at:string};
type Revision={id:number;content:string;status:string;staff_reply:string;created_at:string;resolved_at:string|null};
type Detail=Project & {files:Asset[];revisions:Revision[];activity:{event:string;detail:string;created_at:string}[]};
const stageNames:Record<string,string>={planning:"策划排期",shooting:"拍摄中",producing:"制作中",editing:"剪辑/修改中",client_review:"客户验收",delivered:"已验收交付"};
const requestNames:Record<string,string>={pending:"待报价确认",accepted:"已转正式订单",rejected:"未接单"};
const yuan=(v:number)=>(v/100).toLocaleString("zh-CN",{style:"currency",currency:"CNY"});
const day=(s:string|null)=>s?.slice(0,10)||"—";
async function api<T>(path:string, init?:RequestInit):Promise<T>{
  const r=await fetch(`/api${path}`,{credentials:"include",cache:"no-store",...init});
  if(!r.ok){const err=await r.json().catch(()=>({}));throw Error(typeof err.detail==="string"?err.detail:`请求失败：HTTP ${r.status}`);}
  return r.json();
}
const json=(value:unknown):RequestInit=>({headers:{"Content-Type":"application/json"},body:JSON.stringify(value)});
const requestDefaults=()=>({title:"",brief:"",video_count:"5",aspect_ratio:"9:16",duration_seconds:"30",desired_date:"",reference_url:""});

function FileList({files}:{files:Asset[]}){
  return <div className="mp-file-grid">{files.map(f=><div className="mp-file" key={f.id}>
    <div><strong>{f.filename}</strong><small>{({material:"素材",draft:"预览稿",final:"最终成品"} as Record<string,string>)[f.kind]||f.kind} · {(f.size_bytes/1024/1024).toFixed(1)} MB</small></div>
    {f.mime.startsWith("video/")?<video controls preload="metadata" src={f.file_url} />:f.mime.startsWith("image/")?<img src={f.file_url} alt={f.filename}/>:null}
    <a href={f.file_url} target="_blank" rel="noopener noreferrer">查看 / 下载</a>
  </div>)}{!files.length&&<p className="muted">暂无文件</p>}</div>;
}

function UploadBox({endpoint,kind,onDone,disabled=false,label}:{endpoint:string;kind?:string;onDone:()=>Promise<void>;disabled?:boolean;label:string}){
  const [file,setFile]=useState<File|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState("");
  const upload=async(e:FormEvent)=>{e.preventDefault();if(!file)return;setBusy(true);setError("");try{
    if(file.size>100*1024*1024)throw Error("单文件不得超过 100 MB");
    const data=new FormData();data.append("file",file);if(kind)data.append("kind",kind);
    await api(endpoint,{method:"POST",body:data});setFile(null);await onDone();
  }catch(e){setError((e as Error).message);}finally{setBusy(false);}};
  return <form className="mp-upload" onSubmit={upload}>
    <label>{label}<input type="file" accept=".mp4,.mov,.webm,.jpg,.jpeg,.png,.pdf" disabled={disabled||busy} onChange={e=>setFile(e.target.files?.[0]||null)}/></label>
    <button className="secondary-btn" disabled={disabled||busy||!file}>{busy?"上传中…":"上传文件"}</button>
    {error&&<div className="error">{error}</div>}
  </form>;
}

export function MerchantProjectsV13({approved}:{approved:boolean}){
  const [requests,setRequests]=useState<RequestItem[]>([]),[projects,setProjects]=useState<Project[]>([]);
  const [form,setForm]=useState(requestDefaults()),[showForm,setShowForm]=useState(false);
  const [activeRequest,setActiveRequest]=useState<number|null>(null),[reqFiles,setReqFiles]=useState<Asset[]>([]);
  const [selected,setSelected]=useState<number|null>(null),[detail,setDetail]=useState<Detail|null>(null);
  const [revision,setRevision]=useState(""),[busy,setBusy]=useState(false),[error,setError]=useState(""),[message,setMessage]=useState("");
  const refresh=useCallback(async()=>{
    const [rs,ps]=await Promise.all([api<RequestItem[]>("/portal/project-requests"),api<Project[]>("/portal/projects")]);
    setRequests(rs);setProjects(ps);
  },[]);
  const refreshDetail=useCallback(async(id:number)=>{setDetail(await api<Detail>(`/portal/projects/${id}`));},[]);
  const refreshReqFiles=useCallback(async(id:number)=>{setReqFiles(await api<Asset[]>(`/portal/project-requests/${id}/files`));},[]);
  useEffect(()=>{refresh().catch(e=>setError(e.message));},[refresh]);
  const submit=async(e:FormEvent)=>{e.preventDefault();setBusy(true);setError("");try{
    await api("/portal/project-requests",{method:"POST",...json({...form,video_count:Number(form.video_count),duration_seconds:Number(form.duration_seconds),desired_date:form.desired_date||null})});
    setForm(requestDefaults());setShowForm(false);setMessage("需求已提交，等待黑曼波团队报价确认");await refresh();
  }catch(e){setError((e as Error).message);}finally{setBusy(false);}};
  const revise=async(e:FormEvent)=>{e.preventDefault();if(!selected)return;setBusy(true);setError("");try{
    await api(`/portal/projects/${selected}/revisions`,{method:"POST",...json({content:revision})});
    setRevision("");setMessage("修改意见已送达制作团队");await refreshDetail(selected);await refresh();
  }catch(e){setError((e as Error).message);}finally{setBusy(false);}};
  const accept=async()=>{if(!selected||!confirm("确认该项目成品符合要求并完成交付？确认后不可再提交修改意见。"))return;
    setBusy(true);setError("");try{await api(`/portal/projects/${selected}/accept`,{method:"POST"});setMessage("验收成功！");await refreshDetail(selected);await refresh();}
    catch(e){setError((e as Error).message);}finally{setBusy(false);}};
  return <section className="mp-root">
    <div className="mp-head"><div><h2>视频制作服务</h2><p className="muted">商家下单 · 上传素材 · 查看拍摄与剪辑进度 · 成品验收</p></div>
      <button className="primary" disabled={!approved} onClick={()=>setShowForm(!showForm)}>{showForm?"取消填写":"＋ 提交制作需求"}</button></div>
    {!approved&&<div className="merchant-alert">当前商家尚未审核通过，请先完成资料审核后再提交订单。</div>}
    {error&&<div className="error">{error}</div>}{message&&<div className="success">{message}</div>}
    <div className="mp-kpis">{[["待报价需求",requests.filter(x=>x.status==="pending").length],["制作中项目",projects.filter(x=>!(["delivered","cancelled"].includes(x.status))).length],["待我验收",projects.filter(x=>x.stage==="client_review").length]].map(([label,value])=><div className="panel" key={label}><span className="muted">{label}</span><strong>{value}</strong></div>)}</div>
    {showForm&&<form className="panel order-form" onSubmit={submit}>
      <label>项目名称 *<input required minLength={2} maxLength={200} value={form.title} onChange={e=>setForm({...form,title:e.target.value})} placeholder="例如：新品宣传短视频"/></label>
      <label>视频条数 *<input type="number" required min={1} max={1000} value={form.video_count} onChange={e=>setForm({...form,video_count:e.target.value})}/></label>
      <label>视频比例<select value={form.aspect_ratio} onChange={e=>setForm({...form,aspect_ratio:e.target.value})}><option>9:16</option><option>16:9</option><option>1:1</option><option>4:5</option></select></label>
      <label>单条时长（秒）<input type="number" min={5} max={3600} required value={form.duration_seconds} onChange={e=>setForm({...form,duration_seconds:e.target.value})}/></label>
      <label>希望交付日期<input type="date" value={form.desired_date} onChange={e=>setForm({...form,desired_date:e.target.value})}/></label>
      <label>参考链接<input maxLength={500} type="url" placeholder="https://..." value={form.reference_url} onChange={e=>setForm({...form,reference_url:e.target.value})}/></label>
      <label className="span2">拍摄、制作、剪辑需求 *<textarea required minLength={5} maxLength={3000} rows={4} value={form.brief} onChange={e=>setForm({...form,brief:e.target.value})} placeholder="拍摄场景、风格、用途、产品卖点、交付要求等"/></label>
      <div className="span2"><button className="primary" disabled={busy}>{busy?"提交中…":"提交需求（由工作人员报价确认）"}</button></div>
    </form>}
    <div className="panel"><h3>我的需求申请</h3><div className="mp-list">{requests.map(r=><div className="mp-list-item" key={r.id}>
      <div><b>{r.title}</b><small>需求 #{r.id} · {r.video_count} 条 · {r.aspect_ratio} · {day(r.created_at)}</small><small>{requestNames[r.status]||r.status}{r.staff_note?` · 工作人员回复：${r.staff_note}`:""}</small></div>
      <button className="secondary-btn" onClick={()=>{setActiveRequest(r.id);refreshReqFiles(r.id).catch(e=>setError(e.message));}}>素材管理</button>
      {r.linked_order_id !== null && (
  <button
    className="textbtn"
    onClick={() => {
      const orderId = r.linked_order_id;

      if (orderId === null) return;

      setSelected(orderId);

      refreshDetail(orderId).catch(e =>
        setError(e.message)
      );
    }}
  >
    查看正式订单
  </button>
)}
    </div>)}{!requests.length&&<p className="muted">暂无需求，可点击“提交制作需求”开始。</p>}</div>
      {activeRequest&&<div className="mp-subpanel"><div className="mp-head"><h3>需求 #{activeRequest} 的原始素材</h3><button className="textbtn" onClick={()=>setActiveRequest(null)}>收起</button></div>
        <UploadBox endpoint={`/portal/project-requests/${activeRequest}/files`} label="上传需求附件（单文件≤100 MB）" disabled={!approved||requests.find(r=>r.id===activeRequest)?.status==="rejected"} onDone={()=>refreshReqFiles(activeRequest)}/>
        <FileList files={reqFiles}/></div>}
    </div>
    <div className="panel"><h3>我的制作订单</h3><div className="mp-list">{projects.map(p=><div className="mp-list-item" key={p.id}>
      <div><b>{p.title}</b><small>{p.order_no} · {stageNames[p.stage]||p.stage} · {p.progress}%</small><small>订单金额 {yuan(p.amount_cents)} · 已收 {yuan(p.paid_cents)} · 待收 {yuan(p.outstanding_cents)}</small></div>
      <button className="secondary-btn" onClick={()=>{setSelected(p.id);refreshDetail(p.id).catch(e=>setError(e.message));}}>查看进度 / 验收</button>
    </div>)}{!projects.length&&<p className="muted">暂无正式制作订单。工作人员确认报价后会显示在这里。</p>}</div></div>
    {detail&&selected&&<div className="panel mp-detail"><div className="mp-head"><div><h3>{detail.title}</h3><p className="muted">{detail.order_no} · {stageNames[detail.stage]||detail.stage} · {detail.progress}%</p></div><button className="secondary-btn" onClick={()=>{setDetail(null);setSelected(null);}}>关闭</button></div>
      <div className="mp-progress"><div style={{width:`${detail.progress}%`}}/></div>
      {detail.client_note&&<p className="mp-note">制作团队留言：{detail.client_note}</p>}
      <p className="muted">交付日期：{day(detail.due_date)} · 已收款：{yuan(detail.paid_cents)} · 待收款：{yuan(detail.outstanding_cents)}</p>
      <h3>交付文件与素材</h3><FileList files={detail.files}/>
      <UploadBox endpoint={`/projects/${selected}/files`} kind="material" label="补充拍摄素材" disabled={!approved||["delivered","closed","cancelled"].includes(detail.status)} onDone={()=>refreshDetail(selected)}/>
      <h3>修改记录</h3>{detail.revisions.map(r=><p className="mp-note" key={r.id}>#{r.id} {r.status==="open"?"待处理":"已处理"}：{r.content}{r.staff_reply&&<><br/>工作人员回复：{r.staff_reply}</>}</p>)}
      {detail.stage==="client_review"&&approved&&!detail.accepted_at&&<div className="mp-review-actions"><form onSubmit={revise}><label>提出修改意见<textarea required minLength={3} maxLength={2000} rows={3} value={revision} onChange={e=>setRevision(e.target.value)} placeholder="请说明需要调整的画面、字幕或音乐位置"/></label><button disabled={busy} className="secondary-btn">提交修改意见</button></form>
        <button className="primary" disabled={busy||detail.revisions.some(r=>r.status==="open")} onClick={accept}>确认成品验收并交付</button></div>}
      {detail.accepted_at&&<div className="success">已于 {day(detail.accepted_at)} 确认验收</div>}
      <h3>处理记录</h3><div className="mp-timeline">{detail.activity.map((e,i)=><p key={i}><span>{day(e.created_at)}</span> {e.detail}</p>)}{!detail.activity.length&&<p className="muted">暂无处理记录</p>}</div>
    </div>}
  </section>;
}

export function StaffProjectsV13({admin}:{admin:boolean}){
  const [requests,setRequests]=useState<RequestItem[]>([]),[projects,setProjects]=useState<Project[]>([]),[detail,setDetail]=useState<Detail|null>(null);
  const [reqId,setReqId]=useState<number|null>(null),[reqFiles,setReqFiles]=useState<Asset[]>([]);
  const [amount,setAmount]=useState("0"),[cost,setCost]=useState("0"),[due,setDue]=useState(""),[staffNote,setStaffNote]=useState("");
  const [stage,setStage]=useState("planning"),[progress,setProgress]=useState("0"),[clientNote,setClientNote]=useState("");
  const [resolveText,setResolveText]=useState<Record<number,string>>({});
  const [error,setError]=useState(""),[msg,setMsg]=useState(""),[busy,setBusy]=useState(false);
  const refresh=useCallback(async()=>{const [r,p]=await Promise.all([api<RequestItem[]>("/staff/project-requests"),api<Project[]>("/staff/projects")]);setRequests(r);setProjects(p);},[]);
  const openProject=async(id:number)=>{const d=await api<Detail>(`/staff/projects/${id}`);setDetail(d);setStage(d.stage);setProgress(String(d.progress));setClientNote(d.client_note);};
  useEffect(()=>{refresh().catch(e=>setError(e.message));},[refresh]);
  const convert=async(id:number)=>{if(!confirm(`确认将需求 #${id} 转为正式订单？金额 ${amount} 元。`))return;setBusy(true);setError("");try{
    await api(`/staff/project-requests/${id}/convert`,{method:"POST",...json({amount,cost,due_date:due||null,staff_note:staffNote})});
    setReqId(null);setMsg("已创建正式订单，可在接单管理模块登记收款");await refresh();
  }catch(e){setError((e as Error).message);}finally{setBusy(false);}};
  const reject=async(id:number)=>{const reason=prompt("请输入不接单原因（至少3字）");if(!reason)return;setBusy(true);setError("");try{
    await api(`/staff/project-requests/${id}/reject`,{method:"POST",...json({reason})});setMsg("已回复商家");await refresh();
  }catch(e){setError((e as Error).message);}finally{setBusy(false);}};
  const saveStage=async(e:FormEvent)=>{e.preventDefault();if(!detail)return;setBusy(true);setError("");try{
    await api(`/staff/projects/${detail.id}/progress`,{method:"POST",...json({stage,progress:Number(progress),client_note:clientNote})});
    setMsg("客户可看到最新制作进度");await openProject(detail.id);await refresh();
  }catch(e){setError((e as Error).message);}finally{setBusy(false);}};
  const resolve=async(revisionId:number)=>{if(!detail)return;setBusy(true);setError("");try{
    await api(`/staff/projects/${detail.id}/revisions/${revisionId}/resolve`,{method:"POST",...json({reply:resolveText[revisionId]||""})});
    await openProject(detail.id);setMsg("修改意见已处理");
  }catch(e){setError((e as Error).message);}finally{setBusy(false);}};
  return <section className="mp-root"><div className="heading"><h1>商家订单需求与交付</h1><p>处理商家新需求、报价建单、制作进度、成品上传和修改验收</p></div>
    {error&&<div className="error">{error}</div>}{msg&&<div className="success">{msg}</div>}
    <div className="panel"><h3>待确认的商家需求</h3><div className="mp-list">{requests.map(r=><div className="mp-list-item" key={r.id}>
      <div><b>{r.title}</b><small>商家 #{r.merchant_id} · {r.video_count}条 · {r.aspect_ratio} · {r.duration_seconds}秒/条 · {day(r.desired_date)}期望交付</small><small>{requestNames[r.status]||r.status} · {r.brief}</small></div>
      <button className="secondary-btn" onClick={()=>{setReqId(r.id);api<Asset[]>(`/staff/project-requests/${r.id}/files`).then(setReqFiles).catch(e=>setError(e.message));}}>查看需求</button>
    </div>)}{!requests.length&&<p className="muted">暂无需求</p>}</div>
      {reqId&&(()=>{const r=requests.find(x=>x.id===reqId);return r?<div className="mp-subpanel"><div className="mp-head"><h3>需求详情：{r.title}</h3><button className="textbtn" onClick={()=>setReqId(null)}>收起</button></div>
        <p>{r.brief}</p>{r.reference_url&&<p>参考地址：<a href={r.reference_url} target="_blank" rel="noopener noreferrer">{r.reference_url}</a></p>}
        <FileList files={reqFiles}/>
        {admin&&r.status==="pending"&&<div className="mp-admin-form"><label>商定订单金额（元）<input type="number" min="0" step="0.01" value={amount} onChange={e=>setAmount(e.target.value)}/></label>
          <label>内部预估成本（元，仅内部）<input type="number" min="0" step="0.01" value={cost} onChange={e=>setCost(e.target.value)}/></label>
          <label>交付日期<input type="date" value={due} onChange={e=>setDue(e.target.value)}/></label>
          <label>报价说明<input maxLength={1000} value={staffNote} onChange={e=>setStaffNote(e.target.value)}/></label>
          <button disabled={busy} className="primary" onClick={()=>convert(r.id)}>确认报价并生成订单</button>
          <button disabled={busy} className="secondary-btn" onClick={()=>reject(r.id)}>拒绝需求</button>
        </div>}
      </div>:null;})()}
    </div>
    <div className="panel"><h3>在管视频制作项目</h3><div className="mp-list">{projects.map(p=><div className="mp-list-item" key={p.id}>
      <div><b>{p.title}</b><small>{p.order_no} · {stageNames[p.stage]||p.stage} · {p.progress}%</small><small>预计交付 {day(p.due_date)} · 已收 {yuan(p.paid_cents)} · 待收 {yuan(p.outstanding_cents)}</small></div>
      <button className="secondary-btn" onClick={()=>openProject(p.id).catch(e=>setError(e.message))}>处理项目</button>
    </div>)}{!projects.length&&<p className="muted">暂无已关联的商家订单</p>}</div></div>
    {detail&&<div className="panel mp-detail"><div className="mp-head"><div><h3>{detail.title}</h3><p className="muted">{detail.order_no}</p></div><button className="secondary-btn" onClick={()=>setDetail(null)}>关闭</button></div>
      {admin&&!detail.accepted_at&&detail.status!=="cancelled"&&<form className="mp-admin-form" onSubmit={saveStage}>
        <label>制作阶段<select value={stage} onChange={e=>setStage(e.target.value)}>{Object.entries(stageNames).filter(([k])=>k!=="delivered").map(([k,n])=><option key={k} value={k}>{n}</option>)}</select></label>
        <label>完成比例 %<input type="number" min="0" max="100" value={progress} onChange={e=>setProgress(e.target.value)}/></label>
        <label>对商家公开的进展说明<textarea maxLength={2000} rows={2} value={clientNote} onChange={e=>setClientNote(e.target.value)}/></label>
        <button className="primary" disabled={busy}>保存并同步给商家</button>
      </form>}
      {detail.accepted_at&&<div className="success">客户已于 {day(detail.accepted_at)} 确认验收</div>}
      <h3>文件管理</h3><FileList files={detail.files}/>
      {admin&&!detail.accepted_at&&!(["delivered","closed","cancelled"].includes(detail.status))&&<>
        <UploadBox label="上传试看视频（草稿）" endpoint={`/projects/${detail.id}/files`} kind="draft" onDone={()=>openProject(detail.id)}/>
        <UploadBox label="上传正式交付成品" endpoint={`/projects/${detail.id}/files`} kind="final" onDone={()=>openProject(detail.id)}/>
      </>}
      <h3>客户提出的修改意见</h3>{detail.revisions.map(r=><div className="mp-note" key={r.id}><b>#{r.id} {r.status==="open"?"待处理":"已处理"}</b><p>{r.content}</p>
        {r.staff_reply&&<p>回复：{r.staff_reply}</p>}{admin&&r.status==="open"&&<div className="mp-inline"><input maxLength={2000} value={resolveText[r.id]||""} onChange={e=>setResolveText({...resolveText,[r.id]:e.target.value})} placeholder="填写处理结果"/><button className="secondary-btn" disabled={busy||!(resolveText[r.id]||"").trim()} onClick={()=>resolve(r.id)}>标记已完成</button></div>}
      </div>)}{!detail.revisions.length&&<p className="muted">暂无修改意见</p>}
      <h3>项目处理记录</h3>{detail.activity.map((e,i)=><p className="mp-note" key={i}>{day(e.created_at)} · {e.detail}</p>)}
    </div>}
  </section>;
}
