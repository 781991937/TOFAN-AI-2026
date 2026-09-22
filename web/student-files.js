(()=> {
  const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
  const body=()=>document.getElementById("filesBody");
  async function loadStudentFiles(){
    const panel=document.getElementById("filesPanel"),b=body();
    if(!panel||!b)return;
    panel.classList.remove("hidden");
    try{
      const [files,teachers]=await Promise.all([api("/student/files"),api("/student/files/teachers")]);
      b.innerHTML='<div class="subscription-card"><h3>رفع ملف للدراسة</h3><p>PDF أو DOCX أو TXT. اختر المدرس الذكي المرتبط بالمقرر.</p><select id="fileTeacher"><option value="">اختر المدرس</option>'+teachers.teachers.map(t=>'<option value="'+esc(t.slug)+'">'+esc(t.name)+'</option>').join("")+'</select><input id="studentUpload" type="file" accept=".pdf,.docx,.txt" style="margin-top:10px"><button id="uploadStudentFile" class="primary">رفع الملف</button><div id="fileUploadState" class="muted"></div></div><h3>مكتبة الملفات</h3>'+(files.files?.length?files.files.map(f=>'<div class="detail-item"><b>'+esc(f.original_name)+'</b><div class="muted">'+Number(f.size_bytes||0).toLocaleString()+' bytes · '+esc(f.uploaded_at)+'</div></div>').join(""):'<div class="detail-item">لا توجد ملفات مرفوعة بعد.</div>');
      document.getElementById("uploadStudentFile").onclick=async()=>{
        const teacher=document.getElementById("fileTeacher").value,file=document.getElementById("studentUpload").files[0],state=document.getElementById("fileUploadState");
        if(!teacher||!file){state.textContent="اختر المدرس والملف أولًا.";return}
        const fd=new FormData();fd.append("file",file);state.textContent="جارٍ الرفع والاستخراج…";
        try{const d=await api("/student/files/upload?teacher_slug="+encodeURIComponent(teacher),{method:"POST",body:fd});state.textContent="تم رفع الملف. الخطوة التالية: بدء الشرح مع المدرس الذكي.";loadStudentFiles()}catch(e){state.textContent=e.message}
      };
    }catch(e){b.innerHTML='<div class="detail-item">'+esc(e.message)+'</div>'}
  }
  window.loadStudentFiles=loadStudentFiles;
  document.addEventListener("DOMContentLoaded",()=>{const b=document.getElementById("refreshFiles");if(b)b.onclick=loadStudentFiles});
})();