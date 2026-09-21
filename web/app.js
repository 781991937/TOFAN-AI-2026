const I18N={ar:{academy:"الأكاديمية الذكية",heroTitle:"أكاديميتك الذكية للتعلّم المتدرّج",heroText:"منهج عالمي، معلّمون بالذكاء الاصطناعي، تقدّم محفوظ، واختبارات مرتبطة بمخرجات التعلّم.",login:"تسجيل الدخول",register:"إنشاء حساب",email:"البريد الإلكتروني",password:"كلمة المرور",name:"الاسم",logout:"تسجيل الخروج",learning:"التعلّم",specialties:"التخصصات",access:"الوصول",specialtyTitle:"مسارات التخصص",dynamic:"واجهة تتكيّف مع تخصصك",home:"الرئيسية",curriculum:"المنهج",progress:"التقدم",certificates:"الشهادات",profile:"الملف",back:"العودة",outcomes:"مخرجات التعلّم",prerequisites:"المتطلبات السابقة",units:"الوحدات",lessons:"الدروس",start:"فتح المقرر",noPrereq:"لا توجد متطلبات سابقة مسجلة.",noLessons:"لا توجد دروس مسجلة في هذه الوحدة.",courseType:"نوع المقرر",required:"إلزامي",elective:"اختياري",lessonContent:"محتوى الدرس متاح عبر المعلّم الذكي بعد بدء الخطوة التعليمية.",openTeacher:"بدء التعلّم مع المعلّم الذكي",openLesson:"فتح الدرس",lesson:"الدرس",teacher:"المعلّم الذكي",teacherReady:"المعلّم الذكي مرتبط بالمقرر ويمكن تشغيله من هنا.",freeSemester:"الفصل الأول من السنة الأولى مجاني",paidSemester:"هذا المحتوى ضمن الوصول المدفوع",teacherUnavailable:"المعلّم الذكي لهذا المقرر غير مفعّل بعد."},en:{academy:"Smart Academy",heroTitle:"Your intelligent academy for mastery-based learning",heroText:"Global knowledge, AI teachers, persistent progress, and assessments tied to learning outcomes.",login:"Sign in",register:"Create account",email:"Email",password:"Password",name:"Name",logout:"Sign out",learning:"Learning",specialties:"Specialties",access:"Access",specialtyTitle:"Specialty paths",dynamic:"An experience that adapts to your specialty",home:"Home",curriculum:"Curriculum",progress:"Progress",certificates:"Certificates",profile:"Profile",back:"Back",outcomes:"Learning outcomes",prerequisites:"Prerequisites",units:"Units",lessons:"Lessons",start:"Open course",noPrereq:"No prerequisites recorded.",noLessons:"No lessons are registered in this unit.",courseType:"Course type",required:"Required",elective:"Elective",lessonContent:"Lesson content is delivered through the smart teacher after the learning step begins.",openTeacher:"Start learning with the smart teacher",openLesson:"Open lesson",lesson:"Lesson",teacher:"AI Teacher",teacherReady:"The AI teacher is linked to this course and can be started here.",freeSemester:"Year 1 · Semester 1 is free",paidSemester:"This content is part of paid access",teacherUnavailable:"The AI teacher for this course is not active yet."}};
let lang=localStorage.getItem("tofan_lang")||"ar",mode="login",token=localStorage.getItem("tofan_token"),isOwner=false;
const $=s=>document.querySelector(s),$$=s=>document.querySelectorAll(s);
I18N.ar.owner="المدير العام";I18N.en.owner="General Manager";function t(k){return I18N[lang][k]||k}
function applyLang(){document.documentElement.lang=lang;document.documentElement.dir=lang==="ar"?"rtl":"ltr";document.body.classList.toggle("en",lang==="en");$$("[data-i18n]").forEach(e=>e.textContent=t(e.dataset.i18n));$("#langBtn").textContent=lang==="ar"?"EN":"AR"}
function toast(m){$("#toast").textContent=m;$("#toast").classList.add("show");setTimeout(()=>$("#toast").classList.remove("show"),2600)}
async function api(path,opt={}){opt.headers={...(opt.headers||{}),...(token?{"Authorization":"Bearer "+token}:{})};const r=await fetch(path,opt);let d={};try{d=await r.json()}catch{}if(!r.ok)throw new Error(d.detail||"Request failed");return d}
function showView(view){$(".nav-btn").forEach(b=>b.classList.toggle("active",b.dataset.view===view));$("#coursePanel").classList.add("hidden");$("#lessonPanel").classList.add("hidden");$("#ownerPanel").classList.add("hidden");if(view==="home"){$("#curriculumPanel").classList.add("hidden");return}if(view==="curriculum")openCurriculum();if(view==="progress")loadProgress();if(view==="certificates")loadCertificates();if(view==="profile")loadProfile();if(view==="owner"&&isOwner)openOwnerManager()}
$$(".nav-btn").forEach(b=>b.onclick=()=>showView(b.dataset.view));
function setMode(m){mode=m;$$(".tab").forEach(x=>x.classList.toggle("active",x.dataset.mode===m));$("#nameWrap").classList.toggle("hidden",m!=="register");$("#authSubmit").textContent=t(m==="login"?"login":"register");$("#authError").textContent=""}
$$(".tab").forEach(x=>x.onclick=()=>setMode(x.dataset.mode));
$("#langBtn").onclick=()=>{lang=lang==="ar"?"en":"ar";localStorage.setItem("tofan_lang",lang);applyLang();setMode(mode);if(token)loadDashboard()};
$("#authForm").onsubmit=async e=>{e.preventDefault();$("#authError").textContent="";try{const body={email:$("#email").value,password:$("#password").value,device_id:"web"};if(mode==="register")body.display_name=$("#displayName").value;const d=await api("/auth/"+(mode==="login"?"login":"register"),{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});token=d.access_token;localStorage.setItem("tofan_token",token);loadDashboard()}catch(err){$("#authError").textContent=err.message}};
$("#logoutBtn").onclick=async()=>{try{await api("/auth/logout",{method:"POST"})}catch{}token=null;localStorage.removeItem("tofan_token");$("#dashboardView").classList.add("hidden");$("#authView").classList.remove("hidden");$("#logoutBtn").classList.add("hidden")};
async function loadDashboard(){try{const [on,sp,roles]=await Promise.all([api("/student/onboarding"),api("/curriculum/specialties"),api("/users/me/roles")]);isOwner=roles.some(x=>["owner","admin"].includes(x.role));$("#ownerNavBtn").classList.toggle("hidden",!isOwner);$("#ownerNavBtn").textContent=t("owner");$("#authView").classList.add("hidden");$("#dashboardView").classList.remove("hidden");$("#logoutBtn").classList.remove("hidden");$("#onboardingText").textContent=on.next_action||"";$("#statSpecialties").textContent=sp.length;$("#statAccess").textContent=on.global_curriculum?.entitled?"ACTIVE":(on.step||"PENDING").toUpperCase();$("#statLearning").textContent="TOFAN CORE";renderSpecialties(sp)}catch(err){token=null;localStorage.removeItem("tofan_token");$("#authView").classList.remove("hidden");toast(err.message)}}
async function renderSpecialties(items){const box=$("#specialties");box.innerHTML="";for(const s of items){let x;try{x=await api("/specialties/"+s.id+"/experience?lang="+lang)}catch{x={theme:{accent:"#c8a85b"},specialty:{name:s.name,description:""}}}const th=x.theme||{},name=x.specialty?.name||s.name;const card=document.createElement("article");card.className="specialty card";card.style.setProperty("--accent",th.accent||"#c8a85b");card.innerHTML="<div class='icon'>"+(th.icon||"◆")+"</div><h3>"+name+"</h3><p>"+(x.specialty?.description||"")+"</p><div class='modules'>"+(th.dashboard_modules||[]).slice(0,4).map(m=>"<span>"+m.replaceAll("_"," ")+"</span>").join("")+"</div>";card.onclick=()=>openCurriculum();box.appendChild(card)}}
async function openCurriculum(){try{$("#coursePanel").classList.add("hidden");const c=await api("/curriculum/ai-tofan-curriculum-v1");$("#curriculumPanel").classList.remove("hidden");$("#curriculumTitle").textContent=c.name+" · v"+c.version;$("#curriculumBody").innerHTML=c.stages.map(s=>"<div class='stage'><h3>"+s.name+"</h3>"+s.courses.map(x=>"<button class='course course-button' data-course-id='"+x.id+"'><b>"+x.code+"</b> — "+x.name+" <small>"+(x.outcomes?.length||0)+" outcomes</small></button>").join("")+"</div>").join("");$$(".course-button").forEach(b=>b.onclick=()=>openCourse(b.dataset.courseId))}catch(err){toast(err.message)}}
async function openCourse(courseId){try{const c=await api("/curriculum/courses/"+encodeURIComponent(courseId));$("#curriculumPanel").classList.add("hidden");$("#coursePanel").classList.remove("hidden");$("#courseTitle").textContent=c.code+" — "+c.name;const type=c.course_type==="elective"?t("elective"):t("required");const prereq=c.prerequisite_course_ids?.length?c.prerequisite_course_ids.map(id=>"<span class='tag'>"+id+"</span>").join(""):"<span class='muted'>"+t("noPrereq")+"</span>";const outcomes=(c.outcomes||[]).map((x,i)=>"<li>"+x+"</li>").join("")||"<li>—</li>";const units=(c.units||[]).map(u=>"<section class='unit'><div class='unit-head'><div><span class='eyebrow'>"+t("units")+" "+u.position+"</span><h3>"+u.title+"</h3></div><span class='count'>"+u.lessons.length+" "+t("lessons")+"</span></div>"+(u.lessons.length?u.lessons.map(l=>"<button class='lesson-row lesson-button' data-lesson-id='"+l.id+"'><span>"+l.position+". "+l.title+"</span><span>"+(l.has_content?"●":"○")+"</span></button>").join(""):"<div class='muted'>"+t("noLessons")+"</div>")+"</section>").join("");$("#courseBody").innerHTML="<div class='course-meta'><span>"+type+"</span><span>"+t("courseType")+"</span></div><div class='detail-grid'><section><h3>"+t("outcomes")+"</h3><ol class='outcome-list'>"+outcomes+"</ol></section><section><h3>"+t("prerequisites")+"</h3><div class='tags'>"+prereq+"</div></section></div><div class='section-head'><h3>"+t("units")+"</h3></div>"+units+"<div class='teacher-entry'><p>"+t("lessonContent")+"</p><button class='primary' id='courseTeacherBtn'>"+t("openTeacher")+"</button></div>";$("#courseTeacherBtn").onclick=()=>toast(t("teacherReady"));
    await loadCourseProgress(c);
    if(c.access?.tier==="paid"){
      const payBtn=document.createElement("button");
      payBtn.className="secondary";
      payBtn.textContent=lang==="ar"?"طلب تفعيل الوصول المدفوع":"Request paid access";
      payBtn.onclick=()=>requestCurriculumPayment(c);
      const host=document.querySelector("#courseBody"); if(host) host.prepend(payBtn);
    }
    if(c.assessment?.id){
      const quizBtn=document.createElement("button");
      quizBtn.className="primary";
      quizBtn.id="courseQuizBtn";
      quizBtn.textContent=lang==="ar"?"بدء الاختبار النهائي":"Start final assessment";
      $("#courseBody").appendChild(quizBtn);
      quizBtn.onclick=()=>startCourseQuiz(c);
    }
    $(".lesson-button").forEach(b=>b.onclick=()=>openLesson(b.dataset.lessonId,c))}catch(err){toast(err.message)}}
$("#backCurriculum").onclick=()=>openCurriculum();
$("#backCourse").onclick=()=>{$("#lessonPanel").classList.add("hidden");$("#coursePanel").classList.remove("hidden")};
async function requestCurriculumPayment(c){
  const stageId=c.stage_id||c.stage?.id;
  if(!stageId){toast(lang==="ar"?"لا يمكن تحديد الفصل المطلوب للدفع":"The semester could not be identified.");return}
  try{
    const account=await api("/student/payments/account");
    if(!account.configured){toast(lang==="ar"?"حساب الدفع غير مُعد بعد من الإدارة.":"Payment account is not configured yet.");return}
    const amount=account.amount??"";
    const reference=prompt(lang==="ar"?"أدخل رقم العملية/المرجع بعد التحويل:":"Enter the transaction/reference number after transfer:");
    if(!reference?.trim()){toast(lang==="ar"?"يجب إدخال رقم العملية/المرجع.":"Transaction reference is required.");return}
    const input=document.createElement("input");input.type="file";input.accept="image/jpeg,image/png,image/webp,application/pdf";
    input.click();
    await new Promise((resolve,reject)=>{input.onchange=()=>input.files?.[0]?resolve():reject(new Error(lang==="ar"?"يجب اختيار إثبات الدفع.":"Payment proof is required."));});
    const result=await api("/student/payments/request",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({product_key:"curriculum_stage:"+stageId,reference:reference.trim()})});
    const form=new FormData();form.append("file",input.files[0]);
    await api("/student/payments/"+encodeURIComponent(result.transaction_id)+"/proof",{method:"POST",body:form});
    const message=lang==="ar"
      ?"المبلغ: "+amount+" "+(account.currency||"")+" — تم إرسال رقم العملية وإثبات الدفع للمالك للمراجعة."
      :"Amount: "+amount+" "+(account.currency||"")+" — transaction reference and payment proof were sent for owner review.";
    toast(message);
    return result;
  }catch(err){toast(err.message)}
}

async function loadCourseProgress(c){
  if(!c.teacher?.slug) return null;
  try{
    const p=await api("/agent/teacher/"+encodeURIComponent(c.teacher.slug)+"/progress");
    const box=document.createElement("div"); box.className="course-progress-card";
    const title=document.createElement("strong"); title.textContent=lang==="ar"?"تقدمك في المقرر":"Your course progress";
    const meta=document.createElement("span"); meta.textContent=(p.completed_steps||0)+" / "+(p.total_steps||0)+" — "+(p.progress_percentage||0)+"%";
    const bar=document.createElement("div"); bar.className="progress-track";
    const fill=document.createElement("div"); fill.className="progress-fill"; fill.style.width=(p.progress_percentage||0)+"%"; bar.appendChild(fill);
    const current=document.createElement("p"); current.textContent=p.current_step?.lesson_title ? (lang==="ar"?"الدرس الحالي: ":"Current lesson: ")+p.current_step.lesson_title : (p.course_completed?(lang==="ar"?"المقرر مكتمل":"Course completed"):(lang==="ar"?"لم يبدأ بعد":"Not started"));
    box.append(title,meta,bar,current);
    const host=document.querySelector("#courseBody"); if(host) host.prepend(box);
    return p;
  }catch{return null}
}

async function startCourseQuiz(c){
  const assessment=c.assessment;
  if(!assessment?.id){toast(lang==="ar"?"لا يوجد اختبار مقرر لهذا المقرر":"No course assessment is configured.");return}
  try{
    if(!c.teacher?.slug){toast(t("teacherUnavailable"));return}
    const progress=await api("/agent/teacher/"+encodeURIComponent(c.teacher.slug)+"/progress");
    if(progress.total_steps && progress.completed_steps < progress.total_steps){
      toast(lang==="ar"?"أكمل جميع الدروس قبل فتح الاختبار النهائي":"Complete all lessons before opening the final assessment.");
      return;
    }
    let d;
    try{d=await api("/agent/teacher/"+encodeURIComponent(c.teacher.slug)+"/assessments/"+encodeURIComponent(assessment.id)+"/questions")}
    catch{d=await api("/agent/teacher/"+encodeURIComponent(c.teacher.slug)+"/assessments/"+encodeURIComponent(assessment.id)+"/generate",{method:"POST"})}
    const questions=d.questions||[];
    if(!questions.length){toast(lang==="ar"?"لم يتم إنشاء أسئلة الاختبار":"No assessment questions were generated.");return}
    $("#curriculumPanel").classList.add("hidden");$("#coursePanel").classList.add("hidden");$("#lessonPanel").classList.remove("hidden");
    $("#lessonTitle").textContent=assessment.title;
    const panel=$("#lessonBody");
    let index=0; const answers={};
    const render=()=>{
      const q=questions[index]; panel.innerHTML="";
      const wrap=document.createElement("div"); wrap.className="teacher-chat";
      const head=document.createElement("div"); head.className="lesson-meta"; head.textContent=(lang==="ar"?"السؤال":"Question")+" "+(index+1)+" / "+questions.length;
      const prompt=document.createElement("h3"); prompt.textContent=q.prompt;
      const options=document.createElement("div"); options.className="quiz-options";
      (q.options||[]).forEach(option=>{
        const label=document.createElement("label"); label.className="quiz-option";
        const input=document.createElement("input"); input.type="radio"; input.name="quiz-answer"; input.value=option; input.checked=answers[String(q.position)]===option;
        label.append(input,document.createTextNode(" "+option)); options.appendChild(label);
      });
      const next=document.createElement("button"); next.className="primary"; next.textContent=index===questions.length-1?(lang==="ar"?"إرسال الاختبار":"Submit assessment"):(lang==="ar"?"التالي":"Next");
      next.onclick=async()=>{
        const selected=panel.querySelector("input[name='quiz-answer']:checked");
        if(!selected){toast(lang==="ar"?"اختر إجابة أولاً":"Choose an answer first.");return}
        answers[String(q.position)]=selected.value;
        if(index<questions.length-1){index++;render();return}
        try{
          const result=await api("/agent/teacher/"+encodeURIComponent(c.teacher.slug)+"/assessments/"+encodeURIComponent(assessment.id)+"/submit",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({answers})});
          panel.innerHTML="";
          const resultBox=document.createElement("div"); resultBox.className="teacher-entry";
          resultBox.innerHTML="<h3>"+(lang==="ar"?"نتيجة الاختبار":"Assessment result")+"</h3>";
          const score=document.createElement("p"); score.textContent=(lang==="ar"?"النتيجة: ":"Score: ")+result.percentage+"% — "+(result.passed?(lang==="ar"?"ناجح":"Passed"):(lang==="ar"?"يحتاج إعادة":"Needs retry")); resultBox.appendChild(score);
          const details=document.createElement("div"); details.className="quiz-results";
          Object.values(result.details||{}).forEach(x=>{const p=document.createElement("p");p.textContent=(x.correct?"✓ ":"✗ ")+(x.correct?(lang==="ar"?"إجابة صحيحة":"Correct"):(lang==="ar"?"الإجابة الصحيحة: "+x.correct_answer:"Correct answer: "+x.correct_answer));details.appendChild(p)});
          resultBox.appendChild(details); panel.appendChild(resultBox);
          if(result.passed){
            try{
              const cert=await api("/certificates/courses/"+encodeURIComponent(c.id)+"/issue",{method:"POST"});
              const cp=document.createElement("p"); cp.textContent=(lang==="ar"?"تم إصدار الشهادة: ":"Certificate issued: ")+cert.certificate_number; resultBox.appendChild(cp);
            }catch(err){const cp=document.createElement("p");cp.textContent=err.message;resultBox.appendChild(cp)}
          }
          const back=document.createElement("button");back.className="primary";back.textContent=lang==="ar"?"العودة للمقرر":"Back to course";back.onclick=()=>openCourse(c.id);panel.appendChild(back);
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
  const free=c.stage?.position===1;
  let teacher=c.teacher||{};
  $("#lessonBody").innerHTML="<div class='lesson-meta'><span>"+t("lesson")+" "+lesson.position+"</span><span>"+(free?t("freeSemester"):t("paidSemester"))+"</span></div><article class='lesson-content'><p>"+(lesson.description||t("lessonContent"))+"</p></article><div class='teacher-entry'><h3>"+t("teacher")+"</h3><p>"+(teacher.available?t("teacherReady"):t("teacherUnavailable"))+"</p><button class='primary' id='lessonTeacherBtn' "+(teacher.available?"":"disabled")+">"+t("openTeacher")+"</button></div>";
  $("#lessonTeacherBtn").onclick=()=>startTeaching(teacher.slug,lesson,c);
}

async function startTeaching(slug,lesson,c){
  if(!slug){toast(t("teacherUnavailable"));return}
  try{
    const unit=(c.units||[]).find(u=>(u.lessons||[]).some(l=>l.id===lesson.id));const position=(c.units||[]).slice(0,(c.units||[]).indexOf(unit)).reduce((n,u)=>n+(u.lessons||[]).length,0)+lesson.position;const step=await api("/agent/teacher/"+encodeURIComponent(slug)+"/teaching-steps",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({source:"global_curriculum",scope_key:"course:"+c.id+":unit:"+unit.id+":lesson:"+lesson.id,position})});
    await openTeacherChat(slug,step.id,lesson,c);
  }catch(e){toast(e.message)}
}
async function openTeacherChat(slug,stepId,lesson,c){
  const panel=$("#lessonBody");
  panel.innerHTML="<div class='teacher-chat'><h3>"+t("teacher")+"</h3><div id='teacherMessages' class='chat-messages'></div><form id='teacherChatForm'><input id='teacherInput' autocomplete='off' placeholder='"+(lang==="ar"?"اكتب إجابتك أو سؤالك…":"Write your answer or question…")+"'><button class='primary' type='submit'>"+(lang==="ar"?"إرسال":"Send")+"</button></form><div class='teacher-actions'><button class='ghost' id='verifyBtn'>"+(lang==="ar"?"تحقق من الفهم":"Verify understanding")+"</button><button class='ghost' id='confirmBtn'>"+(lang==="ar"?"تأكيد فهم الدرس":"Confirm lesson understanding")+"</button></div></div>";
  const messages=$("#teacherMessages");
  const appendTeacherMessage=(role,content)=>{const node=document.createElement("div");node.className="chat-msg "+role;node.textContent=String(content??"");messages.appendChild(node);messages.scrollTop=messages.scrollHeight};
  const send=async(msg)=>{const d=await api("/agent/teacher/"+encodeURIComponent(slug)+"/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:msg,source:"global_curriculum"})});const text=d.content||d.output||"";appendTeacherMessage("assistant",text);return d};
  $("#teacherChatForm").onsubmit=async e=>{e.preventDefault();const input=$("#teacherInput");const msg=input.value.trim();if(!msg)return;appendTeacherMessage("user",msg);input.value="";try{await send(msg)}catch(err){toast(err.message)}};
  $("#verifyBtn").onclick=async()=>{try{const d=await api("/agent/teacher/"+encodeURIComponent(slug)+"/teaching-steps/"+encodeURIComponent(stepId)+"/understanding",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({verified:true})});toast(d.status==="completed"?t("teacherReady"):(lang==="ar"?"تم تسجيل تحقق الفهم":"Understanding check recorded"))}catch(e){toast(e.message)}};
  $("#confirmBtn").onclick=async()=>{try{const d=await api("/agent/teacher/"+encodeURIComponent(slug)+"/teaching-steps/"+encodeURIComponent(stepId)+"/confirm",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({confirmed:true})});toast(d.completed?(lang==="ar"?"تم إكمال الدرس":"Lesson completed"):(lang==="ar"?"تم تسجيل التأكيد":"Confirmation recorded"));if(d.completed){openCourse(c.id)}}catch(e){toast(e.message)}};
}

$("#closeCurriculum").onclick=()=>$("#curriculumPanel").classList.add("hidden");
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
  const input=$("#ownerInput"),msg=input.value.trim();if(!msg)return;
  const appendMessage=(role,content)=>{const node=document.createElement("div");node.className="chat-msg "+role;node.textContent=String(content??"");box.appendChild(node);box.scrollTop=box.scrollHeight};
  appendMessage("user",msg);input.value="";
  try{
    const d=await api("/admin/agent/tofan-main/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:msg})});
    const content=d.content||d.output||JSON.stringify(d);
    appendMessage("assistant",content);
  }catch(err){appendMessage("assistant","تعذر تنفيذ الطلب: "+err.message)}
};