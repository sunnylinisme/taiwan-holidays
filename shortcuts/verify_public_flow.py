"""Interpret the serialized control flow against in-memory fixtures only.
No Shortcut execution, network, EventKit, or user calendar access.
"""
import copy,datetime as dt,json,plistlib,re
from pathlib import Path
BASE=Path(__file__).resolve().parent
W=plistlib.loads((BASE/'taiwan-holidays-public.plist').read_bytes())
A=W['WFWorkflowActions']
NAME=W['WFWorkflowName']
FIXTURE=copy.deepcopy(W)
for a in FIXTURE['WFWorkflowActions']:
 if a['WFWorkflowActionIdentifier'].endswith('.addnewevent'):a['WFWorkflowActionParameters']['WFCalendarDescriptor']={'Title':'公開測試日曆','Identifier':'test-calendar-id','IsAllCalendar':False}
F=json.loads((BASE.parent/'data/holidays.json').read_text())
TODAY=dt.datetime(2026,10,22,tzinfo=dt.timezone(dt.timedelta(hours=8)))
class Stop(Exception):pass
class VM:
 def __init__(self,events=None,feed=None,shortcuts=None):
  self.shortcuts=copy.deepcopy(shortcuts if shortcuts is not None else [{'name':NAME,'workflow':FIXTURE},{'name':'其他捷徑','workflow':None}]);self.reads=[];self.events=copy.deepcopy(events or []);self.feed=copy.deepcopy(feed or F);self.v={};self.out={};self.writes=0;self.removes=0;self.messages=[]
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
   elif op=='getmyworkflows':r=self.shortcuts
   elif op=='getitemname':r=self.val(p['WFInput'])['name']
   elif op=='text.match':r=re.findall(p['WFMatchTextPattern'],str(self.val(p['text'])))
   elif op=='downloadurl':r=copy.deepcopy(self.feed)
   elif op=='detect.dictionary':
    r=self.val(p['WFInput'])
    if isinstance(r,dict) and 'workflow' in r:self.reads.append(r['name']);r=copy.deepcopy(r['workflow'])
    r=json.loads(r) if isinstance(r,str) else r
   elif op=='gettext':r=self.val(p['WFTextActionText'])
   elif op=='number':r=float(p['WFNumberActionNumber'])
   elif op=='setvariable':self.v[p['WFVariableName']]=self.val(p['WFInput'])
   elif op=='appendvariable':
    old=self.v[p['WFVariableName']];new=self.val(p['WFInput']);self.v[p['WFVariableName']]=(old if isinstance(old,list) else [old])+(new if isinstance(new,list) else [new])
   elif op=='getvalueforkey':r=self.val(p['WFInput'])[p['WFDictionaryKey']]
   elif op=='math':
    l=float(self.val(p['WFInput']));v=float(self.val(p['WFMathOperand']));r=l+v if p['WFMathOperation']=='+' else l-v
   elif op=='count':
    r=self.val(p['Input']);r=len(r) if isinstance(r,list) or p['WFCountType']=='Characters' else (0 if r is None else 1)
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
assert v.writes==expected and len(v.events)==expected
assert all(e['start']==e['end'] for e in v.events)
v2=VM(v.events).run();assert v2.writes==v2.removes==0 and len(v2.events)==len(v.events)
v3=VM(v2.events).run();assert v3.writes==v3.removes==0
# An unrelated all-day event causes a skip, and remains untouched.
manual=copy.deepcopy(v.events[0]);manual['notes']='手動行程';manual['title']='個人假期'
manual_events=[manual]
m=VM(manual_events).run();assert manual in m.events and len(m.events)==expected
# Official cancellation removes only marked events, including matching date/calendar.
newfeed=copy.deepcopy(F);cancel=next(d for d in newfeed['holidays'] if d['date_code']>=20261022)
newfeed['holidays'].remove(cancel);newfeed['cancelled']=[cancel]
other_calendar=copy.deepcopy(v.events[0]);other_calendar['calendar']='其他日曆'
c=VM(v.events+[other_calendar], newfeed).run();assert c.removes==1 and c.writes==0 and other_calendar in c.events
c2=VM(c.events,newfeed).run();assert c2.removes==c2.writes==0
# Missing, renamed, duplicate or empty calendar configuration stops before any write.
for shortcuts in [[],[{'name':NAME+'改名','workflow':FIXTURE}], [{'name':NAME,'workflow':FIXTURE}]*2]:
 blocked=VM(shortcuts=shortcuts).run();assert blocked.writes==blocked.removes==0
empty=copy.deepcopy(FIXTURE)
for a in empty['WFWorkflowActions']:
 if a['WFWorkflowActionIdentifier'].endswith('.addnewevent'):a['WFWorkflowActionParameters']['WFCalendarDescriptor']['Title']=''
e=VM(shortcuts=[{'name':NAME,'workflow':empty}]).run();assert e.writes==e.removes==0
assert v.reads==[NAME]
assert all(e['start']>=TODAY for e in v.events)
assert len(W['WFWorkflowImportQuestions'])==1
assert sum(a['WFWorkflowActionIdentifier'].endswith('.addnewevent') for a in A)==1
assert 'TW-DGPA-PUBLIC-CONFIG' not in str(W) and '2000-01-01' not in str(W)
assert not any(a['WFWorkflowActionIdentifier'].endswith(('.writefile','.savefile','.appendfile')) for a in A)
# Invalid downloaded schema stops before initial setup/event creation.
bad=copy.deepcopy(F);bad['schema']=2
b=VM(feed=bad).run();assert b.writes==b.removes==0
print('PASS: serialized-flow simulation; first run adds only',expected,'future holidays; two repeat runs write/delete zero; manual event preserved; cancellation repeat-safe; missing/duplicate/empty settings and invalid feed stop before writes; unrelated Shortcut contents never read.')
