import docx,re,json,os,subprocess,glob

def text_of(p):
    if p.endswith('.pdf'):
        return subprocess.run(['pdftotext','-layout',p,'-'],capture_output=True,text=True).stdout
    d=docx.Document(p); out=[]
    # body order: paragraphs and tables interleaved
    from docx.table import Table; from docx.text.paragraph import Paragraph
    for el in d.element.body.iterchildren():
        if el.tag.endswith('}p'): out.append(Paragraph(el,d).text)
        elif el.tag.endswith('}tbl'):
            t=Table(el,d)
            for r in t.rows:
                seen=[]
                for c in r.cells:
                    if c.text not in seen: seen.append(c.text)
                out.append('\n'.join(seen))
    return '\n'.join(out)
HEADS=[('standards',r'PA Standard\(s\):?'),('essential_questions',r'Essential Question\(s\):?'),('objectives',r'Objectives/Performance Expectations'),
 ('assessment',r'Assessment Evidence/Level of Learning'),('differentiation',r'Differentiated Instruction:?'),('environment',r'Describe Classroom/Behavior Management Plan & Routines'),
 ('prior_knowledge',r'Activate Prior Knowledge/Motivation:?'),('materials',r'Materials Needed:?'),('vocabulary',r'Vocabulary \(New or Review\):?'),
 ('sequence',r'Sequence of the Lesson:?'),('closure',r'Closure:?')]
BOILER=[r'Students will consider and reflect on throughout the lesson:?',r'What will students know and be able to do as a result of this lesson\??',
 r'Students will show what they know by evidence of/list names of formative or summative checks, quizzes, tests which indicate evidence of learning:?',
 r'Modifications in instruction and assessment for students with learning differences, specifically those with 504.s and IEP.s\. Extensions/Enrichment in instruction and assessment for students who are above grade level and/or gifted\.?',
 r'Preparing students for the lesson: How will you activate prior knowledge, build background, or review previous lessons as well as motivate students for the lesson\??',
 r'What learning activities/strategies will you use to engage the students in the learning\? What will students do to use and apply new concepts or skills \(independent practice if relevant\)\?\s*How will you monitor and guide their performance\? Include relevant vocabulary\. Use bullets to sequence your lesson\.?',
 r'What will you do to bring closure to the lesson\? How will you summarize this lesson and preview the lesson that will follow\??',
 r'Domain I+:?\s*(Planning and Preparation|Classroom Environment|Instruction)?:?',r'\(Must be used for each lesson observed by University Supervisor\)']
def parse(t):
    t=t.split('Reflection Guidelines')[0]
    pos=[]
    for k,h in HEADS:
        m=re.search(h,t)
        if m: pos.append((m.start(),m.end(),k))
    pos.sort()
    secs={}
    for i,(s,e,k) in enumerate(pos):
        end=pos[i+1][0] if i+1<len(pos) else len(t)
        body=t[e:end]
        for b in BOILER: body=re.sub(b,'',body)
        lines=[re.sub(r'^[\s•\-–·]+','',l).strip() for l in body.split('\n')]
        lines=[l for l in lines if l and not re.fullmatch(r'[|\s]*',l)]
        secs[k]=lines
    head=t[:pos[0][0]] if pos else t
    m=re.search(r'Subject Area:\s*(.*?)\s+Grade Level:\s*([^\n]*)',head)
    meta={'subject':m.group(1).strip() if m else None,'grade':m.group(2).strip() if m else None}
    return meta,secs
