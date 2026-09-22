(()=> {
  let current=null;
  const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
  const body=()=>document.getElementById("assessmentBody");
  const results=()=>document.getElementById("resultsBody");

  function showResults(d){
    const details=Object.values(d.details||{});
    const wrong=details.filter(x=>!x.correct).length;
    const weak=(d.analysis?.weak_points||[]);
    const next=d.analysis?.next_step;
    body().innerHTML='<div class="quiz-results"><div class="metric-grid"><div class="metric"><span>الدرجة</span><b>'+Number(d.percentage||0).toFixed(1)+'%</b></div><div class="metric"><span>الحالة</span><b>'+(d.passed?"ناجح":"يحتاج مراجعة")+'</b></div></div><p>عدد الإجابات غير الصحيحة: '+wrong+'</p><h3>التحليل</h3>'+(
      weak.length?weak.map(w=>'<div class="detail-item"><b>'+esc(w.topic)+'</b><p>'+esc(w.reason)+'</p></div>').join("")
      :'<div class="detail-item">لا توجد نقاط ضعف مسجلة.</div>'
    )+(next?'<div class="detail-item"><b>الخطوة التالية:</b> '+esc(next.reason)+'</div>':"")+'</div>';
  }

  async function openAssessment(id){
    const b=body();b.innerHTML="<div class='detail-item'>جارٍ تحميل الاختبار…</div>";
    try{
      let d=await api("/student/assessments/"+encodeURIComponent(id));
      if(!d.questions?.length){
        d=await api("/student/assessments/"+encodeURIComponent(id)+"/generate",{method:"POST"});
      }
      current=d;
      b.innerHTML='<div class="detail-item"><b>'+esc(d.title)+'</b><p>'+esc(d.description||"")+'</p><span>'+d.question_count+' سؤال · النجاح من '+(d.pass_percentage??60)+'%</span></div><form id="assessmentForm"></form>';
      const form=document.getElementById("assessmentForm");
      form.innerHTML=d.questions.map(q=>{
        const opts=q.options.map(o=>'<label class="quiz-option"><input type="radio" name="q'+q.position+'" value="'+esc(o)+'" required><span>'+esc(o)+'</span></label>').join("");
        return '<section class="detail-item"><b>'+q.position+'. '+esc(q.prompt)+'</b><div class="quiz-options">'+opts+'</div></section>';
      }).join("")+'<button class="primary" type="submit">تسليم الاختبار وتصحيح النتيجة</button>';
      form.onsubmit=async e=>{
        e.preventDefault();
        const answers={};d.questions.forEach(q=>{const x=form.querySelector('input[name="q'+q.position+'"]:checked');if(x)answers[String(q.position)]=x.value});
        try{
          const result=await api("/student/assessments/"+encodeURIComponent(id)+"/submit",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({answers})});
          showResults(result);
        }catch(err){toast(err.message)}
      };
    }catch(e){b.innerHTML='<div class="detail-item">'+esc(e.message)+'</div>'}
  }

  async function loadAssessments(){
    const panel=document.getElementById("assessmentPanel"),b=body();
    if(!panel||!b)return;
    panel.classList.remove("hidden");
    try{
      const d=await api("/student/assessments");
      b.innerHTML=d.assessments?.length?d.assessments.map(a=>'<article class="subscription-card"><h3>'+esc(a.title)+'</h3><p>'+esc(a.course_code||"")+" · "+esc(a.course_name||"")+'</p><p>'+esc(a.description||"")+'</p><button class="primary assessment-open" data-id="'+esc(a.assessment_id)+'">'+(a.latest?"إعادة الاختبار":"بدء الاختبار")+'</button>'+(a.latest?'<div class="muted">آخر نتيجة: '+Number(a.latest.percentage||0).toFixed(1)+'% — '+(a.latest.passed?"ناجح":"يحتاج مراجعة")+'</div>':"")+'</article>').join(""):'<div class="detail-item">لا توجد اختبارات متاحة بعد.</div>';
      document.querySelectorAll(".assessment-open").forEach(x=>x.onclick=()=>openAssessment(x.dataset.id));
    }catch(e){b.innerHTML='<div class="detail-item">'+esc(e.message)+'</div>'}
  }

  async function loadAssessmentResults(){
    const panel=document.getElementById("resultsPanel"),b=results();
    if(!panel||!b)return;
    panel.classList.remove("hidden");
    try{
      const d=await api("/student/assessments/results/history");
      b.innerHTML=d.results?.length?d.results.map(r=>'<div class="detail-item"><b>اختبار</b><div>'+Number(r.percentage||0).toFixed(1)+'% · '+(r.passed?"ناجح":"لم يجتز")+'</div><small>'+esc(r.graded_at||r.started_at)+'</small></div>').join(""):'<div class="detail-item">لا توجد نتائج بعد.</div>';
    }catch(e){b.innerHTML='<div class="detail-item">'+esc(e.message)+'</div>'}
  }
  window.loadAssessments=loadAssessments;
  window.loadAssessmentResults=loadAssessmentResults;
  document.addEventListener("DOMContentLoaded",()=>{
    const a=document.getElementById("refreshAssessments"),r=document.getElementById("refreshResults");
    if(a)a.onclick=loadAssessments;if(r)r.onclick=loadAssessmentResults;
  });
})();