import "../styles/management.css";
import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { listAdminUsers, createAdminUser, updateAdminUser } from "../api/admin.api";

export default function AdminUsersPage() {
  const location=useLocation();
  const {userId}=useParams();
  const isRoles=location.pathname.endsWith("/roles");
  const [users,setUsers]=useState([]);
  const [query,setQuery]=useState("");
  const [error,setError]=useState("");
  const [showForm,setShowForm]=useState(location.pathname.endsWith("/new")||Boolean(userId));
  const editing=users.find(user=>String(user.id)===String(userId));
  const [form,setForm]=useState({name:"",email:"",role:"STUDENT",password:""});
  useEffect(()=>{listAdminUsers().then(setUsers).catch(e=>setError(e.detail||e.message));},[]);
  useEffect(()=>{
    if(editing)setForm({name:editing.name,email:editing.email,role:editing.role,password:""});
  },[editing?.id]);
  async function save(event){
    event.preventDefault();
    try{
      if(editing) await updateAdminUser(editing.id,{name:form.name,email:form.email,role:form.role});
      else await createAdminUser({name:form.name,email:form.email,role:form.role,password:form.password});
      setUsers(await listAdminUsers());
      setShowForm(false);
    }catch(e){setError(e.detail||e.message);}
  }
  const filtered=users.filter(user=>`${user.name} ${user.email}`.toLowerCase().includes(query.toLowerCase()));
  return <div className="page management-page">
    <div className="page-head"><div><h1>{isRoles?"Vai trò và quyền":"Quản trị tài khoản"}</h1><p className="management-subtitle">{isRoles?"Kiểm tra quyền truy cập theo vai trò trong hệ thống.":"Tạo và chỉnh sửa tài khoản người dùng."}</p></div>{!isRoles&&!showForm&&<Link className="btn-primary" to="/admin/users/new">＋ Tạo tài khoản</Link>}</div>
    {error&&<p role="alert">{error}</p>}
    {isRoles?<div className="management-grid three">{["STUDENT","INSTRUCTOR","ADMIN"].map(role=><section className="management-card" key={role}><h2>{role==="STUDENT"?"Học viên":role==="INSTRUCTOR"?"Giảng viên":"Quản trị viên"}</h2><div className="review-row">{role==="STUDENT"?"Học, ôn tập, checkpoint":"Quản lý theo vai trò"}</div></section>)}</div>:<>
      <div className="management-toolbar"><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Tìm tài khoản..." /></div>
      {showForm&&<form className="management-form management-card" onSubmit={save}><h2>{editing?"Sửa tài khoản":"Tạo tài khoản"}</h2><label>Họ và tên<input value={form.name} onChange={e=>setForm({...form,name:e.target.value})} required /></label><label>Email<input type="email" value={form.email} onChange={e=>setForm({...form,email:e.target.value})} required /></label><label>Vai trò<select value={form.role} onChange={e=>setForm({...form,role:e.target.value})}><option value="STUDENT">Học viên</option><option value="INSTRUCTOR">Giảng viên</option><option value="ADMIN">Quản trị viên</option></select></label>{!editing&&<label>Mật khẩu<input type="password" value={form.password} onChange={e=>setForm({...form,password:e.target.value})} required minLength={8} /></label>}<div className="management-actions"><button className="btn-primary" type="submit">Lưu</button><button className="btn-secondary" type="button" onClick={()=>setShowForm(false)}>Hủy</button></div></form>}
      {!showForm&&<div className="management-table-wrap"><table className="management-table"><thead><tr><th>Tài khoản</th><th>Email</th><th>Vai trò</th><th>Trạng thái</th><th></th></tr></thead><tbody>{filtered.map(user=><tr key={user.id}><td><strong>{user.name}</strong></td><td>{user.email}</td><td>{user.role==="STUDENT"?"Học viên":user.role==="INSTRUCTOR"?"Giảng viên":"Quản trị viên"}</td><td><span className="status-chip success">Hoạt động</span></td><td><Link className="management-link" to={`/admin/users/${user.id}/edit`}>Sửa</Link></td></tr>)}</tbody></table></div>}
    </>}
  </div>;
}
