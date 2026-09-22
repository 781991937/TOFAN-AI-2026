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
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>TOFAN Smart Academy — Manager</title>
<style>
:root{--bg:#080808;--panel:#111;--panel2:#171717;--line:#2a2a2a;--text:#f5f5f5;--muted:#999;--gold:#d4af37;--ok:#35b56a;--danger:#e05b5b;--blue:#5da9e9}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
header{padding:18px 5%;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;background:rgba(8,8,8,.96);z-index:10}
.brand{font-weight:900;font-size:20px}.brand span{color:var(--gold)}button{border:0;border-radius:8px;padding:9px 13px;font-weight:700;cursor:pointer;background:var(--gold);color:#111}
button.ghost{background:#222;color:#fff;border:1px solid #383838;padding:6px 9px}button.danger{background:#3a1717;color:#ffb0b0;border:1px solid #663030}button.ok{background:#173a25;color:#9ff0bd;border:1px solid #2c6744}
main{padding:26px 5%;max-width:1600px;margin:auto}.sub,.muted{color:var(--muted);font-size:13px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:20px 0}
.card,.panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px}.label{color:var(--muted);font-size:12px}.num{font-size:28px;font-weight:900;color:var(--gold);margin-top:5px}
section{margin-top:24px}.section-title{font-size:18px;font-weight:900;margin-bottom:10px}.toolbar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:12px}
.table-wrap{overflow:auto;background:var(--panel);border:1px solid var(--line);border-radius:12px}table{width:100%;border-collapse:collapse;min-width:760px}th,td{padding:11px;border-bottom:1px solid var(--line);text-align:right;font-size:13px}th{color:var(--gold)}
input,select,textarea{background:#181818;color:#fff;border:1px solid #363636;border-radius:8px;padding:10px;width:100%}textarea{min-height:90px;resize:vertical}
.field{display:grid;gap:6px}.field label{font-size:12px;color:var(--muted)}.form-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px}
.tree{display:grid;gap:10px}.node{background:#151515;border:1px solid #2c2c2c;border-radius:10px;padding:12px}.node.dragging{opacity:.45;border-color:var(--gold)}.children{margin-top:9px;margin-right:18px;display:grid;gap:7px}.row{display:flex;gap:7px;align-items:center;flex-wrap:wrap}.node-title{font-weight:800}.pill{font-size:11px;padding:3px 7px;border-radius:999px;background:#242424;color:#ccc}.active{color:#8ee6aa}.inactive{color:#ff9b9b}
.modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.82);z-index:30;padding:18px;overflow:auto}.modal.open{display:block}.modal-card{max-width:900px;margin:25px auto;background:#101010;border:1px solid var(--gold);border-radius:15px;padding:20px}.modal-head{display:flex;justify-content:space-between;gap:10px;align-items:center}.modal-close{background:#222;color:#fff}.notice{padding:10px;border-radius:8px;background:#191919;border:1px solid var(--line);margin-top:10px}.status{font-size:13px;color:var(--muted)}#toast{position:fixed;bottom:20px;left:20px;background:#171717;border:1px solid var(--gold);padding:11px 15px;border-radius:9px;display:none;z-index:50}
@media(max-width:700px){main{padding:18px 3%}.modal{padding:8px}.modal-card{margin:8px auto;padding:14px}.form-grid{grid-template-columns:1fr}}
</style></head>
<body>
<header><div class="brand">TOFAN <span>SMART ACADEMY</span> · Manager</div><button onclick="load()">تحديث</button></header>
<main>
<h1>لوحة المدير العام</h1><div class="sub">إدارة الأكاديمية والمنهج والدفع والمحتوى من مكان واحد</div>
<section><div class="section-title">🤖 محادثة المدير العام الذكي</div>
<div class="panel">
<div id="gmMessages" style="height:280px;overflow:auto;display:grid;gap:8px;margin-bottom:10px"></div>
<div class="toolbar"><input id="gmInput" placeholder="اكتب طلبك للمدير العام..." style="flex:1;min-width:220px"><button onclick="sendGeneralManager()">إرسال</button></div>
<div class="muted">المدير العام ينسّق الوكلاء والأدوات المصرّح بها ويسجل العمليات الحساسة.</div>
</div></section><div id="state" class="status">جاري التحميل...</div>
<div id="cards" class="grid"></div>

<section><div class="section-title">إدارة المدرسين</div><div class="table-wrap"><div class="toolbar" style="padding:12px"><select id="courseSelect" style="max-width:500px"></select><button onclick="provisionTeacher()">إنشاء مدرس للمقرر</button></div><div id="teachers"></div></div></section>

<section><div class="section-title">الطلاب</div><div class="table-wrap"><div class="toolbar" style="padding:12px"><input id="studentSearch" placeholder="ابحث بالاسم أو البريد أو الهاتف"><button onclick="loadStudents()">بحث</button></div><div id="students"></div></div></section>
<section><div class="section-title">الاختبارات</div><div id="assessments" class="table-wrap"></div></section>

<section><div class="section-title">إدارة المنهج الأكاديمي</div>
<div class="panel">
<div class="toolbar">
<button onclick="openEditor('curriculum')">+ منهج</button><button onclick="openEditor('specialty')">+ تخصص</button><button onclick="openEditor('stage')">+ سنة / فصل</button><button onclick="openEditor('course')">+ مقرر</button><button onclick="openEditor('unit')">+ وحدة</button><button onclick="openEditor('lesson')">+ محاضرة</button>
<button class="ghost" onclick="loadNativeTree()">تحديث الشجرة</button>
</div>
<div class="notice">اختر المستوى الأب من القوائم داخل النموذج. يمكن سحب العناصر داخل المستوى نفسه لإعادة ترتيبها، مع حفظ الترتيب مباشرة.</div>
<div id="nativeTree" class="tree" style="margin-top:12px"><div class="node">جاري تحميل المنهج...</div></div>
</div></section>

<section><div class="section-title">إدارة ملفات المحاضرات</div><div class="panel"><div class="form-grid">
<div class="field"><label>المحاضرة</label><select id="fileLesson"></select></div>
<div class="field"><label>ملف PDF / DOCX / TXT</label><input id="lessonFile" type="file" accept=".pdf,.docx,.txt"></div>
</div><div class="toolbar" style="margin-top:10px"><button onclick="uploadLessonFile()">رفع الملف</button><button class="ghost" onclick="loadLessonFiles()">عرض ملفات المحاضرة</button></div><div id="lessonFiles"></div></div></section>

<section><div class="section-title">إعداد نقطة الدفع</div><div class="panel"><div class="form-grid">
<div class="field"><label>مزود الدفع</label><input id="payProvider"></div><div class="field"><label>اسم صاحب الحساب</label><input id="payAccountName"></div><div class="field"><label>رقم النقطة / الحساب</label><input id="payAccountNumber"></div><div class="field"><label>المبلغ الافتراضي</label><input id="payAmount" type="number" min="0" step="0.01"></div><div class="field"><label>العملة</label><input id="payCurrency"></div><div class="field"><label>التعليمات</label><textarea id="payInstructions"></textarea></div>
</div><div class="toolbar" style="margin-top:10px"><button onclick="savePaymentAccount()">حفظ إعدادات الدفع</button><span id="payAccountState" class="status"></span></div></div></section>
<section><div class="section-title">المدفوعات</div><div id="payments" class="table-wrap"></div></section>
<section><div class="section-title">آخر أحداث التدقيق</div><div id="audit" class="table-wrap"></div></section>
<section><div class="section-title">إدارة الإشعارات</div><div class="panel"><div class="form-grid">
<div class="field"><label>العنوان</label><input id="noticeTitle" maxlength="255"></div>
<div class="field"><label>نوع الحدث</label><input id="noticeEvent" value="admin.broadcast" maxlength="100"></div>
<div class="field" style="grid-column:1/-1"><label>الرسالة</label><textarea id="noticeMessage" maxlength="5000"></textarea></div>
</div><div class="toolbar" style="margin-top:10px"><button onclick="broadcastNotification()">إرسال لجميع المستخدمين</button><span id="noticeState" class="status"></span></div></div></section>
</main>

<div id="editor" class="modal" onclick="if(event.target===this)closeEditor()"><div class="modal-card"><div class="modal-head"><div><h2 id="editorTitle">إضافة</h2><div class="sub">نموذج إدارة أكاديمي</div></div><button class="modal-close" onclick="closeEditor()">إغلاق</button></div><form id="editorForm" onsubmit="saveEditor(event)"><div id="editorFields" class="form-grid" style="margin-top:15px"></div><div class="toolbar" style="margin-top:15px"><button type="submit">حفظ</button><button type="button" class="ghost" onclick="closeEditor()">إلغاء</button><span id="editorState" class="status"></span></div></form></div></div>
<div id="toast"></div>

<script>
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
async function api(path,opt={}){const r=await fetch(path,{...opt,credentials:"same-origin",headers:opt.body instanceof FormData?{...(opt.headers||{})}:{"Content-Type":"application/json",...(opt.headers||{})}});if(!r.ok){let d={};try{d=await r.json()}catch{}throw new Error(d.detail||"HTTP "+r.status)}return r.status===204?null:r.json()}
const toast=m=>{const e=document.getElementById("toast");e.textContent=m;e.style.display="block";setTimeout(()=>e.style.display="none",2600)};
const cardsEl=document.getElementById("cards"),courseSelect=document.getElementById("courseSelect"),teachers=document.getElementById("teachers"),students=document.getElementById("students"),assessments=document.getElementById("assessments"),payments=document.getElementById("payments"),audit=document.getElementById("audit"),payProvider=document.getElementById("payProvider"),payAccountName=document.getElementById("payAccountName"),payAccountNumber=document.getElementById("payAccountNumber"),payAmount=document.getElementById("payAmount"),payCurrency=document.getElementById("payCurrency"),payInstructions=document.getElementById("payInstructions"),payAccountState=document.getElementById("payAccountState");
const opt=(items,placeholder="اختر...")=>'<option value="">'+placeholder+'</option>'+items.map(x=>'<option value="'+esc(x.id)+'">'+esc(x.name||x.title||x.code)+'</option>').join("");
let catalog={curricula:[],specialties:[],stages:[],courses:[],units:[],lessons:[]};
let editorType=null,editorId=null;

async function refreshCatalog(){
 catalog.curricula=await api("/admin/academy/native/curricula");
 catalog.specialties=await api("/admin/academy/native/specialties");
 catalog.stages=[];catalog.courses=[];catalog.units=[];catalog.lessons=[];
 for(const c of catalog.curricula){const ss=await api("/admin/academy/native/stages?curriculum_id="+encodeURIComponent(c.id));catalog.stages.push(...ss);for(const s of ss){const cs=await api("/admin/academy/native/courses?stage_id="+encodeURIComponent(s.id));catalog.courses.push(...cs);for(const co of cs){const us=await api("/admin/academy/native/units?course_id="+encodeURIComponent(co.id));catalog.units.push(...us);for(const u of us){const ls=await api("/admin/academy/native/lessons?unit_id="+encodeURIComponent(u.id));catalog.lessons.push(...ls)}}}}
}

function actionButtons(type,item){
 const active=item.is_active===false?'<span class="pill inactive">غير نشط</span>':'<span class="pill active">نشط</span>';
 return '<button class="ghost" onclick="openEditor(\''+type+'\',\''+item.id+'\')">تعديل</button> <button class="ghost" onclick="toggleActive(\''+type+'\',\''+item.id+'\')">'+(item.is_active===false?"تفعيل":"تعطيل")+'</button> <button class="danger" onclick="removeNode(\''+type+'\',\''+item.id+'\')">حذف</button> '+active;
}
function node(title,meta,actions,children=""){return '<div class="node" draggable="true" data-id="'+esc(meta.id||"")+'" data-type="'+esc(meta.type||"")+'" ondragstart="dragStart(event)" ondragover="event.preventDefault()" ondrop="dropNode(event)"><div class="row"><span class="node-title">'+esc(title)+'</span><span class="pill">'+esc(meta.code||"")+'</span><span class="muted">'+esc(meta.extra||"")+'</span><span style="margin-right:auto">'+actions+'</span></div>'+children+'</div>'}

async function loadNativeTree(){
 try{
  await refreshCatalog();
  const root=document.getElementById("nativeTree");root.innerHTML="";
  for(const cur of catalog.curricula){
   const ss=catalog.stages.filter(x=>x.curriculum_id===cur.id);
   let ch="";
   for(const s of ss){
    const cs=catalog.courses.filter(x=>x.stage_id===s.id);
    let chtml="";
    for(const co of cs){
     const us=catalog.units.filter(x=>x.course_id===co.id);let uhtml="";
     for(const u of us){
      const ls=catalog.lessons.filter(x=>x.unit_id===u.id);
      const lhtml=ls.map(l=>node(l.title,{id:l.id,type:"lesson",code:"#"+l.position},actionButtons("lesson",l))).join("");
      uhtml+=node(u.title,{id:u.id,type:"unit",code:"#"+u.position},actionButtons("unit",u)+lhtml);
     }
     chtml+=node(co.name,{id:co.id,type:"course",code:co.code,extra:"مقرر"},actionButtons("course",co)+uhtml);
    }
    ch+=node(s.name,{id:s.id,type:"stage",code:s.code,extra:"مرحلة"},actionButtons("stage",s)+chtml);
   }
   root.innerHTML+=node(cur.name,{id:cur.id,type:"curriculum",code:cur.version,extra:cur.status},'<button class="ghost" onclick="openEditor(\'curriculum\',\''+cur.id+'\')">تعديل</button> <button class="danger" onclick="removeNode(\'curriculum\',\''+cur.id+'\')">حذف</button>'+ch);
  }
  if(!catalog.curricula.length)root.innerHTML='<div class="node">لا يوجد منهج بعد.</div>';
  fillLessonSelect();
 }catch(e){document.getElementById("nativeTree").innerHTML='<div class="node inactive">'+esc(e.message)+'</div>'}
}

function fillLessonSelect(){document.getElementById("fileLesson").innerHTML=opt(catalog.lessons.map(x=>({id:x.id,name:x.position+". "+x.title})),"اختر المحاضرة");}
function fieldsFor(type,item={}){
 const selected=(id)=>esc(id||"");
 if(type==="curriculum")return '<div class="field"><label>اسم المنهج</label><input name="name" required value="'+esc(item.name)+'"></div><div class="field"><label>الإصدار</label><input name="version" required value="'+esc(item.version)+'"></div><div class="field"><label>Slug</label><input name="slug" '+(item.id?"readonly":"required")+' value="'+esc(item.slug)+'"></div><div class="field"><label>الحالة</label><select name="status"><option value="draft">مسودة</option><option value="active">نشط</option><option value="archived">مؤرشف</option></select></div><div class="field" style="grid-column:1/-1"><label>الوصف</label><textarea name="description">'+esc(item.description)+'</textarea></div>';
 if(type==="specialty")return '<div class="field"><label>اسم التخصص</label><input name="name" required value="'+esc(item.name)+'"></div><div class="field"><label>الرمز</label><input name="code" required value="'+esc(item.code)+'"></div><div class="field"><label>الاسم بالعربية</label><input name="name_ar" value="'+esc(item.name_ar) +'"></div><div class="field"><label>الاسم بالإنجليزية</label><input name="name_en" value="'+esc(item.name_en)+'"></div>';
 if(type==="stage")return '<div class="field"><label>المنهج</label><select name="curriculum_id" required>'+opt(catalog.curricula)+ '</select></div><div class="field"><label>التخصص</label><select name="specialty_id" required>'+opt(catalog.specialties)+'</select></div><div class="field"><label>الاسم</label><input name="name" required value="'+esc(item.name)+'"></div><div class="field"><label>الرمز</label><input name="code" required value="'+esc(item.code)+'"></div><div class="field"><label>الترتيب</label><input name="position" type="number" min="1" required value="'+esc(item.position||1)+'"></div><div class="field" style="grid-column:1/-1"><label>الوصف</label><textarea name="description">'+esc(item.description)+'</textarea></div>';
 if(type==="course")return '<div class="field"><label>المرحلة</label><select name="stage_id" required>'+opt(catalog.stages.map(x=>({id:x.id,name:x.name+" · "+x.code})))+'</select></div><div class="field"><label>رمز المقرر</label><input name="code" required value="'+esc(item.code)+'"></div><div class="field"><label>اسم المقرر</label><input name="name" required value="'+esc(item.name)+'"></div><div class="field"><label>نوع المقرر</label><select name="course_type"><option value="required">إجباري</option><option value="elective">اختياري</option><option value="practical">عملي</option></select></div><div class="field"><label>الترتيب</label><input name="position" type="number" min="1" required value="'+esc(item.position||1)+'"></div><div class="field" style="grid-column:1/-1"><label>الوصف</label><textarea name="description">'+esc(item.description)+'</textarea></div>';
 if(type==="unit")return '<div class="field"><label>المقرر</label><select name="course_id" required>'+opt(catalog.courses.map(x=>({id:x.id,name:x.code+" — "+x.name})))+'</select></div><div class="field"><label>عنوان الوحدة</label><input name="title" required value="'+esc(item.title)+'"></div><div class="field"><label>الترتيب</label><input name="position" type="number" min="1" required value="'+esc(item.position||1)+'"></div>';
 return '<div class="field"><label>الوحدة</label><select name="unit_id" required>'+opt(catalog.units.map(x=>({id:x.id,name:x.position+". "+x.title})))+'</select></div><div class="field"><label>عنوان المحاضرة</label><input name="title" required value="'+esc(item.title)+'"></div><div class="field"><label>الترتيب</label><input name="position" type="number" min="1" required value="'+esc(item.position||1)+'"></div><div class="field" style="grid-column:1/-1"><label>الوصف</label><textarea name="description">'+esc(item.description)+'</textarea></div><div class="field" style="grid-column:1/-1"><label>محتوى Markdown</label><textarea name="content_markdown">'+esc(item.content_markdown)+'</textarea></div>';
}
function openEditor(type,id=""){
 editorType=type;editorId=id;
 const item=id?(catalog[{curriculum:"curricula",specialty:"specialties",stage:"stages",course:"courses",unit:"units",lesson:"lessons"}[type]]||[]).find(x=>x.id===id):{};
 document.getElementById("editorTitle").textContent=(id?"تعديل ":"إضافة ")+({curriculum:"منهج",specialty:"تخصص",stage:"مرحلة",course:"مقرر",unit:"وحدة",lesson:"محاضرة"}[type]);
 document.getElementById("editorFields").innerHTML=fieldsFor(type,item||{});
 const form=document.getElementById("editorForm");
 for(const [name,value] of Object.entries(item||{})){const el=form.elements[name];if(el&&value!=null)el.value=value}
 document.getElementById("editor").classList.add("open");
}
function closeEditor(){document.getElementById("editor").classList.remove("open");editorId=null;editorType=null}
async function saveEditor(e){
 e.preventDefault();const fd=new FormData(e.target),d=Object.fromEntries(fd.entries());document.getElementById("editorState").textContent="جارٍ الحفظ...";
 try{
  let path,method="POST";
  if(editorType==="curriculum"){path=editorId?"/admin/academy/native/curricula/"+editorId:"/admin/academy/native/curricula";if(editorId){method="PATCH";delete d.slug}}
  else if(editorType==="specialty"){path=editorId?"/admin/academy/native/specialties/"+editorId:"/admin/academy/native/specialties";if(editorId)method="PATCH"}
  else if(editorType==="stage"){path=editorId?"/admin/academy/native/stages/"+editorId:"/admin/academy/native/stages";if(editorId)method="PATCH";else d.position=Number(d.position)}
  else if(editorType==="course"){path=editorId?"/admin/academy/native/courses/"+editorId:"/admin/academy/native/courses";if(editorId)method="PATCH";else{d.position=Number(d.position);const st=catalog.stages.find(x=>x.id===d.stage_id);d.curriculum_id=st.curriculum_id}if(editorId)delete d.stage_id}
  else if(editorType==="unit"){path=editorId?"/admin/academy/native/units/"+editorId:"/admin/academy/native/units";if(editorId)method="PATCH";else d.position=Number(d.position)}
  else {path=editorId?"/admin/academy/native/lessons/"+editorId:"/admin/academy/native/lessons";if(editorId)method="PATCH";else d.position=Number(d.position)}
  await api(path,{method,body:JSON.stringify(d)});toast("تم الحفظ");closeEditor();await loadNativeTree();
 }catch(err){document.getElementById("editorState").textContent=err.message}
}
async function removeNode(type,id){if(!confirm("حذف هذا العنصر؟ قد يفشل الحذف إذا كانت له بيانات مرتبطة."))return;try{await api("/admin/academy/native/"+type+"/"+id,{method:"DELETE"});toast("تم الحذف");await loadNativeTree()}catch(e){toast(e.message)}}
async function toggleActive(type,id){if(!["specialty","course"].includes(type))return toast("التفعيل/التعطيل متاح للتخصص والمقرر حاليًا.");try{await api("/admin/academy/native/"+type+"/"+id+"/active",{method:"PATCH"});toast("تم تحديث الحالة");await loadNativeTree()}catch(e){toast(e.message)}}
let dragData=null;function dragStart(e){const n=e.currentTarget;dragData={id:n.dataset.id,type:n.dataset.type};n.classList.add("dragging");e.dataTransfer.effectAllowed="move"}async function dropNode(e){e.preventDefault();const target=e.currentTarget;target.classList.remove("dragging");if(!dragData||dragData.type!==target.dataset.type||dragData.id===target.dataset.id)return;const siblings=[...target.parentElement.children].filter(x=>x.classList.contains("node")&&x.dataset.type===dragData.type);const targetIndex=siblings.indexOf(target);if(targetIndex<0)return;const position=targetIndex+1;try{await api("/admin/academy/native/"+dragData.type+"/"+dragData.id+"/reorder?position="+position,{method:"POST"});toast("تم حفظ الترتيب");await loadNativeTree()}catch(err){toast(err.message)}finally{dragData=null}}

async function uploadLessonFile(){const id=document.getElementById("fileLesson").value,f=document.getElementById("lessonFile").files[0];if(!id||!f)return toast("اختر المحاضرة والملف أولاً");const fd=new FormData();fd.append("file",f);try{await api("/admin/content/lectures/"+id+"/files",{method:"POST",body:fd});toast("تم رفع الملف");await loadLessonFiles()}catch(e){toast(e.message)}}
async function loadLessonFiles(){const id=document.getElementById("fileLesson").value;if(!id)return;try{const d=await api("/admin/content?lecture_id="+encodeURIComponent(id));document.getElementById("lessonFiles").innerHTML=d.files.map(x=>'<div class="notice"><b>'+esc(x.original_name)+'</b> · '+esc(x.status)+' · '+esc(x.text_characters)+' حرف · '+esc(x.size_bytes)+' bytes</div>').join("")||'<div class="notice">لا توجد ملفات.</div>'}catch(e){toast(e.message)}}

async function broadcastNotification(){
 const title=document.getElementById("noticeTitle").value.trim();
 const message=document.getElementById("noticeMessage").value.trim();
 const event_type=document.getElementById("noticeEvent").value.trim()||"admin.broadcast";
 if(!title||!message)return toast("أدخل عنوان الإشعار والرسالة");
 try{
  const d=await api("/admin/notifications/broadcast",{method:"POST",body:JSON.stringify({title,message,event_type})});
  document.getElementById("noticeState").textContent="تم إرسال "+d.created+" إشعار";
  document.getElementById("noticeMessage").value="";
 }catch(e){document.getElementById("noticeState").textContent=e.message}
}
async function savePaymentAccount(){try{const d={provider_name:payProvider.value.trim(),account_name:payAccountName.value.trim()||null,account_number:payAccountNumber.value.trim(),amount:payAmount.value?Number(payAmount.value):null,currency:payCurrency.value.trim()||null,instructions:payInstructions.value.trim()||null};await api("/student/payments/account",{method:"PUT",body:JSON.stringify(d)});payAccountState.textContent="تم الحفظ";toast("تم حفظ إعدادات الدفع")}catch(e){payAccountState.textContent=e.message}}
async function confirmPayment(id){if(!confirm("تأكيد الدفع وتفعيل الوصول؟"))return;try{await api("/manager/payments/"+id+"/confirm",{method:"POST"});toast("تم تأكيد الدفع");load()}catch(e){toast(e.message)}}
async function rejectPayment(id){const reason=prompt("سبب الرفض (اختياري)","");try{await api("/manager/payments/"+id+"/reject?reason="+encodeURIComponent(reason||""),{method:"POST"});toast("تم رفض الدفع");load()}catch(e){toast(e.message)}}
async function provisionTeacher(){const course_id=document.getElementById("courseSelect").value;if(!course_id)return toast("اختر مقررًا");try{await api("/manager/teachers/"+encodeURIComponent(course_id)+"/provision",{method:"POST"});toast("تم إنشاء المدرس");load()}catch(e){toast(e.message)}}
async function changeStatus(id,status){try{await api("/manager/teachers/"+encodeURIComponent(id)+"/status?status="+encodeURIComponent(status),{method:"POST"});load()}catch(e){toast(e.message)}}
async function loadStudents(){load()}
async function viewStudent(id){toast("عرض تفاصيل الطالب: "+id)}

function table(headers,rows){return '<table><thead><tr>'+headers.map(h=>'<th>'+esc(h)+'</th>').join("")+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+r.map(v=>'<td>'+v+'</td>').join("")+'</tr>').join("")+'</tbody></table>'}
async function load(){
 document.getElementById("state").textContent="جاري التحديث...";
 try{
  const q=encodeURIComponent(document.getElementById("studentSearch")?.value||"");
  const [d,a,p,l,t,s,c]=await Promise.all([api("/manager/dashboard"),api("/manager/assessments?limit=10"),api("/manager/payments?limit=10"),api("/manager/audit-log?limit=10"),api("/manager/teachers"),api("/manager/students?limit=10&query="+q),api("/manager/courses")]);
  const cards=[["المستخدمون",d.users.total],["طلاب الجامعات",d.users.university_students],["المتعلمون المستقلون",d.users.independent_learners],["المدرسون النشطون",d.teachers.active],["المقررات",d.curriculum.active_courses],["الدروس",d.curriculum.lessons],["محاولات الاختبار",d.assessments.attempts],["ناجح",d.assessments.passed],["مدفوعات معلقة",d.payments.pending],["مدفوعات مؤكدة",d.payments.confirmed]];
  cardsEl.innerHTML=cards.map(x=>'<div class="card"><div class="label">'+esc(x[0])+'</div><div class="num">'+esc(x[1])+'</div></div>').join("");
  courseSelect.innerHTML='<option value="">اختر مقررًا</option>'+c.courses.map(x=>'<option value="'+esc(x.course_id)+'">'+esc(x.code+" — "+x.name)+'</option>').join("");
  teachers.innerHTML=table(["المدرس","المقرر","الحالة","إجراء"],t.teachers.map(x=>[esc(x.name),esc(x.curriculum_course_id||"-"),esc(x.status),'<button class="ghost" onclick="changeStatus(\''+x.agent_id+'\',\''+(x.status==="active"?"paused":"active")+'\')">'+(x.status==="active"?"إيقاف":"تفعيل")+'</button>']));
  students.innerHTML=table(["الاسم","النوع","الحالة","التحقق","التاريخ"],s.students.map(x=>[esc(x.name),esc(x.user_type),esc(x.profile_status),x.biometric_verified?"نعم":"لا",esc(x.updated_at)]));
  assessments.innerHTML=table(["الطالب","النسبة","النتيجة","الحالة","التاريخ"],a.assessments.map(x=>[esc(x.user_id),esc(x.percentage??"-"),x.passed===true?"ناجح":x.passed===false?"غير ناجح":"-",esc(x.status),esc(x.submitted_at||x.started_at)]));
  payments.innerHTML=table(["المعاملة","المنتج","المبلغ","الحالة","المرجع","الإثبات","التاريخ","إجراء"],p.payments.map(x=>[esc(x.transaction_id),esc(x.product_key),esc((x.amount??"-")+" "+(x.currency||"")),esc(x.status),esc(x.reference||"-"),x.proof_file_id?"متوفر":"لا يوجد",esc(x.created_at),x.status==="pending"?'<button class="ok" onclick="confirmPayment(\''+x.transaction_id+'\')">تأكيد</button> <button class="danger" onclick="rejectPayment(\''+x.transaction_id+'\')">رفض</button>':"—"]));
  audit.innerHTML=table(["الحدث","المستخدم","الوقت"],(l.events||l.audit||[]).map(x=>[esc(x.action||x.event||"-"),esc(x.user_id||"-"),esc(x.created_at||"-")]));
  document.getElementById("state").textContent="تم التحديث";
 }catch(e){document.getElementById("state").textContent=e.message}
 try{const a=await api("/student/payments/account");if(a.configured){payProvider.value=a.provider_name||"";payAccountName.value=a.account_name||"";payAccountNumber.value=a.account_number||"";payAmount.value=a.amount??"";payCurrency.value=a.currency||"";payInstructions.value=a.instructions||""}}catch{}
 await loadNativeTree();
}
load();
</script><script>
function addGeneralManagerMessage(role,text){
  const box=document.getElementById("gmMessages"); if(!box)return;
  const row=document.createElement("div");
  row.style.cssText="padding:10px;border:1px solid #2a2a2a;border-radius:9px;background:"+(role==="user"?"#171717":"#1b1710");
  row.innerHTML="<b>"+(role==="user"?"أنت":"🤖 المدير العام")+"</b><div style='margin-top:5px;white-space:pre-wrap'>"+String(text).replace(/[&<>]/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[m]))+"</div>";
  box.appendChild(row); box.scrollTop=box.scrollHeight;
}
async function sendGeneralManager(){
  const input=document.getElementById("gmInput"); const message=input.value.trim(); if(!message)return;
  addGeneralManagerMessage("user",message); input.value="";
  try{
    const result=await api("/admin/agent/tofan-main/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message})});
    addGeneralManagerMessage("assistant",result.content||result.output||JSON.stringify(result,null,2));
  }catch(err){addGeneralManagerMessage("assistant","تعذر تنفيذ الطلب: "+err.message)}
}
document.getElementById("gmInput")?.addEventListener("keydown",e=>{if(e.key==="Enter"){e.preventDefault();sendGeneralManager()}});
</script></body></html>"""
