"""Server-rendered TOFAN manager dashboard."""

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from app.auth.authorization import require_owner_or_admin

router = APIRouter(prefix="/manager", tags=["main-manager-ui"])


@router.get("/dashboard-ui", response_class=HTMLResponse, include_in_schema=False)
def dashboard_ui(_: list = Depends(require_owner_or_admin)) -> str:
    return r"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TOFAN Manager Dashboard</title>
<style>
:root{--bg:#090909;--panel:#121212;--line:#272727;--text:#f4f4f4;--muted:#9a9a9a;--gold:#d4af37;--danger:#d9534f;--ok:#35b56a}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
header{padding:22px 5%;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center}
.brand{font-weight:800;font-size:22px}.brand span{color:var(--gold)}button{background:var(--gold);border:0;padding:10px 16px;border-radius:8px;font-weight:700;cursor:pointer}
main{padding:28px 5%;max-width:1500px;margin:auto}.sub{color:var(--muted);margin-top:5px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin:24px 0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px}.label{color:var(--muted);font-size:13px}.num{font-size:30px;font-weight:800;margin-top:7px;color:var(--gold)}
section{margin-top:25px}.section-title{font-size:18px;font-weight:800;margin-bottom:10px}
.table-wrap{overflow:auto;background:var(--panel);border:1px solid var(--line);border-radius:12px}.modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.78);z-index:20;padding:24px;overflow:auto}.modal.open{display:block}.modal-card{max-width:1100px;margin:30px auto;background:#111;border:1px solid var(--gold);border-radius:14px;padding:22px}.modal-head{display:flex;justify-content:space-between;align-items:center;gap:12px}.modal-close{background:#222;color:#fff}.detail-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin:15px 0}.detail{background:#181818;border:1px solid var(--line);padding:12px;border-radius:9px}.detail b{display:block;color:var(--muted);font-size:12px;margin-bottom:4px}
table{width:100%;border-collapse:collapse;min-width:800px}th,td{padding:12px;border-bottom:1px solid var(--line);text-align:right;font-size:13px}th{color:var(--gold)}
.badge{padding:4px 8px;border-radius:999px;background:#242424}.ok{color:var(--ok)}.fail{color:var(--danger)}
#state{color:var(--muted);font-size:13px}
</style>
</head>
<body>
<header><div class="brand">TOFAN <span>SMART ACADEMY</span> · Manager</div><button onclick="load()">تحديث</button></header>
<main>
<h1>لوحة المدير العام</h1><div class="sub">مركز التحكم التشغيلي للأكاديمية</div><div id="state">جاري تحميل البيانات...</div>
<div id="cards" class="grid"></div>

<section><div class="section-title">إدارة المدرسين</div>
<div class="table-wrap"><div style="padding:14px;display:flex;gap:10px;flex-wrap:wrap;align-items:center">
<select id="courseSelect" style="padding:10px;border-radius:8px;background:#181818;color:#fff;border:1px solid #333;min-width:280px"></select>
<button onclick="provisionTeacher()">إنشاء مدرس للمقرر</button></div>
<div id="teachers"></div></div></section>

<section><div class="section-title">الطلاب</div><div style="padding:14px;display:flex;gap:10px;flex-wrap:wrap"><input id="studentSearch" placeholder="ابحث بالاسم أو البريد أو الهاتف" style="flex:1;min-width:240px;padding:10px;border-radius:8px;background:#181818;color:#fff;border:1px solid #333"><button onclick="loadStudents()">بحث</button></div><div id="students" class="table-wrap"></div></section><div id="studentModal" class="modal" onclick="if(event.target===this)closeStudent()"><div class="modal-card"><div class="modal-head"><div><h2 id="studentTitle">تفاصيل الطالب</h2><div id="studentState" class="sub">—</div></div><button class="modal-close" onclick="closeStudent()">إغلاق</button></div><div id="studentDetails"></div></div></div>
<section><div class="section-title">الاختبارات</div><div id="assessments" class="table-wrap"></div></section>
<section><div class="section-title">إعداد نقطة الدفع</div>
<div class="detail-grid" style="padding:14px">
<div class="detail"><b>مزود الدفع</b><input id="payProvider" style="width:100%;padding:9px"></div>
<div class="detail"><b>اسم صاحب الحساب</b><input id="payAccountName" style="width:100%;padding:9px"></div>
<div class="detail"><b>رقم النقطة / الحساب</b><input id="payAccountNumber" style="width:100%;padding:9px"></div>
<div class="detail"><b>المبلغ</b><input id="payAmount" type="number" min="0" step="0.01" style="width:100%;padding:9px"></div>
<div class="detail"><b>العملة</b><input id="payCurrency" style="width:100%;padding:9px"></div>
<div class="detail"><b>التعليمات</b><textarea id="payInstructions" style="width:100%;padding:9px"></textarea></div>
</div><div style="padding:0 14px 14px"><button onclick="savePaymentAccount()">حفظ إعدادات الدفع</button><span id="payAccountState" class="sub" style="margin-right:10px"></span></div></section>
<section><div class="section-title">المدفوعات</div><div id="payments" class="table-wrap"></div></section>
<section><div class="section-title">آخر أحداث التدقيق</div><div id="audit" class="table-wrap"></div></section>
</main>
<script>
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[c]));
const cell=v=>String(v??"").startsWith("__HTML__") ? "<td>"+String(v).slice(8)+"</td>" : "<td>"+esc(v)+"</td>";
function table(headers,rows){return '<table><thead><tr>'+headers.map(h=>'<th>'+esc(h)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+r.map(cell).join('')+'</tr>').join('')+'</tbody></table>'}
async function get(path){const r=await fetch(path,{credentials:"same-origin"});if(!r.ok)throw new Error("HTTP "+r.status);return r.json()}
async function load(){
 document.getElementById("state").textContent="جاري التحديث...";
 try{const a=await get("/student/payments/account"); if(a.configured){payProvider.value=a.provider_name||"";payAccountName.value=a.account_name||"";payAccountNumber.value=a.account_number||"";payAmount.value=a.amount??"";payCurrency.value=a.currency||"";payInstructions.value=a.instructions||"";}}catch{}
 try{
  const studentQuery=encodeURIComponent(document.getElementById("studentSearch")?.value||"");
  const [d,a,p,l,t,s,c]=await Promise.all([
   get("/manager/dashboard"),get("/manager/assessments?limit=10"),get("/manager/payments?limit=10"),
   get("/manager/audit-log?limit=10"),get("/manager/teachers"),get("/manager/students?limit=10&query="+studentQuery),get("/manager/courses")
  ]);
  const cards=[
   ["المستخدمون",d.users.total],["طلاب الجامعات",d.users.university_students],["المتعلمون المستقلون",d.users.independent_learners],
   ["المدرسون النشطون",d.teachers.active],["المقررات",d.curriculum.active_courses],["الدروس",d.curriculum.lessons],
   ["محاولات الاختبار",d.assessments.attempts],["ناجح",d.assessments.passed],["مدفوعات معلقة",d.payments.pending],["مدفوعات مؤكدة",d.payments.confirmed]
  ];
  document.getElementById("cards").innerHTML=cards.map(x=>'<div class="card"><div class="label">'+x[0]+'</div><div class="num">'+x[1]+'</div></div>').join("");
  document.getElementById("courseSelect").innerHTML='<option value="">اختر مقررًا</option>'+c.courses.map(x=>'<option value="'+esc(x.course_id)+'">'+esc(x.code+" — "+x.name)+'</option>').join("");
  document.getElementById("teachers").innerHTML=table(["المدرس","المقرر","الحالة","إجراء"],t.teachers.map(x=>[x.name,x.curriculum_course_id||"-",x.status,`__HTML__<button onclick="changeStatus('${x.agent_id}','${x.status==="active"?"paused":"active"}')">${x.status==="active"?"إيقاف مؤقت":"تفعيل"}</button>`]));
  document.getElementById("students").innerHTML=table(["الاسم","النوع","الحالة","التحقق","التاريخ","إجراء"],s.students.map(x=>[x.name,x.user_type,x.profile_status,x.biometric_verified?"نعم":"لا",x.updated_at,"__HTML__<button onclick="viewStudent('"+x.user_id+"')">عرض</button>"]));
  document.getElementById("assessments").innerHTML=table(["الطالب","النسبة","النتيجة","الحالة","التاريخ"],a.assessments.map(x=>[x.user_id,x.percentage??"-",x.passed===true?"ناجح":x.passed===false?"غير ناجح":"-",x.status,x.submitted_at||x.started_at]));
  document.getElementById("payments").innerHTML=table(["المعاملة","الطالب","المنتج","الحالة","المبلغ","إجراء"],p.payments.map(x=>[x.transaction_id,x.user_id,x.product_key,x.status,(x.amount??"-")+" "+(x.currency??""),x.status==="pending" ? `__HTML__<button onclick="confirmPayment('${x.transaction_id}')">تأكيد</button> <button onclick="rejectPayment('${x.transaction_id}')">رفض</button>` : "—"]));
  document.getElementById("audit").innerHTML=table(["الإجراء","المورد","المعرف","المستخدم","التاريخ"],l.events.map(x=>[x.action,x.resource_type||"-",x.resource_id||"-",x.user_id||"-",x.created_at]));
  document.getElementById("state").textContent="تم التحديث بنجاح";
 }catch(e){document.getElementById("state").textContent="تعذر تحميل البيانات: "+e.message}
}
async function loadStudents(){
 const q=encodeURIComponent(document.getElementById("studentSearch")?.value||"");
 try{
  const s=await get("/manager/students?limit=10&query="+q);
  document.getElementById("students").innerHTML=table(["الاسم","النوع","الحالة","التحقق","التاريخ","إجراء"],s.students.map(x=>[x.name,x.user_type,x.profile_status,x.biometric_verified?"نعم":"لا",x.updated_at,"__HTML__<button onclick="viewStudent('"+x.user_id+"')">عرض</button>"]));
 }catch(e){document.getElementById("state").textContent="تعذر البحث: "+e.message}
}

async function viewStudent(id){
 document.getElementById("studentModal").classList.add("open");
 document.getElementById("studentState").textContent="جاري تحميل ملف الطالب...";
 document.getElementById("studentDetails").innerHTML="";
 try{
  const x=await get("/manager/students/"+encodeURIComponent(id)+"/snapshot");
  const s=x.student||{};
  document.getElementById("studentTitle").textContent=s.full_name||s.display_name||"تفاصيل الطالب";
  document.getElementById("studentState").textContent="تم تحميل الملف التشغيلي";
  const usage=(x.teaching_usage||[]).map(u=>"<div class=\"detail\"><b>المصدر</b>"+esc(u.source)+"<br>الملفات: "+esc(u.files_used)+" / "+esc(u.files_limit)+"<br>الحروف: "+esc(u.response_chars_used)+" / "+esc(u.response_chars_limit)+"<br>المتبقي: "+esc(u.response_chars_remaining)+(u.paid_access?" · مدفوع":"")+"</div>").join("");
  const progress=(x.progress?.steps||[]).map(p=>"<div class=\"detail\"><b>"+esc(p.course_name||p.scope_key||"خطوة")+"</b>الحالة: "+esc(p.status)+"<br>المحاولات: "+esc(p.attempts)+"<br>فهم موثق: "+(p.understanding_verified?"نعم":"لا")+"<br>مؤكد: "+(p.student_confirmed?"نعم":"لا")+"</div>").join("");
  const teachers=(x.teacher_agents||[]).map(t=>"<div class=\"detail\"><b>المدرس</b>"+esc(t.name)+"<br>"+esc(t.course_code||"")+" — "+esc(t.course_name||"")+"<br>الحالة: "+esc(t.status)+"</div>").join("");
  const assessments=(x.assessments||[]).map(a=>"<div class=\"detail\"><b>اختبار</b>"+esc(a.assessment_id)+"<br>النسبة: "+esc(a.percentage??"-")+"<br>النتيجة: "+(a.passed===true?"ناجح":a.passed===false?"غير ناجح":"غير مكتمل")+"<br>التاريخ: "+esc(a.submitted_at||a.started_at)+"</div>").join("");
  const payments=(x.payments||[]).map(p=>"<div class=\"detail\"><b>دفع</b>"+esc(p.product_key)+"<br>الحالة: "+esc(p.status)+"<br>المبلغ: "+esc(p.amount??"-")+" "+esc(p.currency??"")+"</div>").join("");
  document.getElementById("studentDetails").innerHTML="<div class=\"detail-grid\"><div class=\"detail\"><b>النوع</b>"+esc(s.user_type)+"</div><div class=\"detail\"><b>الحالة</b>"+esc(s.profile_status)+"</div><div class=\"detail\"><b>البريد</b>"+esc(s.email||"-")+"</div><div class=\"detail\"><b>الهاتف</b>"+esc(s.phone||"-")+"</div><div class=\"detail\"><b>العمر</b>"+esc(s.age??"-")+"</div><div class=\"detail\"><b>التحقق الحيوي</b>"+(s.biometric_verified?"نعم":"لا")+"</div><div class=\"detail\"><b>الخطوات</b>"+esc(x.progress?.steps_completed||0)+" / "+esc(x.progress?.steps_total||0)+"</div></div><h3>استخدام التدريس</h3><div class=\"detail-grid\">"+(usage||"<div class=\"detail\">لا توجد بيانات استخدام.</div>")+"</div><h3>تقدم الدراسة</h3><div class=\"detail-grid\">"+(progress||"<div class=\"detail\">لا توجد خطوات مسجلة.</div>")+"</div><h3>المدرسون</h3><div class=\"detail-grid\">"+(teachers||"<div class=\"detail\">لا يوجد مدرس مسند.</div>")+"</div><h3>الاختبارات</h3><div class=\"detail-grid\">"+(assessments||"<div class=\"detail\">لا توجد محاولات.</div>")+"</div><h3>المدفوعات</h3><div class=\"detail-grid\">"+(payments||"<div class=\"detail\">لا توجد معاملات.</div>")+"</div>";
 }catch(e){document.getElementById("studentState").textContent="تعذر تحميل الملف: "+e.message}
}
function closeStudent(){document.getElementById("studentModal").classList.remove("open")}

async function provisionTeacher(){
 const id=document.getElementById("courseSelect").value;
 if(!id)return alert("اختر مقررًا أولًا");
 await post("/manager/teachers/"+encodeURIComponent(id)+"/provision",{});
 await load();
}
async function changeStatus(id,status){
 await post("/manager/teachers/"+encodeURIComponent(id)+"/status?status="+encodeURIComponent(status),{});
 await load();
}
async function savePaymentAccount(){
 const body={provider_name:payProvider.value,account_name:payAccountName.value||null,account_number:payAccountNumber.value,amount:payAmount.value?Number(payAmount.value):null,currency:payCurrency.value||null,instructions:payInstructions.value||null,active:true};
 try{await fetch("/student/payments/account",{method:"PUT",headers:{"Content-Type":"application/json"},credentials:"same-origin",body:JSON.stringify(body)}).then(async r=>{if(!r.ok)throw new Error(await r.text())});payAccountState.textContent="تم حفظ إعدادات الدفع";}catch(e){payAccountState.textContent="فشل الحفظ: "+e.message}
}
async function confirmPayment(id){
 if(!confirm("تأكيد هذه المعاملة؟"))return;
 await post("/manager/payments/"+encodeURIComponent(id)+"/confirm",{});
 await load();
}
async function rejectPayment(id){
 const reason=prompt("سبب الرفض (اختياري):")||"Payment rejected by manager";
 await post("/manager/payments/"+encodeURIComponent(id)+"/reject",{reason});
 await load();
}
async function post(path,body){
 const r=await fetch(path,{method:"POST",headers:{"Content-Type":"application/json"},credentials:"same-origin",body:JSON.stringify(body||{})});
 if(!r.ok){const t=await r.text();throw new Error(t||("HTTP "+r.status));}
 return r.json();
}
load();
</script>
</body>
</html>"""
