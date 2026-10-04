import json, os, random, re, requests
from dotenv import load_dotenv
load_dotenv()
class AIText(str): source='template'
def ask_ai(prompt, fallback=''):
    try:
        url=os.getenv('OLLAMA_URL','http://localhost:11434').rstrip('/')
        model=os.getenv('OLLAMA_MODEL','llama3.2'); timeout=int(os.getenv('OLLAMA_TIMEOUT','120'))
        r=requests.post(f'{url}/api/generate',json={'model':model,'prompt':prompt,'stream':False},timeout=(3,timeout)); r.raise_for_status()
        t=(r.json().get('response') or '').strip()
        if t:
            x=AIText(t); x.source='ollama'; return x
    except Exception: pass
    x=AIText(fallback() if callable(fallback) else fallback); x.source='template'; return x

def generate_questions(subject,topic,difficulty,n):
    prompt=f'''Create {n} college MCQs. Subject: {subject}. Topic: {topic}. Difficulty: {difficulty}. Return ONLY JSON array with question, options (4 strings), answer (0-3).'''
    fallback=[]
    templates=[
      f'Which statement best describes {topic} in {subject}?',
      f'What is a practical use of {topic} in {subject}?',
      f'Which approach is most appropriate when solving problems involving {topic}?',
      f'What should a student verify when applying {topic}?']
    for i in range(n):
        opts=[f'Correct application of {topic}', 'An unrelated concept', 'A formatting rule', 'None of these']
        fallback.append({'question':templates[i%4],'options':opts,'answer':0})
    raw=ask_ai(prompt,json.dumps(fallback)); m=re.search(r'\[.*\]',str(raw),re.S)
    try: items=json.loads(m.group(0)) if m else []
    except Exception: items=[]
    valid=[]
    for q in items:
        try:
            if q.get('question') and len(q.get('options',[]))==4 and 0<=int(q.get('answer'))<4:
                valid.append({'question':str(q['question']),'options':[str(x) for x in q['options']],'answer':int(q['answer'])})
        except Exception: pass
    return (valid[:n] or fallback), getattr(raw,'source','template')

def lesson_plan(subject,topic,minutes,level,objectives):
    prompt=f'Create a concise college lesson plan for {subject}, topic {topic}, {minutes} minutes, level {level}. Objectives: {objectives or "none"}. Include objectives, prerequisites, flow, activities, assessment and homework.'
    fb=f'''LESSON PLAN: {topic}\nSubject: {subject} | Duration: {minutes} minutes | Level: {level}\n\nLEARNING OBJECTIVES\n- Explain the core ideas of {topic}.\n- Solve at least one representative problem.\n\nLESSON FLOW\n1. Recap and introduction - 10%\n2. Concept explanation - 35%\n3. Guided activity - 30%\n4. Discussion - 15%\n5. Wrap-up and questions - 10%\n\nACTIVITIES\n- Worked example and pair discussion.\n\nASSESSMENT\n- Short exit quiz and participation check.\n\nHOMEWORK\n- Practice three problems on {topic}.'''
    return ask_ai(prompt,fb)

def progress_summary(stat,marks):
    subj='; '.join(f"{m['subject']}: {m['pct']}%" for m in marks) or 'no marks yet'
    fb=f"{stat['name']} has {stat['att']}% attendance and an average internal score of {stat['avg']}%. Subject results: {subj}. Risk level: {stat['risk']}. Focus next on the weakest subject and maintain consistent attendance."
    return ask_ai(f'Write a short academic progress summary. Student: {stat["name"]}; attendance: {stat["att"]}%; average: {stat["avg"]}%; risk: {stat["risk"]}; subjects: {subj}.',fb)
