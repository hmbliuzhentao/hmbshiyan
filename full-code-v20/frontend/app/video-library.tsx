"use client";

import {useCallback,useEffect,useState,type FormEvent} from "react";

type Video={id:string;filename:string;size_bytes:number;status:string;created_at:string;stream_url:string;created_by:number};
type Props={currentUser:{id:number;role:string}};
const sizeText=(n:number)=>n>=1024*1024?`${(n/1024/1024).toFixed(1)} MB`:`${(n/1024).toFixed(0)} KB`;

export default function VideoLibrary({currentUser}:Props){
  const [videos,setVideos]=useState<Video[]>([]);
  const [total,setTotal]=useState(0);
  const [page,setPage]=useState(1);
  const [q,setQ]=useState("");
  const [query,setQuery]=useState("");
  const [file,setFile]=useState<File|null>(null);
  const [active,setActive]=useState<Video|null>(null);
  const [busy,setBusy]=useState(false);
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");
  const pages=Math.max(1,Math.ceil(total/20));

  const load=useCallback(async()=>{
    setLoading(true);setError("");
    try{
      const params=new URLSearchParams({page:String(page),limit:"20"});
      if(query)params.set("q",query);
      const res=await fetch(`/api/videos?${params}`,{credentials:"include",cache:"no-store"});
      const data=await res.json().catch(()=>({}));
      if(!res.ok)throw Error(typeof data.detail==="string"?data.detail:`加载失败（${res.status}）`);
      setVideos(data.items||[]);setTotal(data.total||0);
    }catch(e){setError((e as Error).message);}
    finally{setLoading(false);}
  },[page,query]);

  useEffect(()=>{load();},[load]);

  async function upload(e:FormEvent){
    e.preventDefault();
    if(!file)return;
    if(file.size>100*1024*1024){setError("单个文件最大 100 MB");return;}
    const body=new FormData();body.append("file",file);
    setBusy(true);setError("");setNotice("");
    try{
      const res=await fetch("/api/videos",{method:"POST",body,credentials:"include"});
      const data=await res.json().catch(()=>({}));
      if(!res.ok)throw Error(typeof data.detail==="string"?data.detail:`上传失败（${res.status}）`);
      setFile(null);setNotice("视频已上传，可在制作任务中关联。");
      if(page!==1)setPage(1);else await load();
    }catch(e){setError((e as Error).message);}
    finally{setBusy(false);}
  }
  async function remove(v:Video){
    if(!window.confirm(`确定删除「${v.filename}」？已关联审核任务的视频不允许删除。`))return;
    setBusy(true);setError("");setNotice("");
    try{
      const res=await fetch(`/api/videos/${encodeURIComponent(v.id)}`,{method:"DELETE",credentials:"include"});
      const data=await res.json().catch(()=>({}));
      if(!res.ok)throw Error(typeof data.detail==="string"?data.detail:`删除失败（${res.status}）`);
      setActive(null);setNotice("视频文件已删除。");await load();
    }catch(e){setError((e as Error).message);}
    finally{setBusy(false);}
  }

  return <div className="v20-integrated">
    <div className="heading order-heading"><div><h1>视频素材库</h1><p>上传、筛选和预览视频；已绑定审核任务的视频受到保护。</p></div><button className="secondary-btn" onClick={()=>load()}>刷新</button></div>
    {error&&<div className="error" role="alert">{error}</div>}
    {notice&&<div className="success">{notice}</div>}
    <form className="panel bm-video-upload" onSubmit={upload}>
      <label><strong>上传视频</strong><input type="file" accept=".mp4,.mov,.webm,video/mp4,video/quicktime,video/webm" onChange={e=>setFile(e.target.files?.[0]||null)}/></label>
      <p className="help">支持 MP4、MOV、WebM，单文件最大 100 MB。文件保存在服务器 V2 视频卷中。</p>
      <button className="primary" disabled={!file||busy}>{busy?"上传中…":"上传到素材库"}</button>
    </form>
    <div className="panel">
      <form className="toolbar bm-ws-toolbar" onSubmit={e=>{e.preventDefault();setPage(1);setQuery(q.trim());}}>
        <input placeholder="搜索视频文件名" value={q} onChange={e=>setQ(e.target.value)}/>
        <button className="secondary-btn">搜索</button>
      </form>
      {loading?<div className="empty">正在读取视频…</div>:videos.length===0?<div className="empty">素材库暂无视频</div>:
      <div className="tablewrap"><table><thead><tr><th>视频文件</th><th>大小</th><th>上传时间</th><th>操作</th></tr></thead><tbody>{videos.map(v=><tr key={v.id}>
        <td><strong>{v.filename}</strong></td><td>{sizeText(v.size_bytes)}</td><td>{v.created_at?.slice(0,16).replace("T"," ")}</td>
        <td><button className="textbtn" onClick={()=>setActive(v)}>播放</button>
        {(["admin","super_admin"].includes(currentUser.role)||currentUser.id===v.created_by)&&<button className="textbtn danger" disabled={busy} onClick={()=>remove(v)}>删除</button>}</td>
      </tr>)}</tbody></table></div>}
      {total>20&&<div className="pager"><button disabled={page<=1} onClick={()=>setPage(p=>p-1)}>上一页</button><span>第 {page}/{pages} 页，共 {total} 条</span><button disabled={page>=pages} onClick={()=>setPage(p=>p+1)}>下一页</button></div>}
    </div>
    {active&&<div className="modal-bg" onClick={()=>setActive(null)}><div className="modal" onClick={e=>e.stopPropagation()}>
      <div className="modal-title"><strong>{active.filename}</strong><button onClick={()=>setActive(null)}>关闭</button></div>
      <video controls preload="metadata" src={active.stream_url}/>
      <p className="help">{sizeText(active.size_bytes)} · 视频流只对有权限的账号开放</p>
    </div></div>}
  </div>;
}
