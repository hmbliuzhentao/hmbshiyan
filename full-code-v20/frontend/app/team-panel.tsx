"use client";

import {useCallback,useEffect,useState,type FormEvent} from "react";

type User={id:number;name:string;email:string;phone?:string;role:string;is_active?:boolean;created_at?:string};
const roleLabels:Record<string,string>={super_admin:"超级管理员",admin:"管理员",manager:"运营管理",producer:"视频制作",editor:"剪辑",viewer:"只读运营",merchant:"商家"};
type FormValues={name:string;email:string;password:string;role:string};
const empty=():FormValues=>({name:"",email:"",password:"",role:"producer"});

export default function TeamPanel({currentUser}:{currentUser:User}){
  const admin=["super_admin","admin"].includes(currentUser.role);
  const [members,setMembers]=useState<User[]>([]);
  const [loading,setLoading]=useState(false);
  const [saving,setSaving]=useState(false);
  const [error,setError]=useState("");
  const [message,setMessage]=useState("");
  const [showForm,setShowForm]=useState(false);
  const [form,setForm]=useState<FormValues>(empty());

  const load=useCallback(async()=>{
    if(!admin)return;
    setLoading(true);setError("");
    try{
      const response=await fetch("/api/users",{credentials:"include",cache:"no-store"});
      const data=await response.json().catch(()=>({}));
      if(!response.ok)throw Error(typeof data.detail==="string"?data.detail:`加载失败（${response.status}）`);
      setMembers((data as User[]).filter(u=>u.role!=="merchant"));
    }catch(e){setError((e as Error).message);}
    finally{setLoading(false);}
  },[admin]);

  useEffect(()=>{load();},[load]);

  async function create(e:FormEvent){
    e.preventDefault();
    if(!admin)return;
    setSaving(true);setError("");setMessage("");
    try{
      const response=await fetch("/api/users",{
        credentials:"include",method:"POST",
        headers:{"Content-Type":"application/json"},body:JSON.stringify(form)
      });
      const data=await response.json().catch(()=>({}));
      if(!response.ok)throw Error(typeof data.detail==="string"?data.detail:`创建失败（${response.status}）`);
      setForm(empty());setShowForm(false);setMessage("员工账号已创建，请通过安全渠道交付初始密码。");await load();
    }catch(e){setError((e as Error).message);}
    finally{setSaving(false);}
  }

  return <div className="v20-integrated">
    <div className="heading order-heading"><div><h1>团队与员工账号</h1><p>管理内部账号、角色和团队协作权限。商家账号请在「商家管理」维护。</p></div>
      {admin&&<button className="primary" onClick={()=>setShowForm(true)}>＋ 新增员工</button>}
    </div>
    {!admin?<div className="panel"><h3>团队目录</h3><p className="muted">为保护员工账号信息，团队成员目录仅管理员可查看。你可以使用「账号安全」修改自己的登录信息。</p></div>:
      <div className="panel">
        {error&&<div className="error" role="alert">{error}</div>}
        {message&&<div className="success">{message}</div>}
        <div className="toolbar"><h3>员工账户 · {members.length}</h3><button className="secondary-btn" onClick={()=>load()}>刷新</button></div>
        {loading?<div className="empty">正在加载员工列表…</div>:
          <div className="tablewrap"><table><thead><tr><th>姓名</th><th>邮箱</th><th>角色</th><th>状态</th></tr></thead><tbody>
            {members.map(m=><tr key={m.id}><td>{m.name}</td><td>{m.email}</td><td>{roleLabels[m.role]||m.role}</td><td><span className="merchant-status approved">{m.is_active===false?"已停用":"启用"}</span></td></tr>)}
            {!members.length&&<tr><td colSpan={4} className="empty">暂无员工账号</td></tr>}
          </tbody></table></div>}
        <p className="help">当前支持员工账号创建与列表查看；修改角色、停用和重置员工密码需后续管理接口支持。</p>
      </div>}
    {admin&&showForm&&<div className="modal-bg" onClick={()=>setShowForm(false)}><div className="modal order-modal" onClick={e=>e.stopPropagation()}>
      <div className="modal-title"><h3>创建员工账号</h3><button onClick={()=>setShowForm(false)}>关闭</button></div>
      <form className="order-form" onSubmit={create}>
        <label>员工姓名<input required maxLength={80} value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/></label>
        <label>员工邮箱<input type="email" required value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/></label>
        <label>员工角色<select value={form.role} onChange={e=>setForm({...form,role:e.target.value})}><option value="manager">运营管理</option><option value="producer">视频制作</option><option value="editor">剪辑</option><option value="viewer">只读运营</option><option value="admin">管理员</option></select></label>
        <label>初始密码<input type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={form.password} onChange={e=>setForm({...form,password:e.target.value})}/></label>
        <div className="order-modal-actions span2"><button type="button" className="secondary-btn" onClick={()=>setShowForm(false)}>取消</button><button className="primary" disabled={saving}>{saving?"创建中…":"创建员工"}</button></div>
      </form>
    </div></div>}
  </div>;
}
