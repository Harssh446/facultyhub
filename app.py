import csv, io, os, random, uuid
from datetime import date, datetime
from functools import wraps
from pathlib import Path
from flask import Flask, Response, abort, flash, g, redirect, render_template, request, send_from_directory, session, url_for
from markupsafe import Markup
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from storage import load, save, next_id
from seed import ensure_data
from ai import generate_questions, lesson_plan, progress_summary

BASE=Path(__file__).parent; UPLOADS=BASE/'data'/'uploads'; UPLOADS.mkdir(parents=True,exist_ok=True)
SUBJECTS=['Data Structures','Database Systems','Operating Systems','Computer Networks','Engineering Mathematics']
BRANCHES=['CSE','IT','ECE']; STATUSES=['Present','Absent','Late']; MAXM={'t1':30,'t2':30,'asg':20}; TOTAL=80
ALLOWED={'pdf','doc','docx','txt','png','jpg','jpeg','zip','py','java','c','cpp'}
app=Flask(__name__); app.secret_key=os.getenv('SECRET_KEY','dev-secret-change-me'); app.config['MAX_CONTENT_LENGTH']=5*1024*1024
ensure_data()

def grade_for(p):
    for n,g_ in ((90,'A+'),(80,'A'),(70,'B+'),(60,'B'),(50,'C'),(40,'D')):
        if p>=n:return g_
    return 'F'

def risk_for(att,avg):
    if att<65 or avg<40:l='Red'
    elif att<75 or avg<55:l='Amber'
    else:l='Green'
    reasons=[]
    if att<75:reasons.append(f'Attendance {att}% is below 75%')
    if avg<55:reasons.append(f'Average internal marks {avg}% are below 55%')
    return l,reasons

def students_map():return {s['roll']:s for s in load('students')}
def parse_date(s,default=None):
    try:return datetime.strptime(s,'%Y-%m-%d').date()
    except:return default
def to_int(v,d,lo,hi):
    try:return max(lo,min(hi,int(v)))
    except:return d
def to_float(v,lo,hi):
    try:return round(max(lo,min(hi,float(v))),1)
    except:return None

def all_stats(branch=None):
    att={}
    for r in load('attendance'):
        x=att.setdefault(r['roll'],[0,0]);x[1]+=1;x[0]+=r['status'] in ('Present','Late')
    mk={}
    for m in load('marks'):mk.setdefault(m['roll'],[]).append((m['t1']+m['t2']+m['asg'])/TOTAL*100)
    out=[]
    for s in load('students'):
        if branch and s['branch']!=branch:continue
        p,d=att.get(s['roll'],[0,0]); a=round(p/d*100,1) if d else 0
        vals=mk.get(s['roll'],[]); avg=round(sum(vals)/len(vals),1) if vals else 0
        risk,reasons=risk_for(a,avg)
        out.append({**s,'att':a,'present':p,'days':d,'avg':avg,'grade':grade_for(avg),'risk':risk,'reasons':reasons})
    return out

def stat_for(roll):return next((x for x in all_stats() if x['roll']==roll),None)
def marks_rows(roll):
    out=[]
    for m in load('marks'):
        if m['roll']==roll:
            tot=round(m['t1']+m['t2']+m['asg'],1);pct=round(tot/TOTAL*100,1)
            out.append({**m,'total':tot,'pct':pct,'grade':grade_for(pct)})
    return sorted(out,key=lambda x:x['subject'])

def student_profile(roll):
    s=students_map().get(roll)
    if not s:return None
    subs={x['assignment_id']:x for x in load('submissions') if x['roll']==roll}; assigns=[]
    for a in sorted(load('assignments'),key=lambda x:x['due']):
        sub=subs.get(a['id']);assigns.append({**a,'sub':sub,'status':sub['status'] if sub else 'Pending'})
    attempts=sorted([x for x in load('quiz_attempts') if x['roll']==roll],key=lambda x:x['id'],reverse=True)[:8]
    return {'student':s,'stat':stat_for(roll),'marks':marks_rows(roll),'assigns':assigns,'attempts':attempts}

def csv_response(name,headers,rows):
    b=io.StringIO();w=csv.writer(b);w.writerow(headers);w.writerows(rows)
    return Response(b.getvalue(),mimetype='text/csv',headers={'Content-Disposition':f'attachment; filename={name}'})

def csrf_token():
    if '_csrf' not in session:session['_csrf']=uuid.uuid4().hex
    return session['_csrf']
app.jinja_env.globals.update(csrf=lambda:Markup(f'<input type="hidden" name="_csrf" value="{csrf_token()}">'),grade_for=grade_for,MAXM=MAXM,TOTAL=TOTAL)
@app.before_request
def before():
    g.user=None
    if session.get('user'):g.user=next((u for u in load('users') if u['username']==session['user']),None)
    if request.method=='POST' and request.form.get('_csrf')!=session.get('_csrf'):abort(400)
@app.context_processor
def inject():return {'user':g.get('user'),'SUBJECTS':SUBJECTS,'BRANCHES':BRANCHES,'STATUSES':STATUSES,'today_str':date.today().isoformat()}
def login_required(f):
    @wraps(f)
    def w(*a,**k):
        if not g.user:return redirect(url_for('login',next=request.path))
        return f(*a,**k)
    return w
def faculty_required(f):
    @wraps(f)
    def w(*a,**k):
        if not g.user:return redirect(url_for('login',next=request.path))
        if g.user['role']!='faculty':abort(403)
        return f(*a,**k)
    return w
def is_faculty():return bool(g.user and g.user['role']=='faculty')

def render(page,**ctx):return render_template('portal.html',page=page,**ctx)

@app.route('/')
def index():return redirect(url_for('dashboard') if g.user else url_for('login'))
@app.route('/login',methods=['GET','POST'])
def login():
    if g.user:return redirect(url_for('dashboard'))
    if request.method=='POST':
        name=request.form.get('username','').strip().lower();pw=request.form.get('password','');u=next((x for x in load('users') if x['username']==name),None)
        if u and check_password_hash(u['password_hash'],pw):
            session.clear();session['user']=u['username'];csrf_token();return redirect(request.args.get('next') if request.args.get('next','').startswith('/') else url_for('dashboard'))
        flash('Invalid username or password.','error')
    return render_template('login.html')
@app.route('/register',methods=['GET','POST'])
def register():
    if request.method=='POST':
        username=request.form.get('username','').strip().lower();name=request.form.get('name','').strip();pw=request.form.get('password','');roll=request.form.get('roll','').strip().upper()
        if len(username)<3 or len(pw)<6 or not name:flash('Enter a valid name, username and password.','error')
        elif any(u['username']==username for u in load('users')):flash('Username already exists.','error')
        else:
            users=load('users');users.append({'username':username,'password_hash':generate_password_hash(pw),'role':'student','name':name,'roll':roll or username.upper()});save('users',users)
            if roll and not any(s['roll']==roll for s in load('students')):
                students=load('students');students.append({'roll':roll,'name':name,'branch':request.form.get('branch','CSE'),'email':request.form.get('email',f'{username}@facultyhub.edu')});save('students',students)
            flash('Account created. Please sign in.','success');return redirect(url_for('login'))
    return render_template('login.html',register=True)
@app.route('/logout',methods=['POST'])
def logout():session.clear();flash('You have been signed out.','success');return redirect(url_for('login'))
@app.route('/password',methods=['GET','POST'])
@login_required
def password():
    if request.method=='POST':
        cur,new,conf=(request.form.get(k,'') for k in ('current','new','confirm'))
        if not check_password_hash(g.user['password_hash'],cur):flash('Current password is incorrect.','error')
        elif len(new)<6:flash('New password must be at least 6 characters.','error')
        elif new!=conf:flash('New passwords do not match.','error')
        else:
            users=load('users');
            for u in users:
                if u['username']==g.user['username']:u['password_hash']=generate_password_hash(new)
            save('users',users);flash('Password updated.','success');return redirect(url_for('dashboard'))
    return render(page='password')

@app.route('/dashboard')
@login_required
def dashboard():
    stats=all_stats();n=len(stats);avg_att=round(sum(x['att'] for x in stats)/n,1) if n else 0;avg_marks=round(sum(x['avg'] for x in stats)/n,1) if n else 0
    if is_faculty():
        risk_counts={k:sum(x['risk']==k for x in stats) for k in ('Green','Amber','Red')};at_risk=sorted([x for x in stats if x['risk']!='Green'],key=lambda x:(x['risk']!='Red',x['att']))[:8]
        subavg={}
        for m in load('marks'):subavg.setdefault(m['subject'],[]).append((m['t1']+m['t2']+m['asg'])/TOTAL*100)
        subject_rows=[(k,round(sum(v)/len(v),1)) for k,v in sorted(subavg.items())]
        pending=[s for s in load('submissions') if s['status']!='Evaluated']
        return render('faculty_dashboard',stats=stats,n=n,avg_att=avg_att,avg_marks=avg_marks,risk_counts=risk_counts,at_risk=at_risk,subject_rows=subject_rows,pending_count=len(pending),recent=pending[:6])
    p=student_profile(g.user['roll']);return render('student_dashboard',p=p,avg_att=avg_att,avg_marks=avg_marks)

@app.route('/students')
@faculty_required
def students():
    q=request.args.get('q','').lower();branch=request.args.get('branch','');rows=[x for x in all_stats(branch or None) if not q or q in x['name'].lower() or q in x['roll'].lower() or q in x['email'].lower()]
    return render('students',rows=rows,q=q,branch=branch)
@app.route('/students/<roll>')
@login_required
def student_detail(roll):
    if not is_faculty() and g.user['roll']!=roll:abort(403)
    p=student_profile(roll)
    if not p:abort(404)
    summary=progress_summary(p['stat'],p['marks']) if request.args.get('summary') else None
    return render('student_detail',p=p,summary=summary)

@app.route('/attendance/take',methods=['GET','POST'])
@faculty_required
def attendance_take():
    d=parse_date(request.values.get('date'),date.today());students=load('students')
    if request.method=='POST':
        if d>date.today():flash('You cannot take attendance for a future date.','error');return redirect(url_for('attendance_take'))
        rows=[r for r in load('attendance') if r['date']!=d.isoformat()];nid=next_id(rows)
        for s in students:
            st=request.form.get('status_'+s['roll'],'Present');rows.append({'id':nid,'date':d.isoformat(),'roll':s['roll'],'status':st if st in STATUSES else 'Present'});nid+=1
        save('attendance',rows);flash('Attendance saved for ' + d.strftime('%d %b %Y') + '.', 'success');return redirect(url_for('attendance_take',date=d.isoformat()))
    existing={r['roll']:r['status'] for r in load('attendance') if r['date']==d.isoformat()};return render('attendance_take',students=students,date=d.isoformat(),existing=existing)
def filtered_attendance(roll=None):
    a=request.args;f=parse_date(a.get('from'));t=parse_date(a.get('to'));forced=roll or a.get('roll','');status=a.get('status','');branch=a.get('branch','');smap=students_map();rows=[]
    for r in load('attendance'):
        s=smap.get(r['roll']);d=parse_date(r['date'])
        if not s or (f and d<f) or (t and d>t) or (forced and r['roll']!=forced) or (status and r['status']!=status) or (branch and s['branch']!=branch):continue
        rows.append({**r,'name':s['name'],'branch':s['branch']})
    return sorted(rows,key=lambda x:(x['date'],x['roll']),reverse=True)
@app.route('/attendance')
@login_required
def attendance():
    rows=filtered_attendance(None if is_faculty() else g.user['roll']);return render('attendance',rows=rows[:300],total=len(rows),counts={s:sum(r['status']==s for r in rows) for s in STATUSES})
@app.route('/attendance/export.csv')
@login_required
def attendance_export():
    rows=filtered_attendance(None if is_faculty() else g.user['roll']);return csv_response('attendance.csv',['Date','Roll No','Name','Branch','Status'],[[r['date'],r['roll'],r['name'],r['branch'],r['status']] for r in rows])

@app.route('/marks',methods=['GET','POST'])
@login_required
def marks():
    if not is_faculty():return render('marks',rows=marks_rows(g.user['roll']))
    subject=request.values.get('subject',SUBJECTS[0]);subject=subject if subject in SUBJECTS else SUBJECTS[0];students=load('students');data=load('marks')
    if request.method=='POST':
        data=[m for m in data if m['subject']!=subject]
        for s in students:
            row={'roll':s['roll'],'subject':subject};any_=False
            for k,mx in MAXM.items():
                raw=request.form.get(f'{k}_{s["roll"]}','').strip();any_=any_ or raw!='';row[k]=to_float(raw,0,mx) or 0
            if any_:data.append(row)
        save('marks',data);flash(f'Marks saved for {subject}.','success');return redirect(url_for('marks',subject=subject))
    cur={m['roll']:m for m in data if m['subject']==subject};return render('marks',subject=subject,students=students,cur=cur)
@app.route('/marks/export.csv')
@faculty_required
def marks_export():
    smap=students_map();rows=[]
    for m in sorted(load('marks'),key=lambda x:(x['subject'],x['roll'])):
        tot=round(m['t1']+m['t2']+m['asg'],1);pct=round(tot/TOTAL*100,1);rows.append([m['roll'],smap.get(m['roll'],{}).get('name',''),m['subject'],m['t1'],m['t2'],m['asg'],tot,pct,grade_for(pct)])
    return csv_response('marks.csv',['Roll No','Name','Subject','Test 1','Test 2','Assignment','Total','Percent','Grade'],rows)

@app.route('/assignments')
@login_required
def assignments():
    items=sorted(load('assignments'),key=lambda a:a['due']);subs=load('submissions');smap=students_map()
    if is_faculty():
        for a in items:
            ss=[s for s in subs if s['assignment_id']==a['id']];a.update(submitted=len(ss),total=len(smap),evaluated=sum(s['status']=='Evaluated' for s in ss))
    else:
        mine={s['assignment_id']:s for s in subs if s['roll']==g.user['roll']}
        for a in items:a['sub']=mine.get(a['id']);a['status']=a['sub']['status'] if a['sub'] else 'Pending'
    return render('assignments',items=items)
@app.route('/assignments/new',methods=['GET','POST'])
@faculty_required
def assignment_new():
    if request.method=='POST':
        title=request.form.get('title','').strip();subject=request.form.get('subject','');due=parse_date(request.form.get('due'))
        if not title or subject not in SUBJECTS or not due:flash('Title, subject and valid due date are required.','error')
        else:
            a=load('assignments');a.append({'id':next_id(a),'title':title,'subject':subject,'due':due.isoformat(),'max_marks':to_int(request.form.get('max_marks'),20,1,100),'description':request.form.get('description','').strip()});save('assignments',a);flash('Assignment created.','success');return redirect(url_for('assignments'))
    return render('assignment_new')
@app.route('/assignments/<int:aid>')
@login_required
def assignment_detail(aid):
    a=next((x for x in load('assignments') if x['id']==aid),None)
    if not a:abort(404)
    subs=[s for s in load('submissions') if s['assignment_id']==aid];smap=students_map()
    for s in subs:s['name']=smap.get(s['roll'],{}).get('name',s['roll'])
    mine=next((s for s in subs if s['roll']==g.user['roll']),None) if not is_faculty() else None
    return render('assignment_detail',assignment=a,subs=subs,mine=mine)
@app.route('/assignments/<int:aid>/submit',methods=['POST'])
@login_required
def assignment_submit(aid):
    if is_faculty():abort(403)
    a=next((x for x in load('assignments') if x['id']==aid),None)
    if not a:abort(404)
    file=request.files.get('file');title=request.form.get('comment','').strip()
    if not file or not file.filename:flash('Choose a file to submit.','error');return redirect(url_for('assignment_detail',aid=aid))
    ext=Path(file.filename).suffix.lower().lstrip('.')
    if ext not in ALLOWED:flash('Unsupported file type.','error');return redirect(url_for('assignment_detail',aid=aid))
    name=f'{uuid.uuid4().hex}_{secure_filename(file.filename)}';file.save(UPLOADS/name)
    subs=load('submissions');existing=next((s for s in subs if s['assignment_id']==aid and s['roll']==g.user['roll']),None);late=date.today()>date.fromisoformat(a['due'])
    obj={'id':existing['id'] if existing else next_id(subs),'assignment_id':aid,'roll':g.user['roll'],'filename':file.filename,'stored':name,'submitted_on':date.today().isoformat(),'late':late,'status':'Late' if late else 'Submitted','marks':None,'feedback':title}
    if existing:subs[subs.index(existing)]=obj
    else:subs.append(obj)
    save('submissions',subs);flash('Assignment submitted.','success');return redirect(url_for('assignment_detail',aid=aid))
@app.route('/submissions/<int:sid>/evaluate',methods=['POST'])
@faculty_required
def evaluate(sid):
    subs=load('submissions');s=next((x for x in subs if x['id']==sid),None)
    if not s:abort(404)
    a=next(x for x in load('assignments') if x['id']==s['assignment_id']);marks=to_float(request.form.get('marks'),0,a['max_marks'])
    if marks is None:flash('Enter valid marks.','error')
    else:s.update(marks=marks,feedback=request.form.get('feedback','').strip(),status='Evaluated');save('submissions',subs);flash('Submission evaluated.','success')
    return redirect(url_for('assignment_detail',aid=a['id']))
@app.route('/uploads/<path:name>')
@login_required
def upload(name):
    s=next((x for x in load('submissions') if x.get('stored')==name),None)
    if not s or (not is_faculty() and s['roll']!=g.user['roll']):abort(404)
    return send_from_directory(UPLOADS,name,as_attachment=True,download_name=s['filename'])

@app.route('/questions')
@faculty_required
def questions():return render('questions',rows=load('questions'))
@app.route('/questions/add',methods=['POST'])
@faculty_required
def question_add():
    f=request.form;opts=[f.get(f'opt{i}','').strip() for i in range(4)];ans=to_int(f.get('answer'),-1,0,3)
    if f.get('subject') not in SUBJECTS or not f.get('topic') or not f.get('question') or not all(opts):flash('Fill every question field.','error')
    else:
        q=load('questions');q.append({'id':next_id(q),'subject':f['subject'],'topic':f['topic'].strip(),'question':f['question'].strip(),'options':opts,'answer':ans,'difficulty':f.get('difficulty','medium'),'status':'approved','source':'faculty'});save('questions',q);flash('Question added.','success')
    return redirect(url_for('questions'))
@app.route('/questions/generate',methods=['POST'])
@faculty_required
def question_generate():
    f=request.form;subject=f.get('subject');topic=f.get('topic','').strip();difficulty=f.get('difficulty','medium');n=to_int(f.get('count'),5,1,20)
    if subject not in SUBJECTS or not topic:flash('Choose a subject and topic.','error');return redirect(url_for('questions'))
    qs,source=generate_questions(subject,topic,difficulty,n);return render('generated_questions',qs=qs,subject=subject,topic=topic,source=source)

@app.route('/paper',methods=['GET','POST'])
@faculty_required
def paper():
    if request.method=='POST':
        subject=request.form.get('subject');topic=request.form.get('topic','').strip();difficulty=request.form.get('difficulty','any');count=to_int(request.form.get('count'),10,1,50)
        bank=[q for q in load('questions') if q['status']=='approved' and q['subject']==subject and (not topic or topic.lower() in q['topic'].lower()) and (difficulty in ('any','mixed','') or q['difficulty']==difficulty)]
        if len(bank)<count: qs,_=generate_questions(subject,topic or 'core topics',difficulty,count)
        else:random.shuffle(bank);qs=bank[:count]
        return render('paper',qs=qs,subject=subject,title=request.form.get('title','Internal Assessment'),marks_per=to_int(request.form.get('marks_per'),1,1,20),duration=to_int(request.form.get('duration'),60,5,300))
    topics=sorted({q['topic'] for q in load('questions')});return render('paper_form',topics=topics)

@app.route('/quiz',methods=['GET','POST'])
@login_required
def quiz():
    if request.method=='POST':
        f=request.form;subject=f.get('subject');topic=f.get('topic','').strip();difficulty=f.get('difficulty','any');n=to_int(f.get('count'),5,1,20)
        bank=[q for q in load('questions') if q['status']=='approved' and q['subject']==subject and (not topic or topic.lower() in q['topic'].lower()) and (difficulty in ('any','mixed','') or q['difficulty']==difficulty)]
        if len(bank)<n:qs,_=generate_questions(subject,topic or 'core topics',difficulty,n)
        else:random.shuffle(bank);qs=bank[:n]
        session['quiz']={'questions':qs,'subject':subject};return redirect(url_for('quiz_take'))
    return render('quiz_form')
@app.route('/quiz/take')
@login_required
def quiz_take():
    q=session.get('quiz');
    if not q:return redirect(url_for('quiz'))
    return render('quiz_take',qs=q['questions'],subject=q['subject'])
@app.route('/quiz/submit',methods=['POST'])
@login_required
def quiz_submit():
    qd=session.pop('quiz',None)
    if not qd:return redirect(url_for('quiz'))
    results=[];score=0
    for i,q in enumerate(qd['questions']):
        raw=request.form.get(f'q{i}');chosen=int(raw) if raw and raw.isdigit() else None;ok=chosen==q['answer'];score+=ok;results.append({'q':q,'chosen':chosen,'ok':ok})
    if not is_faculty():
        a=load('quiz_attempts');a.append({'id':next_id(a),'roll':g.user['roll'],'subject':qd['subject'],'score':score,'total':len(results),'pct':round(score/len(results)*100),'date':date.today().isoformat()});save('quiz_attempts',a)
    return render('quiz_result',results=results,score=score,total=len(results),subject=qd['subject'])

@app.route('/analytics')
@faculty_required
def analytics():
    stats=all_stats();return render('analytics',stats=stats,counts={k:sum(x['risk']==k for x in stats) for k in ('Green','Amber','Red')},attempts=sorted(load('quiz_attempts'),key=lambda x:x['id'],reverse=True)[:10])
@app.route('/timetable')
@login_required
def timetable():return render('timetable',tt=load('timetable'))
@app.route('/lesson-plan',methods=['GET','POST'])
@faculty_required
def lesson():
    plan=None
    if request.method=='POST':
        f=request.form;plan=lesson_plan(f.get('subject'),f.get('topic'),to_int(f.get('minutes'),60,10,240),f.get('level','Undergraduate'),f.get('objectives','').strip())
    return render('lesson',plan=plan)
@app.route('/report')
@faculty_required
def report():
    stats=all_stats();return render('report',stats=stats,generated=datetime.now().strftime('%d %b %Y, %H:%M'),avg_att=round(sum(x['att'] for x in stats)/len(stats),1) if stats else 0,avg_marks=round(sum(x['avg'] for x in stats)/len(stats),1) if stats else 0)
@app.route('/performance/export.csv')
@faculty_required
def performance_export():return csv_response('performance.csv',['Roll No','Name','Branch','Attendance %','Average Marks %','Grade','Risk'],[[x['roll'],x['name'],x['branch'],x['att'],x['avg'],x['grade'],x['risk']] for x in all_stats()])

@app.errorhandler(400)
def e400(e):return render('error',code=400,message='Bad request or expired form. Refresh and try again.'),400
@app.errorhandler(403)
def e403(e):return render('error',code=403,message='You do not have permission to view this page.'),403
@app.errorhandler(404)
def e404(e):return render('error',code=404,message='We could not find that page.'),404
@app.errorhandler(413)
def e413(e):return render('error',code=413,message='File too large. Maximum 5 MB.'),413
if __name__=='__main__':app.run(debug=os.getenv('FLASK_DEBUG','1')=='1',port=int(os.getenv('PORT','5000')))
