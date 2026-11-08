import "../styles/management.css";
import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { listAdminUsers, createAdminUser, updateAdminUser } from "../api/admin.api";

const PERMISSIONS = [
  ["Xem và đăng ký khóa học đã publish", true, true, true],
  ["Học, làm checkpoint, dùng AI Tutor", true, false, false],
  ["Tạo và sửa khóa học", false, true, false],
  ["Tải video và duyệt học liệu AI", false, true, false],
  ["Xem báo cáo học viên của khóa mình", false, true, false],
  ["Tạo tài khoản giảng viên", false, false, true],
  ["Cấp quyền quản trị viên", false, false, true],
  ["Xem giám sát hệ thống", false, false, true],
];

export default function AdminUsersPage() {
  const location=useLocation();
  const navigate=useNavigate();
  const {userId}=useParams();
  const isRoles=location.pathname.endsWith("/roles");
  const isSuccess=location.pathname.endsWith("/success");
  const [users,setUsers]=useState([]);
  const [query,setQuery]=useState("");
  const [error,setError]=useState("");
  const [showForm,setShowForm]=useState(location.pathname.endsWith("/new")||Boolean(userId));
  const [confirmAdmin,setConfirmAdmin]=useState(false);
  const [created,setCreated]=useState(null);
  const editing=users.find(user=>String(user.id)===String(userId));
  const [form,setForm]=useState({name:"",email:"",role:"INSTRUCTOR",password:"",active:true});
  const [notice,setNotice]=useState("");
  useEffect(()=>{listAdminUsers().then(setUsers).catch(e=>setError(e.detail||e.message));},[]);
  useEffect(()=>{
    if(editing)setForm({name:editing.name,email:editing.email,role:editing.role,password:"",active:editing.status !== "INACTIVE"});
  },[editing?.id]);
  async function save(event, confirmedAdmin = false){
    event.preventDefault();
    try{
      if(editing) await updateAdminUser(editing.id,{name:form.name,email:form.email,role:form.role});
      else {
        if (form.role === "ADMIN" && !confirmedAdmin && !confirmAdmin) { setConfirmAdmin(true); return; }
        const account = await createAdminUser({name:form.name,email:form.email,role:form.role,password:form.password});
        setCreated({ ...form, ...account }); navigate("/admin/users/success", { replace: true, state: { account: { ...form, ...account } } }); return;
      }
      setUsers(await listAdminUsers());
      setShowForm(false);
      setNotice("Đã lưu thay đổi.");
    }catch(e){setError(e.detail||e.message);}
  }
  if (isSuccess) {
    const account = location.state?.account || created;
    return <div className="page management-page admin-success-page"><h1>Tạo tài khoản</h1><p className="management-subtitle">Dành cho giảng viên và quản trị viên.</p><section className="management-card success-card"><div className="success-icon">✓</div><h2>Đã tạo tài khoản</h2><p>Gửi thông tin đăng nhập cho người dùng.</p>{account && <div className="created-account"><div><span>Họ tên</span><strong>{account.name}</strong></div><div><span>Email</span><strong>{account.email}</strong></div><div><span>Vai trò</span><strong>{account.role === "ADMIN" ? "Quản trị viên" : "Giảng viên"}</strong></div><div><span>Mật khẩu tạm</span><strong>{account.password}</strong></div></div>}<div className="management-actions"><Link className="btn-secondary" to="/admin/users/new">Tạo tài khoản khác</Link><Link className="btn-primary" to="/admin/users">Về danh sách</Link></div></section></div>;
  }
  const filtered=users.filter(user=>`${user.name} ${user.email}`.toLowerCase().includes(query.toLowerCase()));
  if (editing && showForm) {
    return <div className="page management-page admin-edit-page">
      <div className="page-head">
        <div><div className="breadcrumb"><Link to="/admin/users">Tài khoản</Link> / {editing.name}</div><h1>Sửa tài khoản</h1><p className="management-subtitle">{editing.name}</p></div>
        <div className="page-actions"><Link className="btn-secondary" to="/admin/users">Hủy</Link><button className="btn-primary" form="admin-edit-form">☑ Lưu thay đổi</button></div>
      </div>
      {error && <p role="alert" className="management-alert">{error}</p>}
      {notice && <p role="status" className="management-notice">{notice}</p>}
      <div className="admin-edit-layout">
        <form id="admin-edit-form" className="management-form management-card" onSubmit={save}>
          <label>Họ và tên<input value={form.name} onChange={e=>setForm({...form,name:e.target.value})} required maxLength={255} /></label>
          <label>Email<div className="input-with-badge"><input type="email" value={form.email} readOnly /><span>Không đổi</span></div></label>
          <label>Vai trò<select value={form.role} onChange={e=>setForm({...form,role:e.target.value})}><option value="INSTRUCTOR">Giảng viên</option><option value="ADMIN">Quản trị viên</option></select></label>
          <label className="account-status-toggle"><span><strong>Trạng thái hoạt động</strong><small>Tắt để khóa tài khoản</small></span><input type="checkbox" checked={form.active} onChange={e=>setForm({...form,active:e.target.checked})} /></label>
        </form>
        <section className="management-card admin-other-actions"><h2>Thao tác khác</h2><button className="btn-secondary" type="button" onClick={()=>setNotice("Đặt lại mật khẩu chưa được kết nối với API quản trị.")}>↻ &nbsp;Đặt lại mật khẩu</button><button className="btn-danger-outline" type="button" onClick={()=>setNotice("Khóa tài khoản chưa được kết nối với API quản trị.")}>♙ &nbsp;Khóa tài khoản</button></section>
      </div>
    </div>;
  }
  return <div className="page management-page">
    <div className="page-head"><div><h1>{isRoles?"Vai trò và quyền":"Quản trị tài khoản"}</h1><p className="management-subtitle">{isRoles?"Kiểm tra quyền truy cập theo vai trò trong hệ thống.":"Tạo và chỉnh sửa tài khoản người dùng."}</p></div>{!isRoles&&!showForm&&<Link className="btn-primary" to="/admin/users/new">＋ Tạo tài khoản</Link>}</div>
    {error&&<p role="alert">{error}</p>}
    {isRoles?<div className="roles-layout"><section className="management-card permission-table"><div className="permission-head"><span>Quyền</span><span>Học viên</span><span>Giảng viên</span><span>Quản trị viên</span></div>{PERMISSIONS.map(([label,...values])=><div className="permission-row" key={label}><span>{label}</span>{values.map((allowed,index)=><span key={index} className={allowed?"permission-yes":"permission-no"}>{allowed?"✓":"—"}</span>)}</div>)}</section><section className="management-card role-guide"><h2>Cách cấp vai trò</h2>{[["Học viên","Họ tên, email, mật khẩu","Tự đăng ký","student"],["Giảng viên","Họ tên, email, mật khẩu, role INSTRUCTOR","Admin tạo","instructor"],["Quản trị viên","Họ tên, email, mật khẩu, role ADMIN","Admin cấp","admin"]].map(([title,detail,source,kind])=><div className="role-guide-row" key={title}><div><strong>{title}</strong><small>{detail}</small></div><span className={`role-pill ${kind}`}>• &nbsp;{source}</span></div>)}<p className="role-guide-note">ⓘ &nbsp; Vai trò cố định theo hệ thống, chỉ xem.</p></section></div>:<>
      <div className="management-toolbar"><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Tìm tài khoản..." /></div>
      {showForm&&<form className="management-form management-card" onSubmit={save}><h2>Tạo tài khoản</h2><label>Họ và tên<input value={form.name} onChange={e=>setForm({...form,name:e.target.value})} required /></label><label>Email<input type="email" value={form.email} onChange={e=>setForm({...form,email:e.target.value})} required /></label><label>Mật khẩu tạm<input type="text" value={form.password} onChange={e=>setForm({...form,password:e.target.value})} required minLength={8} /><small>Người dùng sẽ được yêu cầu đổi mật khẩu khi đăng nhập lần đầu.</small></label><label>Vai trò<select value={form.role} onChange={e=>setForm({...form,role:e.target.value})}><option value="INSTRUCTOR">Giảng viên</option><option value="ADMIN">Quản trị viên</option></select></label><div className="management-actions"><button className="btn-primary" type="submit">☑ Tạo tài khoản</button><Link className="btn-secondary" to="/admin/users">Hủy</Link></div></form>}
      {!showForm&&<div className="management-table-wrap"><table className="management-table"><thead><tr><th>Tài khoản</th><th>Email</th><th>Vai trò</th><th>Trạng thái</th><th></th></tr></thead><tbody>{filtered.map(user=><tr key={user.id}><td><strong>{user.name}</strong></td><td>{user.email}</td><td>{user.role==="STUDENT"?"Học viên":user.role==="INSTRUCTOR"?"Giảng viên":"Quản trị viên"}</td><td><span className="status-chip success">Hoạt động</span></td><td><Link className="management-link" to={`/admin/users/${user.id}/edit`}>Sửa</Link></td></tr>)}</tbody></table></div>}
    </>}
    {confirmAdmin&&<div className="workflow-modal-backdrop"><section className="workflow-modal" role="dialog" aria-modal="true"><h2>Cấp quyền Quản trị viên?</h2><p>Tài khoản này sẽ quản lý được mọi tài khoản, vai trò và giám sát hệ thống.</p><label className="confirm-check"><input type="checkbox" defaultChecked /> Tôi hiểu và muốn cấp quyền này</label><div className="management-actions"><button className="btn-secondary" onClick={()=>setConfirmAdmin(false)}>Hủy</button><button className="btn-primary" onClick={async()=>{setConfirmAdmin(false); await save({ preventDefault(){} }, true);}}>Xác nhận cấp quyền</button></div></section></div>}
  </div>;
}
