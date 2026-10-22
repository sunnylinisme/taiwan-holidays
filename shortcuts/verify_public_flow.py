"""Interpret the serialized control flow against in-memory fixtures only.
No Shortcut execution, network, EventKit, or user calendar access.
"""
import copy,datetime as dt,json,plistlib,re,itertools
from pathlib import Path
BASE=Path(__file__).resolve().parent
W=plistlib.loads((BASE/'taiwan-holidays-public.plist').read_bytes())
A=W['WFWorkflowActions']
NAME=W['WFWorkflowName']
F=json.loads((BASE.parent/'data/holidays.json').read_text())
TODAY=dt.datetime(2026,10,22,tzinfo=dt.timezone(dt.timedelta(hours=8)))
EVENT_IDS=itertools.count()
class Stop(Exception):pass
class VM:
 def __init__(self,events=None,feed=None,storage=None,cancel_choice=False):
  self.storage=storage if storage is not None else {};self.cancel_choice=cancel_choice;self.prompts=0
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
     left=self.val(p['WFInput']);right=self.val(p['WFConditionalActionString']) if 'WFConditionalActionString' in p else float(p['WFNumberValue']);left=str(left) if 'WFConditionalActionString' in p else float(left);condition=p['WFCondition']
     ok={0:left<right,2:left>right,3:left>=right,4:left==right,5:left!=right}[condition]
     if ok:self.seq(i+1,alt or j)
     elif alt is not None:self.seq(alt+1,j)
    else:
     values=self.val(p['WFInput']);values=values if isinstance(values,list) else [values]
     for item in values:self.v['Repeat Item']=item;self.out[p['UUID']]=item;self.seq(i+1,j)
    i=j+1;continue
   if op=='comment' or op=='nothing':pass
   elif op=='date':r=TODAY if p['WFDateActionMode']=='Current Date' else dt.datetime.fromisoformat(str(self.val(p['WFDateActionDate'])))
   elif op=='format.date':r=dt.datetime.fromisoformat(str(self.val(p['WFDate']))).strftime('%Y%m%d')
   elif op=='getstoredcontent':r=self.storage.get(p['WFStoredContentKey'])
   elif op=='setstoredcontent':self.storage[p['WFStoredContentKey']]=self.val(p['WFInput']);r=self.storage[p['WFStoredContentKey']]
   elif op=='dictionary':r={self.val(q['WFKey']):self.val(q['WFValue']) for q in p['WFItems']['Value']['WFDictionaryFieldValueItems']}
   elif op=='alert':
    if getattr(self,'cancel_explanation',False):raise Stop()
   elif op=='downloadurl':r=copy.deepcopy(self.feed)
   elif op=='detect.dictionary':
    r=self.val(p['WFInput'])
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
    r=self.val(p['Input']);r=0 if r is None else (len(r) if isinstance(r,list) or p['WFCountType']=='Characters' else 1)
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
    choice=p['WFCalendarDescriptor']
    if choice.get('Value',{}).get('Type')=='Ask':
     self.prompts+=1
     if self.cancel_choice:raise Stop()
     calendar=getattr(self,'selected_calendar','公開測試日曆')
    else:
     calendar=self.val(choice)
     assert isinstance(calendar,str), 'Calendar input must be plain text; dictionary becomes JSON title at native runtime'
     if getattr(self,'wrong_calendar',False):calendar='錯誤預設日曆'
    r={'id':next(EVENT_IDS),'calendar':calendar,'title':self.val(p['WFCalendarItemTitle']),'start':dt.datetime.fromisoformat(str(self.val(p['WFCalendarItemStartDate']))),'end':dt.datetime.fromisoformat(str(self.val(p['WFCalendarItemEndDate']))),'all_day':p['WFCalendarItemAllDay'],'notes':self.val(p['WFCalendarItemNotes'])};self.events.append(r);self.writes+=1
   elif op=='removeevents':
    values=self.val(p['WFInputEvents']);values=values if isinstance(values,list) else [values]
    for ev in values:self.events.remove(ev);self.removes+=1
   elif op=='notification':self.messages.append(self.val(p['WFNotificationActionBody']))
   elif op=='exit':raise Stop()
   else:raise AssertionError(op)
   self.out[p['UUID']]=r;i+=1
 def run(self):
  try:self.seq(0,len(A))
  except Stop:pass
  return self
state={}
v=VM(storage=state).run();expected=sum(d['date_code']>=20261022 for d in F['holidays'])
assert v.prompts==1 and v.writes==expected and v.removes==0 and len(v.events)==expected and not state
assert all(e['start']==e['end'] and e['start']>=TODAY for e in v.events)
# Every rerun prompts; the real-holiday seed is removed when already present. Final events unchanged.
v2=VM(v.events).run();assert v2.prompts==1 and v2.writes==v2.removes==1 and v2.events==v.events
v3=VM(v2.events).run();assert v3.prompts==1 and v3.events==v.events
manual=copy.deepcopy(v.events[0]);manual['notes']='手動行程';manual['title']='個人假期'
m=VM([manual]).run();assert m.prompts==1 and m.removes==1 and manual in m.events and len(m.events)==expected
cancelled=VM(cancel_choice=True).run();assert cancelled.prompts==1 and cancelled.writes==cancelled.removes==0
# Switching calendars never treats another calendar's holiday as an existing event.
switch=VM(v.events);switch.selected_calendar='第二個日曆';switch.run()
assert switch.prompts==1 and switch.writes==expected and len(switch.events)==2*expected
assert all(e in switch.events for e in v.events)
rerun=VM(switch.events);rerun.selected_calendar='第二個日曆';rerun.run();assert rerun.events==switch.events
newfeed=copy.deepcopy(F);day=next(d for d in newfeed['holidays'] if d['date_code']>=20261022)
newfeed['holidays'].remove(day);newfeed['cancelled']=[day]
other=copy.deepcopy(v.events[0]);other['calendar']='其他日曆'
c=VM(v.events+[other],newfeed).run();assert c.prompts==1 and c.removes==2 and c.writes==1 and other in c.events
c2=VM(c.events,newfeed).run();assert c2.prompts==1 and c2.removes==c2.writes==1 and c2.events==c.events
bad=copy.deepcopy(F);bad['schema']=2
b=VM(feed=bad).run();assert b.prompts==b.writes==b.removes==0
assert W['WFWorkflowImportQuestions']==[]
assert not any(a['WFWorkflowActionIdentifier'].endswith(('.getmyworkflows','.getstoredcontent','.setstoredcontent','.deletestoredcontent','.writefile','.savefile','.appendfile')) for a in A)
assert 'TW-DGPA-PUBLIC-CONFIG' not in str(W) and '2000-01-01' not in str(W)
bad=VM();bad.wrong_calendar=True;bad.run();assert bad.writes==2 and any('日曆與選擇不符' in x for x in bad.messages)
print('PASS: prompt once EVERY run; no persistent settings; repeat final events unchanged; switches calendars correctly; manual entries preserved; cancel has no changes; corrections scoped; invalid feed stops; wrong destination stops.')

explain=VM();explain.cancel_explanation=True;explain.run();assert explain.prompts==explain.writes==explain.removes==0
print('PASS: canceling purpose explanation has zero prompts or writes.')
