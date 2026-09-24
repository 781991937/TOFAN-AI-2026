const I18N={ar:{academy:"الأكاديمية الذكية",heroTitle:"أكاديميتك الذكية للتعلّم المتدرّج",heroText:"منهج عالمي، معلّمون بالذكاء الاصطناعي، تقدّم محفوظ، واختبارات مرتبطة بمخرجات التعلّم.",login:"تسجيل الدخول",register:"إنشاء حساب",email:"البريد الإلكتروني",password:"كلمة المرور",name:"الاسم",logout:"تسجيل الخروج",learning:"التعلّم",specialties:"التخصصات",access:"الوصول",specialtyTitle:"مسارات التخصص",dynamic:"واجهة تتكيّف مع تخصصك",home:"الرئيسية",curriculum:"المنهج",progress:"التقدم",certificates:"الشهادات",profile:"الملف",notifications:"الإشعارات",assessments:"الاختبارات",results:"النتائج والتحليل",files:"ملفاتي",refresh:"تحديث",markRead:"تحديد كمقروء",back:"العودة",outcomes:"مخرجات التعلّم",prerequisites:"المتطلبات السابقة",units:"الوحدات",lessons:"الدروس",start:"فتح المقرر",noPrereq:"لا توجد متطلبات سابقة مسجلة.",noLessons:"لا توجد دروس مسجلة في هذه الوحدة.",courseType:"نوع المقرر",required:"إلزامي",elective:"اختياري",lessonContent:"محتوى الدرس متاح عبر المعلّم الذكي بعد بدء الخطوة التعليمية.",openTeacher:"بدء التعلّم مع المعلّم الذكي",openLesson:"فتح الدرس",lesson:"الدرس",teacher:"المعلّم الذكي",teacherReady:"المعلّم الذكي مرتبط بالمقرر ويمكن تشغيله من هنا.",freeSemester:"الفصل الأول من السنة الأولى مجاني",paidSemester:"هذا المحتوى ضمن الوصول المدفوع",teacherUnavailable:"المعلّم الذكي لهذا المقرر غير مفعّل بعد.",onboardingTitle:"إعداد حساب الطالب",userType:"نوع الحساب",universityStudent:"طالب جامعي",independentLearner:"متعلم مستقل",fullName:"الاسم الكامل",age:"العمر",university:"الجامعة",college:"الكلية / المركز",major:"التخصص",saveProfile:"حفظ الملف والمتابعة",registerPasskey:"تفعيل بصمة الجهاز / Passkey",authenticatePasskey:"التحقق بالبصمة / Passkey",onboardingDone:"تم التحقق من الحساب. يمكنك الآن الدخول إلى الأكاديمية.",select:"اختر",profileSaved:"تم حفظ الملف. الخطوة التالية هي التحقق من الجهاز.",passkeyDone:"تم التحقق من الجهاز بنجاح.",passkeyLogin:"دخول بالبصمة / Passkey",passkeyLoginNeedEmail:"أدخل بريد حسابك أولاً.",passkeyLoginDone:"تم تسجيل الدخول بالبصمة بنجاح.",underConstruction:"غير متاح حاليًا — سيتم إضافته لاحقًا."},en:{academy:"Smart Academy",heroTitle:"Your intelligent academy for mastery-based learning",heroText:"Global knowledge, AI teachers, persistent progress, and assessments tied to learning outcomes.",login:"Sign in",register:"Create account",email:"Email",password:"Password",name:"Name",logout:"Sign out",learning:"Learning",specialties:"Specialties",access:"Access",specialtyTitle:"Specialty paths",dynamic:"An experience that adapts to your specialty",home:"Home",curriculum:"Curriculum",progress:"Progress",certificates:"Certificates",profile:"Profile",notifications:"Notifications",assessments:"Assessments",results:"Results & Analysis",files:"My Files",refresh:"Refresh",markRead:"Mark as read",back:"Back",outcomes:"Learning outcomes",prerequisites:"Prerequisites",units:"Units",lessons:"Lessons",start:"Open course",noPrereq:"No prerequisites recorded.",noLessons:"No lessons are registered in this unit.",courseType:"Course type",required:"Required",elective:"Elective",lessonContent:"Lesson content is delivered through the smart teacher after the learning step begins.",openTeacher:"Start learning with the smart teacher",openLesson:"Open lesson",lesson:"Lesson",teacher:"AI Teacher",teacherReady:"The AI teacher is linked to this course and can be started here.",freeSemester:"Year 1 · Semester 1 is free",paidSemester:"This content is part of paid access",teacherUnavailable:"The AI teacher for this course is not active yet.",onboardingTitle:"Student account setup",userType:"Account type",universityStudent:"University student",independentLearner:"Independent learner",fullName:"Full name",age:"Age",university:"University",college:"College / Center",major:"Specialization",saveProfile:"Save profile and continue",registerPasskey:"Enable device passkey",authenticatePasskey:"Verify with passkey",onboardingDone:"Your account is verified. You can now enter the academy.",select:"Select",profileSaved:"Profile saved. The next step is device verification.",passkeyDone:"Device verification completed.",underConstruction:"Not available yet — it will be added later."}};
let lang=localStorage.getItem("tofan_lang")||"ar",mode="login",token=localStorage.getItem("tofan_token"),isOwner=false,currentSpecialty=null;
let voiceOutput=localStorage.getItem("tofan_voice_output")!=="off",speechRecognition=null,speechListening=false;
const $=s=>document.querySelector(s),$$=s=>document.querySelectorAll(s);
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
I18N.ar.owner="المدير العام";I18N.en.owner="General Manager";function t(k){return I18N[lang][k]||k}
function applyLang(){document.documentElement.lang=lang;document.documentElement.dir=lang==='ar'?"rtl":"ltr";document.body.classList.toggle("en",lang==='en');$$$("[data-i18n]").forEach(e=>e.textContent=t(e.dataset.i18n));$("#langBtn").textContent=lang==='ar'?"EN":"AR"}
function toast(m){$("#toast").textContent=m;$("#toast").classList.add("show");setTimeout(()=>$("#toast").classList.remove("show"),2600)}
async function api(path,opt={}){opt.headers={...(opt.headers||{}),...(token?{"Authorization":"Bearer "+token}:{})};const r=await fetch(path,opt);let d={};try{d=await r.json()}catch{}if(!r.ok)throw new Error(d.detail||"Request failed");return d}
async function showView(view){
  const valid=["home","curriculum","progress","assessments","results","files","certificates","profile","notifications","access","owner"];
  if(!valid.includes(view))return;
  $$(".nav-btn").forEach(b=>b.classList.toggle("active",b.dataset.view===view));
  ["curriculumPanel","coursePanel","lessonPanel","notificationsPanel","accessPanel","ownerPanel","assessmentPanel","resultsPanel","filesPanel"].forEach(id=>{const e=$("#"+id);if(e)e.classList.add("hidden")});
  try{
    if(view==="home")return;
    if(view==="curriculum")await openCurriculum();
    else if(view==="progress")await loadProgress();
    else if(view==="assessments"&&typeof window.loadAssessments==="function")await window.loadAssessments();
    else if(view==="results"&&typeof window.loadAssessmentResults==="function")await window.loadAssessmentResults();
    else if(view==="files"&&typeof window.loadStudentFiles==="function")await window.loadStudentFiles();
    else if(view==="certificates")await loadCertificates();
    else if(view==="profile")await loadProfile();
    else if(view==="notifications")await loadNotifications();
    else if(view==="access"&&typeof window.loadAccess==="function")await window.loadAccess();
    else if(view==="owner"&&isOwner)await openOwnerManager();
  }catch(err){console.error("TOFAN navigation error",view,err);toast(err?.message||"تعذر فتح الواجهة المطلوبة");}
}
document.addEventListener("click",event=>{
  const button=event.target.closest?.(".nav-btn");
  if(!button||button.disabled)return;
  event.preventDefault();
  showView(button.dataset.view);
});
function setMode(m){mode=m;$$$(".tab").forEach(x=>x.classList.toggle("active",x.dataset.mode===m));$("#nameWrap").classList.toggle("hidden",m!=="register");$("#authSubmit").textContent=t(m==="login"?"login":"register");$("#authError").textContent=""}
$$$(".tab").forEach(x=>x.onclick=()=>setMode(x.dataset.mode));
$("#langBtn").onclick=()=>{lang=lang==='ar'?"en":"ar";localStorage.setItem("tofan_lang",lang);applyLang();setMode(mode);if(token)loadDashboard()};
$("#authForm").onsubmit=async e=>{e.preventDefault();$("#authError").textContent="";try{const body={email:$("#email").value,password:$("#password").value,device_id:"web"};if(mode==="register")body.display_name=$("#displayName").value;const d=await api("/auth/"+(mode==="login"?"login":"register"),{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});token=d.access_token;localStorage.setItem("tofan_token",token);loadDashboard()}catch(err){$("#authError").textContent=err.message}};
$("#passkeyLoginBtn").onclick=async()=>{try{
  if(!window.PublicKeyCredential||!navigator.credentials)throw new Error(lang==='ar'?"هذا الجهاز/المتصفح لا يدعم Passkey.":"This browser/device does not support passkeys.");
  const email=$("#email").value.trim();
  if(!email)throw new Error(t("passkeyLoginNeedEmail"));
  const d=await fetch("/auth/passkey/options",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({email})});
  const data=await d.json(); if(!d.ok)throw new Error(data.detail||"Passkey login failed.");
  const assertion=await navigator.credentials.get({publicKey:webauthnOptions(data.options.publicKey||data.options)});
  const complete=await fetch("/auth/passkey/complete",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({email,challenge_id:data.challenge_id,response:credentialJSON(assertion)})});
  const result=await complete.json(); if(!complete.ok)throw new Error(result.detail||"Passkey verification failed.");
  token=result.access_token;localStorage.setItem("tofan_token",token);toast(t("passkeyLoginDone"));await loadDashboard();
}catch(err){$("#authError").textContent=err.message}};
$("#logoutBtn").onclick=async()=>{try{await api("/auth/logout",{method:"POST"})}catch{}token=null;localStorage.removeItem("tofan_token");$("#dashboardView").classList.add("hidden");$("#authView").classList.remove("hidden");$("#logoutBtn").classList.add("hidden")};
function b64ToBuf(v){const s=String(v||"").replace(/-/g,"+").replace(/_/g,"/");const p=s+"=".repeat((4-s.length%4)%4);const bin=atob(p);return Uint8Array.from(bin,c=>c.charCodeAt(0)).buffer}
function bufToB64(v){const bytes=new Uint8Array(v);let s="";for(const b of bytes)s+=String.fromCharCode(b);return btoa(s).replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/,"")}
function webauthnOptions(value){if(!value||typeof value!=="object")return value;if(Array.isArray(value))return value.map(webauthnOptions);const out={...value};if(typeof out.challenge==="string")out.challenge=b64ToBuf(out.challenge);if(out.user&&typeof out.user==="object"&&typeof out.user.id==="string")out.user={...out.user,id:b64ToBuf(out.user.id)};for(const key of ["allowCredentials","excludeCredentials"]){if(Array.isArray(out[key]))out[key]=out[key].map(x=>({...x,id:typeof x.id==="string"?b64ToBuf(x.id):x.id}));}return out}
function credentialJSON(c){const r=c.response||{};const out={id:c.id,rawId:bufToB64(c.rawId),type:c.type,response:{}};for(const k of ["clientDataJSON","attestationObject","authenticatorData","signature","userHandle"]){if(r[k])out.response[k]=bufToB64(r[k]);}if(r.transports)out.response.transports=r.transports;return out}
async function completePasskeyRegistration(){
  if(!window.PublicKeyCredential||!navigator.credentials){throw new Error(lang==='ar'?"هذا الجهاز/المتصفح لا يدعم Passkey.":"This browser/device does not support passkeys.")}
  const d=await api("/student/profile/passkey/register/options?device_id="+encodeURIComponent("web-"+navigator.userAgent.slice(0,80)));
  const credential=await navigator.credentials.create({publicKey:webauthnOptions(d.options.publicKey||d.options)});
  await api("/student/profile/passkey/register/complete?challenge_id="+encodeURIComponent(d.challenge_id),{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({device_id:"web-"+navigator.userAgent.slice(0,80),response:credentialJSON(credential)})});
  const a=await api("/student/profile/passkey/authenticate/options");
  const assertion=await navigator.credentials.get({publicKey:webauthnOptions(a.options.publicKey||a.options)});
  const verified=await api("/student/profile/passkey/authenticate/complete",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({challenge_id:a.challenge_id,response:credentialJSON(assertion)})});
  return verified;
}
async function loadOnboardingState(){
  const d=await api("/student/onboarding");
  const panel=$("#onboardingPanel"), body=$("#onboardingBody");
  if(!panel||!body)return d;
  panel.classList.remove("hidden");
  $("#onboardingStep").textContent=d.step||"—";
  if(d.step==="academy_catalog"||d.step==="curriculum"||d.completed){
    body.innerHTML="<p class='success'>"+t("onboardingDone")+"</p>";
    return d;
  }
  if(d.step==="biometric_registration"||d.step==="biometric_authentication"){
    body.innerHTML="<p>"+(lang==='ar'?"تحقق من هويتك عبر مفتاح مرور آمن مرتبط بقفل جهازك.":"Verify your identity with a secure passkey protected by your device lock.")+"</p><button id='passkeyBtn' class='primary'>"+t(d.step==="biometric_registration"?"registerPasskey":"authenticatePasskey")+"</button>";
    $("#passkeyBtn").onclick=async()=>{try{if(d.step==="biometric_registration"){await completePasskeyRegistration()}else{const a=await api("/student/profile/passkey/authenticate/options");const assertion=await navigator.credentials.get({publicKey:webauthnOptions(a.options.publicKey||a.options)});await api("/student/profile/passkey/authenticate/complete",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({challenge_id:a.challenge_id,response:credentialJSON(assertion)})})}toast(t("passkeyDone"));loadDashboard()}catch(e){toast(e.message)}};
    return d;
  }
  if(d.step==="profile"){
    const p=await api("/student/profile");
    body.innerHTML="<form id='profileForm' class='onboarding-form'><label>"+t("userType")+"</label><select id='profileType'><option value='university_student'>"+t("universityStudent")+"</option><option value='independent_learner'>"+t("independentLearner")+"</option></select><label>"+t("fullName")+"</label><input id='profileName' required value='"+esc(p.profile?.full_name||"")+"'><label>"+t("age")+"</label><input id='profileAge' type='number' min='1' max='120' value='"+(p.profile?.age||"")+"'><div id='academicFields'><label>"+t("university")+"</label><select id='profileUniversity'><option value=''>"+t("select")+"</option></select><label>"+t("college")+"</label><select id='profileCollege' disabled><option value=''>"+t("select")+"</option></select><label>"+t("major")+"</label><select id='profileMajor' disabled><option value=''>"+t("select")+"</option></select></div><button class='primary' type='submit'>"+t("saveProfile")+"</button></form>";
    const type=$("#profileType"), acad=$("#academicFields"), uni=$("#profileUniversity"), college=$("#profileCollege"), major=$("#profileMajor");
    const fill=async(url,sel)=>{const d=await api(url);sel.innerHTML="<option value=''>"+t("select")+"</option>"+(d.items||[]).map(x=>"<option value='"+esc(x.id)+"'>"+esc(x.name)+"</option>").join("");sel.disabled=(d.items||[]).length===0};
    const loadUni=async()=>{await fill("/catalog/institutions",uni)};
    type.onchange=()=>{acad.classList.toggle("hidden",type.value!=="university_student");};
    await loadUni();
    uni.onchange=async()=>{college.innerHTML="<option value=''>"+t("select")+"</option>";major.innerHTML="<option value=''>"+t("select")+"</option>";major.disabled=true;if(uni.value){await fill("/catalog/institutions/"+encodeURIComponent(uni.value)+"/colleges",college)}};
    college.onchange=async()=>{major.innerHTML="<option value=''>"+t("select")+"</option>";major.disabled=true;if(uni.value&&college.value){await fill("/catalog/institutions/"+encodeURIComponent(uni.value)+"/majors?college_id="+encodeURIComponent(college.value),major)}};
    type.onchange();
    $("#profileForm").onsubmit=async e=>{e.preventDefault();try{if(type.value==="university_student"&&(!uni.value||!college.value||!major.value))throw new Error(lang==='ar'?"اختر الجامعة والكلية والتخصص.":"Select university, college, and specialization.");await api("/student/profile",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({user_type:type.value,full_name:$("#profileName").value.trim(),age:$("#profileAge").value?Number($("#profileAge").value):null,institution_id:type.value==="university_student"?uni.value:null,college_unit_id:type.value==="university_student"?college.value:null,major_unit_id:type.value==="university_student"?major.value:null})});toast(t("profileSaved"));loadDashboard()}catch(e){toast(e.message)}};
  }
  return d;
}

async function loadDashboard(){try{
  const [roles,sp]=await Promise.all([api("/users/me/roles"),api("/curriculum/specialties")]);
  isOwner=roles.some(x=>["owner","admin"].includes(x.role));
  $("#ownerNavBtn").classList.toggle("hidden",!isOwner);
  $("#ownerNavBtn").textContent=t("owner");
  $("#authView").classList.add("hidden");$("#dashboardView").classList.remove("hidden");$("#logoutBtn").classList.remove("hidden");
  let on=null;
  if(isOwner){
    $("#onboardingPanel").classList.add("hidden");
    $("#onboardingText").textContent=lang==="ar"?"تم التعرف على حساب المدير العام.":"General Manager account recognized.";
    $("#statAccess").textContent="OWNER";
    $("#statLearning").textContent="TOFAN CORE";
  }else{
    on=await api("/student/onboarding");
    $("#onboardingText").textContent=on.next_action||"";
    await loadOnboardingState();
    $("#statAccess").textContent=on.global_curriculum?.entitled?"ACTIVE":(on.step||"PENDING").toUpperCase();
    $("#statLearning").textContent="TOFAN CORE";
  }
  $("#statSpecialties").textContent=sp.length;
  renderSpecialties(sp);
}catch(err){token=null;localStorage.removeItem("tofan_token");$("#authView").classList.remove("hidden");toast(err.message)}}
async function renderSpecialties(items){
  const box=$("#specialties");box.innerHTML="";
  for(const s of items){
    let x;
    try{x=await api("/specialties/"+s.id+"/experience?lang="+lang)}catch{x={theme:{accent:"#c8a85b"},specialty:{name:s.name,description:s.description||""}}}
    const th=x.theme||{},name=(lang==='ar'?s.name_ar:s.name_en)||x.specialty?.name||s.name;
    const description=(lang==='ar'?s.description_ar:s.description_en)||x.specialty?.description||s.description||"";
    const card=document.createElement("article");card.className="specialty card";card.style.setProperty("--accent",th.accent||"#c8a85b");
    card.innerHTML="<div class='icon'>"+(th.icon||s.icon||"◆")+"</div><h3>"+name+"</h3><p>"+description+"</p><div class='modules'>"+(th.dashboard_modules||[]).slice(0,4).map(m=>"<span>"+m.replaceAll("_"," ")+"</span>").join("")+"</div>";
    card.onclick=()=>{currentSpecialty=s;openCurriculum(s.curriculum_slug)};
    box.appendChild(card)
  }
}
async function openCurriculum(slug){try{$("#coursePanel").classList.add("hidden");const curriculumSlug=slug||currentSpecialty?.curriculum_slug||"ai-tofan-curriculum-v1";const c=await api("/curriculum/"+encodeURIComponent(curriculumSlug));$("#curriculumPanel").classList.remove("hidden");$("#curriculumTitle").textContent=c.name+" · v"+c.version;const stages=c.stages||c.semesters||[];const byYear={};stages.forEach(s=>{const y=s.year||Math.ceil((s.position||1)/2);(byYear[y]??=[]).push(s)});$("#curriculumBody").innerHTML=Object.entries(byYear).map(([year,items])=>"<section class='year-group'><div class='section-head'><h2>"+(lang==='ar'?"السنة ":"Year ")+year+"</h2><span>"+items.length+" "+(lang==='ar'?"فصول":"semesters")+"</span></div>"+items.map(s=>"<div class='stage'><div class='stage-head'><h3>"+s.name+"</h3><span>"+(lang==='ar'?"الفصل ":"Semester ")+(s.semester||((s.position||1)%2||2))+"</span></div>"+(s.courses||[]).map(x=>"<button class='course course-button' data-course-id='"+esc(x.id)+"'><b>"+esc(x.code)+"</b> — "+esc(x.name)+" <small>"+(x.outcomes?.length||0)+" "+(lang==='ar'?"مخرجات تعلم":"outcomes")+"</small></button>").join("")+"</div>").join("")+"</section>").join("");$$$(".course-button").forEach(b=>b.onclick=()=>openCourse(b.dataset.courseId))}catch(err){toast(err.message)}}
async function openCourse(courseId){try{const c=await api("/curriculum/courses/"+encodeURIComponent(courseId));$("#curriculumPanel").classList.add("hidden");$("#coursePanel").classList.remove("hidden");$("#courseTitle").textContent=c.code+" — "+c.name;const type=c.course_type==="elective"?t("elective"):t("required");const prereq=c.prerequisite_course_ids?.length?c.prerequisite_course_ids.map(id=>"<span class='tag'>"+id+"</span>").join(""):"<span class='muted'>"+t("noPrereq")+"</span>";const outcomes=(c.outcomes||[]).map((x,i)=>"<li>"+x+"</li>").join("")||"<li>—</li>";const units=(c.units||[]).map(u=>"<section class='unit'><div class='unit-head'><div><span class='eyebrow'>"+t("units")+" "+u.position+"</span><h3>"+u.title+"</h3></div><span class='count'>"+u.lessons.length+" "+t("lessons")+"</span></div>"+(u.lessons.length?u.lessons.map(l=>"<button class='lesson-row lesson-button' data-lesson-id='"+l.id+"'><span>"+l.position+". "+l.title+"</span><span>"+(l.has_content?"●":"○")+"</span></button>").join(""):"<div class='muted'>"+t("noLessons")+"</div>")+"</section>").join("");$("#courseBody").innerHTML="<div class='course-meta'><span>"+type+"</span><span>"+t("courseType")+"</span></div><div class='detail-grid'><section><h3>"+t("outcomes")+"</h3><ol class='outcome-list'>"+outcomes+"</ol></section><section><h3>"+t("prerequisites")+"</h3><div class='tags'>"+prereq+"</div></section></div><div class='section-head'><h3>"+t("units")+"</h3></div>"+units+"<div class='teacher-entry'><p>"+t("lessonContent")+"</p><button class='primary' id='courseTeacherBtn'>"+t("openTeacher")+"</button></div>";const firstLesson=(c.units||[]).flatMap(u=>u.lessons||[])[0];$("#courseTeacherBtn").onclick=()=>firstLesson?openLesson(firstLesson.id,c):toast(t("noLessons"));if(!firstLesson)$("#courseTeacherBtn").disabled=true;
    const progress=await loadCourseProgress(c);
    if(c.access?.tier==="paid"){
      const payBtn=document.createElement("button");
      payBtn.className="secondary";
      payBtn.textContent=lang==='ar'?"طلب تفعيل الوصول المدفوع":"Request paid access";
      payBtn.onclick=()=>requestCurriculumPayment(c);
      const host=document.querySelector("#courseBody"); if(host) host.prepend(payBtn);
    }
    if(c.assessment?.id){
      const quizBtn=document.createElement("button");
      quizBtn.className="primary";
      quizBtn.id="courseQuizBtn";
      quizBtn.textContent=lang==='ar'?"بدء الاختبار النهائي":"Start final assessment";
      $("#courseBody").appendChild(quizBtn);
      quizBtn.onclick=()=>startCourseQuiz(c);
    }
    if(progress?.next_step?.action==="course_complete"){
      const certBtn=document.createElement("button");certBtn.className="secondary";certBtn.textContent=lang==='ar'?"إصدار شهادة المقرر":"Issue course certificate";$("#courseBody").appendChild(certBtn);
      certBtn.onclick=async()=>{certBtn.disabled=true;try{const cert=await api("/certificates/courses/"+encodeURIComponent(c.id)+"/issue",{method:"POST"});certBtn.textContent=(lang==='ar'?"تم إصدار الشهادة: ":"Certificate issued: ")+cert.certificate_number}catch(e){certBtn.disabled=false;toast(e.message)}};
    }
    $$(".lesson-button").forEach(b=>b.onclick=()=>openLesson(b.dataset.lessonId,c))}catch(err){toast(err.message)}}
$("#backCurriculum").onclick=()=>openCurriculum();
$("#backCourse").onclick=()=>{$("#lessonPanel").classList.add("hidden");$("#coursePanel").classList.remove("hidden")};
async function requestCurriculumPayment(c){
  const stageId=c.stage_id||c.stage?.id;
  if(!stageId){toast(lang==='ar'?"لا يمكن تحديد الفصل المطلوب للدفع":"The semester could not be identified.");return}
  try{
    const account=await api("/student/payments/account");
    if(!account.configured){toast(lang==='ar'?"حساب الدفع غير مُعد بعد من الإدارة.":"Payment account is not configured yet.");return}
    const amount=account.amount??"";
    const reference=prompt(lang==='ar'?"أدخل رقم العملية/المرجع بعد التحويل:":"Enter the transaction/reference number after transfer:");
    if(!reference?.trim()){toast(lang==='ar'?"يجب إدخال رقم العملية/المرجع.":"Transaction reference is required.");return}
    const input=document.createElement("input");input.type="file";input.accept="image/jpeg,image/png,image/webp,application/pdf";
    input.click();
    await new Promise((resolve,reject)=>{input.onchange=()=>input.files?.[0]?resolve():reject(new Error(lang==='ar'?"يجب اختيار إثبات الدفع.":"Payment proof is required."));});
    const result=await api("/student/payments/request",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({product_key:"curriculum_stage:"+stageId,reference:reference.trim()})});
    const form=new FormData();form.append("file",input.files[0]);
    await api("/student/payments/"+encodeURIComponent(result.transaction_id)+"/proof",{method:"POST",body:form});
    const message=lang==='ar'
      ?"المبلغ: "+amount+" "+(account.currency||"")+" — تم إرسال رقم العملية وإثبات الدفع للمالك للمراجعة."
      :"Amount: "+amount+" "+(account.currency||"")+" — transaction reference and payment proof were sent for owner review.";
    toast(message);
    return result;
  }catch(err){toast(err.message)}
}

async function loadCourseProgress(c){
  try{
    const p=await api("/learning-progress/courses/"+encodeURIComponent(c.id));
    const completed=p.completed_lessons||0, tracked=p.tracked_lessons||0, pct=Number(p.progress_percentage||0);
    const box=document.createElement("div"); box.className="course-progress-card";
    const title=document.createElement("strong"); title.textContent=lang==='ar'?"تقدمك في المقرر":"Your course progress";
    const meta=document.createElement("span"); meta.textContent=tracked?completed+" / "+tracked+" — "+pct+"%":(lang==='ar'?"لم يبدأ بعد":"Not started");
    const bar=document.createElement("div"); bar.className="progress-track";
    const fill=document.createElement("div"); fill.className="progress-fill"; fill.style.width=pct+"%"; bar.appendChild(fill);
    const current=document.createElement("p");
    const lessons=(c.units||[]).flatMap(u=>u.lessons||[]);
    current.textContent=p.next_step?.lesson_id
      ? (lang==='ar'?"الخطوة التالية: ":"Next step: ")+(lessons.find(l=>l.id===p.next_step.lesson_id)?.title||p.next_step.reason)
      : (p.next_step?.action==="course_complete"?(lang==='ar'?"المقرر مكتمل":"Course completed"):(lang==='ar'?"لم يبدأ بعد":"Not started"));
    box.append(title,meta,bar,current);
    const host=document.querySelector("#courseBody"); if(host) host.prepend(box);
    return p;
  }catch{return null}
}

async function startCourseQuiz(c){
  const assessment=c.assessment;
  if(!assessment?.id){toast(lang==='ar'?"لا يوجد اختبار مقرر لهذا المقرر":"No course assessment is configured.");return}
  try{
    if(!c.teacher?.slug){toast(t("teacherUnavailable"));return}
    const progress=await api("/agent/teacher/"+encodeURIComponent(c.teacher.slug)+"/progress");
    if(progress.total_steps && progress.completed_steps < progress.total_steps){
      toast(lang==='ar'?"أكمل جميع الدروس قبل فتح الاختبار النهائي":"Complete all lessons before opening the final assessment.");
      return;
    }
    let d;
    try{d=await api("/agent/teacher/"+encodeURIComponent(c.teacher.slug)+"/assessments/"+encodeURIComponent(assessment.id)+"/questions")}
    catch{d=await api("/agent/teacher/"+encodeURIComponent(c.teacher.slug)+"/assessments/"+encodeURIComponent(assessment.id)+"/generate",{method:"POST"})}
    const questions=d.questions||[];
    if(!questions.length){toast(lang==='ar'?"لم يتم إنشاء أسئلة الاختبار":"No assessment questions were generated.");return}
    $("#curriculumPanel").classList.add("hidden");$("#coursePanel").classList.add("hidden");$("#lessonPanel").classList.remove("hidden");
    $("#lessonTitle").textContent=assessment.title;
    const panel=$("#lessonBody");
    let index=0; const answers={};
    const render=()=>{
      const q=questions[index]; panel.innerHTML="";
      const wrap=document.createElement("div"); wrap.className="teacher-chat";
      const head=document.createElement("div"); head.className="lesson-meta"; head.textContent=(lang==='ar'?"السؤال":"Question")+" "+(index+1)+" / "+questions.length;
      const prompt=document.createElement("h3"); prompt.textContent=q.prompt;
      const options=document.createElement("div"); options.className="quiz-options";
      (q.options||[]).forEach(option=>{
        const label=document.createElement("label"); label.className="quiz-option";
        const input=document.createElement("input"); input.type="radio"; input.name="quiz-answer"; input.value=option; input.checked=answers[String(q.position)]===option;
        label.append(input,document.createTextNode(" "+option)); options.appendChild(label);
      });
      const next=document.createElement("button"); next.className="primary"; next.textContent=index===questions.length-1?(lang==='ar'?"إرسال الاختبار":"Submit assessment"):(lang==='ar'?"التالي":"Next");
      next.onclick=async()=>{
        const selected=panel.querySelector("input[name='quiz-answer']:checked");
        if(!selected){toast(lang==='ar'?"اختر إجابة أولاً":"Choose an answer first.");return}
        answers[String(q.position)]=selected.value;
        if(index<questions.length-1){index++;render();return}
        try{
          const result=await api("/agent/teacher/"+encodeURIComponent(c.teacher.slug)+"/assessments/"+encodeURIComponent(assessment.id)+"/submit",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({answers})});
          panel.innerHTML="";
          const resultBox=document.createElement("div"); resultBox.className="teacher-entry";
          resultBox.innerHTML="<h3>"+(lang==='ar'?"نتيجة الاختبار":"Assessment result")+"</h3>";
          const score=document.createElement("p"); score.textContent=(lang==='ar'?"النتيجة: ":"Score: ")+result.percentage+"% — "+(result.passed?(lang==='ar'?"ناجح":"Passed"):(lang==='ar'?"يحتاج إعادة":"Needs retry")); resultBox.appendChild(score);
          const details=document.createElement("div"); details.className="quiz-results";
          Object.values(result.details||{}).forEach(x=>{const p=document.createElement("p");p.textContent=(x.correct?"✓ ":"✗ ")+(x.correct?(lang==='ar'?"إجابة صحيحة":"Correct"):(lang==='ar'?"الإجابة الصحيحة: "+x.correct_answer:"Correct answer: "+x.correct_answer));details.appendChild(p)});
          resultBox.appendChild(details); panel.appendChild(resultBox);
          if(result.passed){
            try{
              const cert=await api("/certificates/courses/"+encodeURIComponent(c.id)+"/issue",{method:"POST"});
              const cp=document.createElement("p"); cp.textContent=(lang==='ar'?"تم إصدار الشهادة: ":"Certificate issued: ")+cert.certificate_number; resultBox.appendChild(cp);
            }catch(err){const cp=document.createElement("p");cp.textContent=err.message;resultBox.appendChild(cp)}
          }
          const back=document.createElement("button");back.className="primary";back.textContent=lang==='ar'?"العودة للمقرر":"Back to course";back.onclick=()=>openCourse(c.id);panel.appendChild(back);
        }catch(err){toast(err.message)}
      };
      wrap.append(head,prompt,options,next); panel.appendChild(wrap);
    };
    render();
  }catch(err){toast(err.message)}
}

async function openLesson(id,c){
  const unit=(c.units||[]).find(u=>(u.lessons||[]).some(l=>l.id===id));
  const lesson=unit?.lessons?.find(l=>l.id===id);
  if(!lesson){toast("Lesson not found");return}
  $("#curriculumPanel").classList.add("hidden");$("#coursePanel").classList.add("hidden");$("#lessonPanel").classList.remove("hidden");
  $("#lessonTitle").textContent=lesson.position+". "+lesson.title;
  try{
    const detail=await api("/curriculum/lessons/"+encodeURIComponent(id));
    const free=c.stage?.position===1;
    const content=detail.content_markdown||"";
    const body=content
      ? "<article class='lesson-content lesson-markdown'><div class='lesson-meta'><span>"+t("lesson")+" "+lesson.position+"</span><span>"+(free?t("freeSemester"):t("paidSemester"))+"</span></div><pre>"+esc(content)+"</pre></article>"
      : "<article class='lesson-content'><div class='lesson-meta'><span>"+t("lesson")+" "+lesson.position+"</span><span>"+(free?t("freeSemester"):t("paidSemester"))+"</span></div><p>"+(esc(detail.description||t("lessonContent")))+"</p></article>";
    const teacher=c.teacher||{};
    $("#lessonBody").innerHTML=body+"<div class='teacher-entry'><h3>"+t("teacher")+"</h3><p>"+(teacher.available?t("teacherReady"):t("teacherUnavailable"))+"</p><button class='primary' id='lessonTeacherBtn' "+(teacher.available?"":"disabled")+">"+t("openTeacher")+"</button></div>";
    $("#lessonTeacherBtn").onclick=()=>startTeaching(teacher.slug,lesson,c);
  }catch(e){
    toast(e.message);
  }
}

async function startTeaching(slug,lesson,c){
  if(!slug){toast(t("teacherUnavailable"));return}
  try{
    const unit=(c.units||[]).find(u=>(u.lessons||[]).some(l=>l.id===lesson.id));const position=(c.units||[]).slice(0,(c.units||[]).indexOf(unit)).reduce((n,u)=>n+(u.lessons||[]).length,0)+lesson.position;const step=await api("/agent/teacher/"+encodeURIComponent(slug)+"/teaching-steps",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({source:"global_curriculum",scope_key:"course:"+c.id+":unit:"+unit.id+":lesson:"+lesson.id,position})});
    await openTeacherChat(slug,step.id,lesson,c);
  }catch(e){toast(e.message)}
}
function speechLocale(){return lang==='ar'?"ar-SA":"en-US"}
function speakText(text){
  if(!voiceOutput||!("speechSynthesis" in window)||!String(text||"").trim())return;
  window.speechSynthesis.cancel();
  const u=new SpeechSynthesisUtterance(String(text).replace(/[*#_]+/g,""));
  u.lang=speechLocale();u.rate=0.95;u.pitch=1;
  const voices=window.speechSynthesis.getVoices();
  const exact=voices.find(v=>v.lang?.toLowerCase()===u.lang.toLowerCase());
  const family=voices.find(v=>v.lang?.toLowerCase().startsWith(lang==='ar'?"ar":"en"));
  if(exact||family)u.voice=exact||family;
  window.speechSynthesis.speak(u);
}
function stopSpeaking(){if("speechSynthesis" in window)window.speechSynthesis.cancel()}
function createVoiceControls(input,onVoiceText=null){
  const wrap=document.createElement("div");wrap.className="voice-controls";
  const mic=document.createElement("button");mic.type="button";mic.className="voice-btn";mic.textContent="🎙️";
  mic.title=lang==='ar'?"تحدث":"Speak";
  const speaker=document.createElement("button");speaker.type="button";speaker.className="voice-btn";speaker.textContent=voiceOutput?"🔊":"🔇";
  speaker.title=lang==='ar'?"الصوت: "+(voiceOutput?"مفعل":"متوقف"):"Voice output: "+(voiceOutput?"on":"off");
  const stop=document.createElement("button");stop.type="button";stop.className="voice-btn";stop.textContent="⏹";
  stop.title=lang==='ar'?"إيقاف الصوت":"Stop voice";
  wrap.append(mic,speaker,stop);
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!SR){mic.disabled=true;mic.title=lang==='ar'?"الإملاء الصوتي غير مدعوم في هذا المتصفح":"Speech input is not supported in this browser";mic.classList.add("disabled")}
  else{
    mic.onclick=()=>{
      if(speechListening){speechRecognition?.stop();return}
      speechRecognition=new SR();speechRecognition.lang=speechLocale();speechRecognition.interimResults=false;speechRecognition.continuous=false;
      speechRecognition.onstart=()=>{speechListening=true;mic.textContent="⏺";mic.classList.add("recording")};
      speechRecognition.onerror=e=>{speechListening=false;mic.textContent="🎙️";mic.classList.remove("recording");if(e.error!=="aborted")toast(lang==='ar'?"تعذر التقاط الصوت: "+e.error:"Voice input failed: "+e.error)};
      speechRecognition.onend=()=>{speechListening=false;mic.textContent="🎙️";mic.classList.remove("recording")};
      speechRecognition.onresult=e=>{const text=Array.from(e.results).map(r=>r[0]?.transcript||"").join(" ").trim();if(text){input.value=text;input.focus();if(typeof onVoiceText==="function")onVoiceText(text)}};
      speechRecognition.start();
    };
  }
  speaker.onclick=()=>{voiceOutput=!voiceOutput;localStorage.setItem("tofan_voice_output",voiceOutput?"on":"off");speaker.textContent=voiceOutput?"🔊":"🔇";if(!voiceOutput)stopSpeaking()};
  stop.onclick=stopSpeaking;
  return wrap;
}

async function openTeacherChat(slug,stepId,lesson,c){
  const panel=$("#lessonBody");
  panel.innerHTML=`<div class='teacher-chat'><h3>\${t("teacher")}</h3><div id='teacherMessages' class='chat-messages'></div><form id='teacherChatForm'><div class='voice-input-row'><input id='teacherInput' autocomplete='off' placeholder='\${lang==="ar"?"اكتب إجابتك أو تحدث…":"Write or speak…"}'><button class='primary voice-send' type='submit'>\${lang==="ar"?"إرسال":"Send"}</button></div><div id='teacherVoiceControls'></div><div class='voice-mode-row'><button type='button' class='ghost voice-mode' id='voiceModeBtn'>\${lang==="ar"?"🎧 الوضع الصوتي: متوقف":"🎧 Voice mode: Off"}</button><span id='voiceState' class='voice-state'>\${lang==="ar"?"يمكنك التحدث ثم الإرسال":"Speak, then send"}</span></div></form><div class='teacher-actions'><button class='ghost' id='verifyBtn'>\${lang==="ar"?"تحقق من الفهم":"Verify understanding"}</button><button class='ghost' id='confirmBtn'>\${lang==="ar"?"تأكيد فهم الدرس":"Confirm lesson understanding"}</button></div></div>`;
  const messages=$("#teacherMessages");
  const appendTeacherMessage=(role,content)=>{const node=document.createElement("div");node.className="chat-msg "+role;node.textContent=String(content??"");messages.appendChild(node);messages.scrollTop=messages.scrollHeight};
  const send=async(msg)=>{const d=await api("/agent/teacher/"+encodeURIComponent(slug)+"/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:msg,source:"global_curriculum"})});const text=d.content||d.output||"";appendTeacherMessage("assistant",text);speakText(text);return d};
  const teacherInput=$("#teacherInput");let voiceMode=false;let voiceSending=false;
  const voiceState=$("#voiceState"),voiceModeBtn=$("#voiceModeBtn");
  const updateVoiceMode=()=>{voiceModeBtn.textContent=lang==='ar'?"🎧 الوضع الصوتي: "+(voiceMode?"مفعل":"متوقف"):"🎧 Voice mode: "+(voiceMode?"On":"Off");voiceState.textContent=voiceMode?(lang==='ar'?"تحدث الآن — سيتم إرسال كلامك تلقائيًا":"Speak now — your transcript will send automatically"):(lang==='ar'?"يمكنك التحدث ثم الإرسال":"Speak, then send")};
  voiceModeBtn.onclick=()=>{voiceMode=!voiceMode;updateVoiceMode();if(voiceMode&&window.speechSynthesis)stopSpeaking()};
  const submitVoiceText=async text=>{if(!voiceMode||voiceSending)return;const msg=String(text||"").trim();if(!msg)return;voiceSending=true;appendTeacherMessage("user",msg);teacherInput.value="";voiceState.textContent=lang==='ar'?"جارٍ إرسال رسالتك…":"Sending your message…";try{await send(msg)}catch(err){toast(err.message)}finally{voiceSending=false;updateVoiceMode()}};
  $("#teacherVoiceControls").appendChild(createVoiceControls(teacherInput,submitVoiceText));
  $("#teacherChatForm").onsubmit=async e=>{e.preventDefault();const input=$("#teacherInput");const msg=input.value.trim();if(!msg)return;appendTeacherMessage("user",msg);input.value="";try{await send(msg)}catch(err){toast(err.message)}};
  $("#verifyBtn").onclick=async()=>{try{const d=await api("/agent/teacher/"+encodeURIComponent(slug)+"/teaching-steps/"+encodeURIComponent(stepId)+"/understanding",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({verified:true})});toast(d.status==="completed"?t("teacherReady"):(lang==='ar'?"تم تسجيل تحقق الفهم":"Understanding check recorded"))}catch(e){toast(e.message)}};
  $("#confirmBtn").onclick=async()=>{try{const d=await api("/agent/teacher/"+encodeURIComponent(slug)+"/teaching-steps/"+encodeURIComponent(stepId)+"/confirm",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({confirmed:true})});toast(d.completed?(lang==='ar'?"تم إكمال الدرس":"Lesson completed"):(lang==='ar'?"تم تسجيل التأكيد":"Confirmation recorded"));if(d.completed){openCourse(c.id)}}catch(e){toast(e.message)}};
}

$("#closeCurriculum").onclick=()=>$("#curriculumPanel").classList.add("hidden");
async function loadNotifications(){
  try{
    $("#curriculumPanel").classList.add("hidden");$("#coursePanel").classList.add("hidden");$("#lessonPanel").classList.add("hidden");$("#ownerPanel").classList.add("hidden");$("#notificationsPanel").classList.remove("hidden");
    const d=await api("/notifications?limit=50");
    const box=$("#notificationsBody");
    if(!box)return;
    const items=d.notifications||[];
    box.innerHTML=items.length?items.map(n=>"<article class='notification-item "+(n.is_read?"":"unread")+"'><div><b>"+esc(n.title||"")+"</b><p>"+esc(n.message||"")+"</p><small>"+esc(n.created_at||"")+"</small></div>"+(n.is_read?"":"<button class='ghost notification-read' data-id='"+esc(n.id)+"'>"+t("markRead")+"</button>")+"</article>").join(""):"<div class='detail-item'>"+(lang==='ar'?"لا توجد إشعارات.":"No notifications.")+"</div>";
    $$$(".notification-read").forEach(btn=>btn.onclick=async()=>{try{await api("/notifications/"+encodeURIComponent(btn.dataset.id)+"/read",{method:"POST"});loadNotifications()}catch(e){toast(e.message)}});
  }catch(e){toast(e.message)}
}
$("#refreshNotifications").onclick=()=>loadNotifications();

async function loadProgress(){try{const d=await api("/learning-progress/courses");$("#curriculumPanel").classList.remove("hidden");$("#coursePanel").classList.add("hidden");$("#curriculumTitle").textContent=t("progress");$("#curriculumBody").innerHTML=(d.courses||[]).map(x=>"<div class='detail-item'><b>"+x.course.name+"</b><span>"+(x.progress_percentage||0)+"%</span><div class='progressbar'><i style='width:"+(x.progress_percentage||0)+"%'></i></div></div>").join("")}catch(e){toast(e.message)}}
async function loadCertificates(){try{const d=await api("/certificates");$("#curriculumPanel").classList.remove("hidden");$("#coursePanel").classList.add("hidden");$("#curriculumTitle").textContent=t("certificates");$("#curriculumBody").innerHTML=d.certificates?.length?d.certificates.map(x=>"<div class='certificate'><b>"+x.title+"</b><div>"+x.certificate_number+"</div></div>").join(""):"<div class='detail-item'>No certificates yet.</div>"}catch(e){toast(e.message)}}
async function loadProfile(){try{const d=await api("/student/onboarding");$("#curriculumPanel").classList.remove("hidden");$("#coursePanel").classList.add("hidden");$("#curriculumTitle").textContent=t("profile");$("#curriculumBody").innerHTML="<div class='metric-grid'><div class='metric'><span>Status</span><b>"+(d.profile?.status||d.step||"—")+"</b></div><div class='metric'><span>Passkey</span><b>"+(d.passkey?.registered?"✓":"—")+"</b></div><div class='metric'><span>Access</span><b>"+(d.global_curriculum?.entitled?"ACTIVE":"PENDING")+"</b></div></div>"}catch(e){toast(e.message)}}
applyLang();if(token)loadDashboard();
async function openOwnerManager(){
  if(!isOwner)return;
  $("#curriculumPanel").classList.add("hidden");$("#coursePanel").classList.add("hidden");$("#lessonPanel").classList.add("hidden");$("#ownerPanel").classList.remove("hidden");
}
$("#ownerChatForm").onsubmit=async e=>{
  e.preventDefault();if(!isOwner)return;
  const input=$("#ownerInput"),box=$("#ownerMessages"),msg=input.value.trim();if(!msg)return;
  const appendMessage=(role,content)=>{const node=document.createElement("div");node.className="chat-msg "+role;node.textContent=String(content??"");box.appendChild(node);box.scrollTop=box.scrollHeight};
  appendMessage("user",msg);input.value="";
  try{
    const d=await api("/admin/agent/tofan-main/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:msg})});
    const content=d.content||d.output||JSON.stringify(d);
    appendMessage("assistant",content);
  }catch(err){appendMessage("assistant","تعذر تنفيذ الطلب: "+err.message)}
};