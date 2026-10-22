"""Interpret the serialized control flow against in-memory fixtures only.
No Shortcut execution, network, EventKit, or user calendar access.
"""
import copy,datetime as dt,json,plistlib
from pathlib import Path
BASE=Path(__file__).resolve().parent
A=plistlib.loads((BASE/'taiwan-holidays-public.plist').read_bytes())['WFWorkflowActions']
F=json.loads((BASE.parent/'data/holidays.json').read_text())
TODAY=dt.datetime(2026,10,22,tzinfo=dt.timezone(dt.timedelta(hours=8)))
class Stop(Exception):pass
class VM:
 def __init__(self,events=None,feed=None):
  self.events=copy.deepcopy(events or []);self.feed=copy.deepcopy(feed or F);self.v={};self.out={};self.writes=0;self.removes=0;self.messages=[]
 def val(self,x):
  if isinstance(x,dict):
   typ=x.get('WFSerializationType');d=x.get('Value',{})
   if typ=='WFTextTokenAttachment':return self.val(d)
   if typ=='WFTextTokenString':
    s=d['string'];tokens=list(d['attachmentsByRange'].values())
    for z in tokens:s=s.replace('\ufffc',str(self.val(z)),1)
    return s
   if typ=='WFStringSubstitutableState':return self.val(d)
   if x.get('Type')=='Variable':return self.val(x['Variable']) if 'Variable' in x else self.v[x['VariableName']]
   if x.get('Type')=='ActionOutput':return self.out[x['OutputUUID']]
  return x
 def seq(self,start,end):
  i=start
  while i<end:
   a=A[i];p=a['WFWorkflowActionParameters'];op=a['WFWorkflowActionIdentifier'].removeprefix('is.workflow.actions.');r=None
   if op in ['conditional','repeat.each'] and p['WFControlFlowMode']==0:
    g=p['GroupingIdentifier'];j=i+1;alt=None
    while not (A[j]['WFWorkflowActionParameters'].get('GroupingIdentifier')==g and A[j]['WFWorkflowActionParameters'].get('WFControlFlowMode')==2):
     if A[j]['WFWorkflowActionParameters'].get('GroupingIdentifier')==g and A[j]['WFWorkflowActionParameters'].get('WFControlFlowMode')==1:alt=j
     j+=1
    if op=='conditional':
     left=float(self.val(p['WFInput']));right=float(p['WFNumberValue']);condition=p['WFCondition']
     ok={0:left<right,2:left>right,3:left>=right,4:left==right,5:left!=right}[condition]
     if ok:self.seq(i+1,alt or j)
     elif alt is not None:self.seq(alt+1,j)
    else:
     values=self.val(p['WFInput']);values=values if isinstance(values,list) else [values]
     for item in values:self.v['Repeat Item']=item;self.seq(i+1,j)
    i=j+1;continue
   if op=='comment' or op=='nothing':pass
   elif op=='date':r=TODAY if p['WFDateActionMode']=='Current Date' else dt.datetime.fromisoformat(str(self.val(p['WFDateActionDate'])))
   elif op=='format.date':r=dt.datetime.fromisoformat(str(self.val(p['WFDate']))).strftime('%Y%m%d')
   elif op=='downloadurl':r=copy.deepcopy(self.feed)
   elif op=='detect.dictionary':
    r=self.val(p['WFInput']);r=json.loads(r) if isinstance(r,str) else r
   elif op=='gettext':r=self.val(p['WFTextActionText'])
   elif op=='number':r=float(p['WFNumberActionNumber'])
   elif op=='setvariable':self.v[p['WFVariableName']]=self.val(p['WFInput'])
   elif op=='appendvariable':
    old=self.v[p['WFVariableName']];new=self.val(p['WFInput']);self.v[p['WFVariableName']]=(old if isinstance(old,list) else [old])+(new if isinstance(new,list) else [new])
   elif op=='getvalueforkey':r=self.val(p['WFInput'])[p['WFDictionaryKey']]
   elif op=='math':
    l=float(self.val(p['WFInput']));v=float(self.val(p['WFMathOperand']));r=l+v if p['WFMathOperation']=='+' else l-v
   elif op=='count':
    r=self.val(p['Input']);r=len(r) if isinstance(r,list) else (0 if r is None else 1)
   elif op=='properties.calendarevents':
    r=self.val(p['WFInput']);r=r[0] if isinstance(r,list) else r;r=r['calendar']
   elif op=='filter.calendarevents':
    rows=p['WFContentItemFilter']['Value']['WFActionParameterFilterTemplates'];r=[]
    for ev in self.events:
     match=True
     for row in rows:
      key=row['Property'];values=row['Values']
      if key=='Start Date':match &= self.val(values['Date'])<=ev['start']<=self.val(values['AnotherDate'])
      elif key=='Calendar':match &= ev['calendar']==self.val(values['Enumeration'])
      elif key=='Is All Day':match &= ev['all_day']==values['Bool']
      elif key=='Notes':match &= self.val(values['String']) in ev['notes']
      else:raise AssertionError(key)
     if match:r.append(ev)
   elif op=='addnewevent':
    r={'calendar':'公開測試日曆','title':self.val(p['WFCalendarItemTitle']),'start':dt.datetime.fromisoformat(str(self.val(p['WFCalendarItemStartDate']))),'end':dt.datetime.fromisoformat(str(self.val(p['WFCalendarItemEndDate']))),'all_day':p['WFCalendarItemAllDay'],'notes':self.val(p['WFCalendarItemNotes'])};self.events.append(r);self.writes+=1
   elif op=='removeevents':
    values=self.val(p['WFInputEvents'])
    for ev in values:self.events.remove(ev);self.removes+=1
   elif op=='notification':self.messages.append(self.val(p['WFNotificationActionBody']))
   elif op=='exit':raise Stop()
   else:raise AssertionError(op)
   self.out[p['UUID']]=r;i+=1
 def run(self):
  try:self.seq(0,len(A))
  except Stop:pass
  return self
v=VM().run();expected=sum(d['date_code']>=20261022 for d in F['holidays'])
assert v.writes==expected+1 and len(v.events)==expected+1
assert all(e['start']==e['end'] for e in v.events)
v2=VM(v.events).run();assert v2.writes==v2.removes==0 and len(v2.events)==len(v.events)
v3=VM(v2.events).run();assert v3.writes==v3.removes==0
# An unrelated all-day event causes a skip, and remains untouched.
manual=copy.deepcopy(v.events[1]);manual['notes']='手動行程';manual['title']='個人假期'
manual_events=[v.events[0],manual]
m=VM(manual_events).run();assert manual in m.events and len(m.events)==expected+1
# Official cancellation removes only marked events, including matching date/calendar.
newfeed=copy.deepcopy(F);cancel=next(d for d in newfeed['holidays'] if d['date_code']>=20261022)
newfeed['holidays'].remove(cancel);newfeed['cancelled']=[cancel]
c=VM(v.events, newfeed).run();assert c.removes==1 and c.writes==0
c2=VM(c.events,newfeed).run();assert c2.removes==c2.writes==0
# Duplicate configuration markers stop before any mutation.
blocked=VM(v.events+[copy.deepcopy(v.events[0])]).run();assert blocked.writes==blocked.removes==0
# Invalid downloaded schema stops before initial setup/event creation.
bad=copy.deepcopy(F);bad['schema']=2
b=VM(feed=bad).run();assert b.writes==b.removes==0
print('PASS: serialized-flow simulation, first-run setup +',expected,'future holidays; 2 repeat runs write/delete zero; manual event preserved; cancellation repeat-safe; duplicate configuration and invalid schema stop before writes.')
