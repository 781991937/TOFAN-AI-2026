(()=> {
  const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
  const body=()=>document.getElementById("filesBody");
  async function loadStudentFiles(){
    const panel=document.getElementById("filesPanel"),b=body();
    if(!panel||!b)return;
    panel.classList.remove("hidden");
    try{
      const [files,teachers]=await Promise.all([api("/student/files"),api("/student/files/teachers")]);
      b.innerHTML='<div class="subscription-card"><h3>رفع ملف للدراسة</h3><p>PDF أو DOCX أو TXT. اختر المدرس الذكي المرتبط بالمقرر. بعد الرفع تبدأ دورة الشرح والفهم ثم الاختبار المجاني.</p><select id="fileTeacher"><option value="">اختر المدرس</option>'+teachers.teachers.map(t=>'<option value="'+esc(t.slug)+'">'+esc(t.name)+'</option>').join("")+'</select><input id="studentUpload" type="file" accept=".pdf,.docx,.txt" style="margin-top:10px"><button id="uploadStudentFile" class="primary">رفع الملف</button><div id="fileUploadState" class="muted"></div></div><h3>مكتبة الملفات</h3>'+(files.files?.length?files.files.map(f=>'<div class="detail-item"><b>'+esc(f.original_name)+'</b><div class="muted">'+Number(f.size_bytes||0).toLocaleString()+' bytes · '+esc(f.uploaded_at)+'</div><div style="margin-top:8px"><button class="primary file-teach" data-file="'+esc(f.file_id)+'" data-teacher="'+esc((teachers.teachers.find(t=>t.course_id===f.course_id)||teachers.teachers[0]||{}).slug||"")+'">بدء الشرح والاختبار</button></div></div>').join(""):'<div class="detail-item">لا توجد ملفات مرفوعة بعد.</div>');
      document.getElementById("uploadStudentFile").onclick=async()=>{
        const teacher=document.getElementById("fileTeacher").value,file=document.getElementById("studentUpload").files[0],state=document.getElementById("fileUploadState");
        if(!teacher||!file){state.textContent="اختر المدرس والملف أولًا.";return}
        const fd=new FormData();fd.append("file",file);state.textContent="جارٍ الرفع والاستخراج…";
        try{const d=await api("/student/files/upload?teacher_slug="+encodeURIComponent(teacher),{method:"POST",body:fd});state.textContent="تم رفع الملف. الخطوة التالية: بدء الشرح مع المدرس الذكي.";loadStudentFiles()}catch(e){state.textContent=e.message}
      };
    }catch(e){b.innerHTML='<div class="detail-item">'+esc(e.message)+'</div>'}
  }

async function openFileTeaching(fileId, teacherSlug){
  if(!teacherSlug){toast("لم يتم العثور على المدرس المرتبط بهذا الملف.");return}
  const b=body();
  const box=document.createElement("div"); box.className="subscription-card"; box.id="fileTeachingBox";
  box.innerHTML='<h3>شرح الملف</h3><div id="fileChatMessages" class="detail-item">جارٍ بدء دورة التعلم…</div><div style="margin-top:10px"><input id="fileChatInput" placeholder="اكتب إجابتك أو سؤالك" style="width:100%"><button id="fileChatSend" class="primary" style="margin-top:8px">إرسال</button></div><div id="fileExamArea" style="margin-top:12px"></div>';
  b.prepend(box);
  const messages=box.querySelector("#fileChatMessages");
  const add=(role,text)=>{const p=document.createElement("p");p.innerHTML="<b>"+(role==="assistant"?"المعلم الذكي":"أنت")+":</b> "+esc(text);messages.appendChild(p);messages.scrollTop=messages.scrollHeight};
  try{
    await api("/agent/teacher/"+encodeURIComponent(teacherSlug)+"/teaching-steps",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({source:"student_files",scope_key:"file:"+fileId,position:1})});
    const send=async(message)=>{if(!message.trim())return;add("user",message);box.querySelector("#fileChatInput").value="";try{const d=await api("/agent/teacher/"+encodeURIComponent(teacherSlug)+"/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message,source:"student_files",content_file_id:fileId})});add("assistant",d.content||d.output||"تم.");if(d.next_step==="file_exam"||d.kind==="file_teaching_completed")renderFileExam(fileId,teacherSlug,box.querySelector("#fileExamArea"));}catch(e){add("assistant","خطأ: "+e.message)}};
    box.querySelector("#fileChatSend").onclick=()=>send(box.querySelector("#fileChatInput").value);
    box.querySelector("#fileChatInput").onkeydown=e=>{if(e.key==="Enter")send(e.target.value)};
    await send("ابدأ شرح الملف خطوة بخطوة، ثم اختبر فهمي قبل فتح الاختبار.");
  }catch(e){messages.textContent=e.message}
}
async function renderFileExam(fileId,teacherSlug,area){
  area.innerHTML="<div class='detail-item'>جارٍ تجهيز الاختبار المجاني…</div>";
  try{const d=await api("/agent/teacher/"+encodeURIComponent(teacherSlug)+"/file-exams/"+encodeURIComponent(fileId)+"/generate",{method:"POST"});area.innerHTML="<h3>الاختبار المجاني</h3><form id='fileExamForm'>"+d.questions.map(q=>'<section class="detail-item"><b>'+q.position+". "+esc(q.prompt)+'</b><div class="quiz-options">'+q.options.map(o=>'<label class="quiz-option"><input type="radio" name="q'+q.position+'" value="'+esc(o)+'" required><span>'+esc(o)+'</span></label>').join("")+"</div></section>").join("")+"<button class='primary' type='submit'>تسليم الاختبار</button></form>";const form=area.querySelector("#fileExamForm");form.onsubmit=async e=>{e.preventDefault();const answers={};d.questions.forEach(q=>{const x=form.querySelector('input[name="q'+q.position+'"]:checked');if(x)answers[String(q.position)]=x.value});try{const result=await api("/agent/teacher/"+encodeURIComponent(teacherSlug)+"/file-exams/"+encodeURIComponent(fileId)+"/submit",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({answers})});area.innerHTML="<div class='quiz-results'><h3>نتيجة الاختبار</h3><p>الدرجة: <b>"+Number(result.percentage||0).toFixed(1)+"%</b></p><p>"+(result.passed?"نجحت في الاختبار.":"تحتاج إلى مراجعة الملف.")+"</p><p>تم إرسال النتيجة إلى المدير العام.</p></div>"}catch(err){area.innerHTML="<div class='error'>"+esc(err.message)+"</div>"}}}catch(e){area.innerHTML="<div class='error'>"+esc(e.message)+"</div>"}}
  window.loadStudentFiles=loadStudentFiles;
  document.addEventListener("DOMContentLoaded",()=>{const b=document.getElementById("refreshFiles");if(b)b.onclick=loadStudentFiles;document.addEventListener("click",e=>{const x=e.target.closest(".file-teach");if(x)openFileTeaching(x.dataset.file,x.dataset.teacher)})});
})();