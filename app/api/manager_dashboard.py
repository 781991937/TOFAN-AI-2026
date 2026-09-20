"""Server-rendered TOFAN manager dashboard."""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/manager", tags=["main-manager-ui"])


@router.get("/dashboard-ui", response_class=HTMLResponse, include_in_schema=False)
def dashboard_ui() -> str:
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
.table-wrap{overflow:auto;background:var(--panel);border:1px solid var(--line);border-radius:12px}
table{width:100%;border-collapse:collapse;min-width:800px}th,td{padding:12px;border-bottom:1px solid var(--line);text-align:right;font-size:13px}th{color:var(--gold)}
.badge{padding:4px 8px;border-radius:999px;background:#242424}.ok{color:var(--ok)}.fail{color:var(--danger)}
#state{color:var(--muted);font-size:13px}
</style>
</head>
<body>
<header><div class="brand">TOFAN <span>SMART ACADEMY</span> · Manager</div><button onclick="load()">تحديث</button></header>
<main>
<h1>لوحة المدير العام</h1><div class="sub">مركز المراقبة التشغيلية للأكاديمية</div><div id="state">جاري تحميل البيانات...</div>
<div id="cards" class="grid"></div>
<section><div class="section-title">آخر الاختبارات</div><div id="assessments" class="table-wrap"></div></section>
<section><div class="section-title">آخر المدفوعات</div><div id="payments" class="table-wrap"></div></section>
<section><div class="section-title">آخر أحداث التدقيق</div><div id="audit" class="table-wrap"></div></section>
</main>
<script>
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",""":"&quot;"}[c]));
const cell=v=>'<td>'+esc(v)+'</td>';
function table(headers,rows){return '<table><thead><tr>'+headers.map(h=>'<th>'+h+'</th>').join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+r.map(cell).join('')+'</tr>').join('')+'</tbody></table>'}
async function get(path){const r=await fetch(path,{credentials:"same-origin"});if(!r.ok)throw new Error("HTTP "+r.status);return r.json()}
async function load(){
 document.getElementById("state").textContent="جاري التحديث...";
 try{
  const [d,a,p,l]=await Promise.all([get("/manager/dashboard"),get("/manager/assessments?limit=10"),get("/manager/payments?limit=10"),get("/manager/audit-log?limit=10")]);
  const cards=[
   ["المستخدمون",d.users.total],["طلاب الجامعات",d.users.university_students],["المتعلمون المستقلون",d.users.independent_learners],
   ["المدرسون النشطون",d.teachers.active],["المقررات",d.curriculum.active_courses],["الدروس",d.curriculum.lessons],
   ["محاولات الاختبار",d.assessments.attempts],["ناجح",d.assessments.passed],["مدفوعات معلقة",d.payments.pending],["مدفوعات مؤكدة",d.payments.confirmed]
  ];
  document.getElementById("cards").innerHTML=cards.map(x=>'<div class="card"><div class="label">'+x[0]+'</div><div class="num">'+x[1]+'</div></div>').join("");
  document.getElementById("assessments").innerHTML=table(["الطالب","النسبة","النتيجة","الحالة","التاريخ"],a.assessments.map(x=>[x.user_id,x.percentage??"-",x.passed===true?"ناجح":x.passed===false?"غير ناجح":"-",x.status,x.submitted_at||x.started_at]));
  document.getElementById("payments").innerHTML=table(["المعاملة","الطالب","المنتج","الحالة","المبلغ","التاريخ"],p.payments.map(x=>[x.transaction_id,x.user_id,x.product_key,x.status,(x.amount??"-")+" "+(x.currency??""),x.created_at]));
  document.getElementById("audit").innerHTML=table(["الإجراء","المورد","المعرف","المستخدم","التاريخ"],l.events.map(x=>[x.action,x.resource_type||"-",x.resource_id||"-",x.user_id||"-",x.created_at]));
  document.getElementById("state").textContent="تم التحديث بنجاح";
 }catch(e){document.getElementById("state").textContent="تعذر تحميل البيانات: "+e.message}
}
load();
</script>
</body>
</html>"""
