(()=> {
  const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
  const body=()=>document.getElementById("filesBody");
  const apiError=(e)=>e?.message||"Request failed";

  async function loadStudentFiles(){
    const panel=document.getElementById("filesPanel"),b=body();
    if(!panel||!b)return;
    panel.classList.remove("hidden");
    try{
      const [files,teachers]=await Promise.all([api("/student/files"),api("/student/files/teachers")]);
      const teacherById=new Map((teachers.teachers||[]).map(t=>[String(t.id),t]));
      b.innerHTML='<div class="subscription-card"><h3>رفع ملف للدراسة</h3><p>PDF أو DOCX أو TXT. اختر المدرس الذكي المرتبط بالمقرر. بعد الرفع تبدأ دورة الشرح والفهم ثم الاختبار المجاني.</p><select id="fileTeacher"><option value="">اختر المدرس</option>'+
        (teachers.teachers||[]).map(t=>'<option value="'+esc(t.slug)+'">'+esc(t.name)+'</option>').join("")+
        '</select><input id="studentUpload" type="file" accept=".pdf,.docx,.txt" style="margin-top:10px"><button id="uploadStudentFile" class="primary">رفع الملف</button><div id="fileUploadState" class="muted"></div></div><h3>مكتبة الملفات</h3>'+
        (files.files?.length?files.files.map(f=>{
          const teacher=teacherById.get(String(f.teaching_agent_id));
          return '<div class="detail-item"><b>'+esc(f.original_name)+'</b><div class="muted">'+Number(f.size_bytes||0).toLocaleString()+' bytes · '+esc(f.uploaded_at||"")+'</div><div style="margin-top:8px">'+
            (teacher?'<button class="primary file-teach" data-file="'+esc(f.file_id)+'" data-teacher="'+esc(teacher.slug)+'">بدء الشرح والاختبار</button>':'<span class="muted">المدرس المرتبط بالملف غير متاح حاليًا.</span>')+
            '</div></div>';
        }).join(""):'<div class="detail-item">لا توجد ملفات مرفوعة بعد.</div>');

      document.getElementById("uploadStudentFile").onclick=async()=>{
        const teacher=document.getElementById("fileTeacher").value;
        const file=document.getElementById("studentUpload").files[0];
        const state=document.getElementById("fileUploadState");
        if(!teacher||!file){state.textContent="اختر المدرس والملف أولًا.";return}
        const fd=new FormData();fd.append("file",file);state.textContent="جارٍ الرفع والاستخراج…";
        try{
          await api("/student/files/upload?teacher_slug="+encodeURIComponent(teacher),{method:"POST",body:fd});
          state.textContent="تم رفع الملف. يمكنك الآن بدء الشرح.";
          await loadStudentFiles();
        }catch(e){state.textContent=apiError(e)}
      };
    }catch(e){b.innerHTML='<div class="detail-item">'+esc(apiError(e))+'</div>'}
  }

  async function openFileTeaching(fileId,teacherSlug){
    if(!teacherSlug){toast("لم يتم العثور على المدرس المرتبط بهذا الملف.");return}
    const b=body(); if(!b)return;
    const box=document.createElement("div"); box.className="subscription-card"; box.id="fileTeachingBox";
    box.innerHTML='<h3>شرح الملف</h3><div id="fileTeachingStatus" class="muted">جارٍ بدء دورة التعلم…</div><div id="fileChatMessages" class="detail-item" style="margin-top:10px;max-height:360px;overflow:auto"></div>'+
      '<div style="margin-top:10px"><input id="fileChatInput" placeholder="اكتب إجابتك أو سؤالك" style="width:100%"><button id="fileChatSend" class="primary" style="margin-top:8px">إرسال</button></div>'+
      '<div class="teacher-actions" style="margin-top:10px"><button class="ghost" id="fileVerify">تحقق من الفهم</button><button class="ghost" id="fileConfirm">تأكيد فهم الدرس</button></div>'+
      '<div id="fileExamArea" style="margin-top:12px"></div>';
    b.prepend(box);

    const messages=box.querySelector("#fileChatMessages");
    const status=box.querySelector("#fileTeachingStatus");
    const input=box.querySelector("#fileChatInput");
    const add=(role,text)=>{
      const p=document.createElement("p");
      p.innerHTML="<b>"+(role==="assistant"?"المعلم الذكي":"أنت")+":</b> "+esc(text);
      messages.appendChild(p);messages.scrollTop=messages.scrollHeight;
    };
    let stepId=null;

    try{
      const step=await api("/agent/teacher/"+encodeURIComponent(teacherSlug)+"/teaching-steps",{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({source:"student_files",scope_key:"file:"+fileId,position:1})
      });
      stepId=step.id;
      status.textContent="بدأ الشرح. تفاعل مع المدرس ثم تحقق من الفهم وأكد إكمال الدرس.";
    }catch(e){status.textContent=apiError(e);return}

    const send=async message=>{
      const msg=String(message||"").trim();if(!msg)return;
      add("user",msg);input.value="";status.textContent="جارٍ إرسال الرسالة…";
      try{
        const d=await api("/agent/teacher/"+encodeURIComponent(teacherSlug)+"/chat",{
          method:"POST",headers:{"Content-Type":"application/json"},
          body:JSON.stringify({message:msg,source:"student_files",content_file_id:fileId})
        });
        add("assistant",d.content||d.output||"تم.");
        if(typeof speakText==="function")speakText(d.content||d.output||"");
        status.textContent="تمت استجابة المدرس. عند اكتمال الفهم استخدم زرّي التحقق والتأكيد.";
      }catch(e){status.textContent=apiError(e)}
    };

    box.querySelector("#fileChatSend").onclick=()=>send(input.value);
    input.onkeydown=e=>{if(e.key==="Enter"){e.preventDefault();send(input.value)}};

    box.querySelector("#fileVerify").onclick=async()=>{
      if(!stepId)return;
      try{
        const d=await api("/agent/teacher/"+encodeURIComponent(teacherSlug)+"/teaching-steps/"+encodeURIComponent(stepId)+"/understanding",{
          method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({verified:true})
        });
        status.textContent=d.status==="completed"?"تم التحقق من الفهم. يمكنك الآن تأكيد إكمال الدرس.":"تم تسجيل تحقق الفهم.";
      }catch(e){status.textContent=apiError(e)}
    };

    box.querySelector("#fileConfirm").onclick=async()=>{
      if(!stepId)return;
      try{
        const d=await api("/agent/teacher/"+encodeURIComponent(teacherSlug)+"/teaching-steps/"+encodeURIComponent(stepId)+"/confirm",{
          method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({confirmed:true})
        });
        status.textContent=d.completed?"اكتملت دورة الشرح. جاري تجهيز الاختبار المجاني…":"تم تسجيل التأكيد.";
        if(d.completed)await renderFileExam(fileId,teacherSlug,box.querySelector("#fileExamArea"));
      }catch(e){status.textContent=apiError(e)}
    };

    await send("ابدأ شرح الملف خطوة بخطوة، واختبر فهمي قبل فتح الاختبار.");
  }

  async function renderFileExam(fileId,teacherSlug,area){
    area.innerHTML="<div class='detail-item'>جارٍ تجهيز الاختبار المجاني…</div>";
    try{
      const d=await api("/agent/teacher/"+encodeURIComponent(teacherSlug)+"/file-exams/"+encodeURIComponent(fileId)+"/generate",{method:"POST"});
      const questions=d.questions||[];
      if(!questions.length)throw new Error("لم يتم إنشاء أسئلة للاختبار.");
      area.innerHTML="<h3>الاختبار المجاني</h3><p class='muted'>أجب عن جميع الأسئلة ثم سلّم الاختبار.</p><form id='fileExamForm'>"+
        questions.map(q=>'<section class="detail-item"><b>'+esc(q.position)+". "+esc(q.prompt)+'</b><div class="quiz-options">'+
          (q.options||[]).map(o=>'<label class="quiz-option"><input type="radio" name="q'+esc(q.position)+'" value="'+esc(o)+'" required><span>'+esc(o)+'</span></label>').join("")+
          '</div></section>').join("")+
        "<button class='primary' type='submit'>تسليم الاختبار</button></form>";
      const form=area.querySelector("#fileExamForm");
      form.onsubmit=async e=>{
        e.preventDefault();
        const answers={};
        questions.forEach(q=>{const x=form.querySelector('input[name="q'+q.position+'"]:checked');if(x)answers[String(q.position)]=x.value});
        try{
          const result=await api("/agent/teacher/"+encodeURIComponent(teacherSlug)+"/file-exams/"+encodeURIComponent(fileId)+"/submit",{
            method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({answers})
          });
          area.innerHTML="<div class='quiz-results'><h3>نتيجة الاختبار</h3><p>الدرجة: <b>"+Number(result.percentage||0).toFixed(1)+"%</b></p><p>"+(result.passed?"نجحت في الاختبار.":"تحتاج إلى مراجعة الملف.")+"</p><p>تم إرسال النتيجة إلى المدير العام.</p></div>";
        }catch(err){area.innerHTML="<div class='error'>"+esc(apiError(err))+"</div>"}
      };
    }catch(e){area.innerHTML="<div class='error'>"+esc(apiError(e))+"</div>"}
  }

  window.loadStudentFiles=loadStudentFiles;
  document.addEventListener("DOMContentLoaded",()=>{
    const refresh=document.getElementById("refreshFiles");if(refresh)refresh.onclick=loadStudentFiles;
    document.addEventListener("click",e=>{
      const x=e.target.closest(".file-teach");
      if(x)openFileTeaching(x.dataset.file,x.dataset.teacher);
    });
  });
})();