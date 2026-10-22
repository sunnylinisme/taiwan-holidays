import copy, json, plistlib, uuid
from pathlib import Path

BASE = Path(__file__).resolve().parent
scaffold = {'WFWorkflowClientVersion':'2600', 'WFWorkflowActions':[]}
calendar = {'Title':'', 'IsAllCalendar':False}
NAME = '更新台灣休假日（公開通用版）'
FEED = 'https://raw.githubusercontent.com/sunnylinisme/taiwan-holidays/main/data/holidays.json'
actions = []
def uid(): return str(uuid.uuid4()).upper()
def token(v): return {'WFSerializationType':'WFTextTokenAttachment','Value':v}
def var(n): return token({'Type':'Variable','VariableName':n})
def text(*parts):
    s = ''; attrs = {}
    for p in parts:
        if isinstance(p,dict):
            attrs['{%d, 1}' % (len(s.encode('utf-16-le'))//2)] = p['Value']; s += '\ufffc'
        else: s += str(p)
    return {'WFSerializationType':'WFTextTokenString','Value':{'string':s,'attachmentsByRange':attrs}} if attrs else s
def add(name, **p):
    p['UUID'] = uid()
    actions.append({'WFWorkflowActionIdentifier':'is.workflow.actions.'+name,'WFWorkflowActionParameters':p})
    return token({'Type':'ActionOutput','OutputUUID':p['UUID'],'OutputName':'結果'})
def put(n,v): add('setvariable',WFVariableName=n,WFInput=v); return var(n)
def get(d,key): return add('getvalueforkey',WFInput=d,WFDictionaryKey=key,WFGetDictionaryValueType='Value')
def math(v,op,rhs): return add('math',WFInput=v,WFMathOperation=op,WFMathOperand=str(rhs) if isinstance(rhs,int) else rhs)
def count(v): return add('count',Input=v,WFCountType='Items')
def ifnum(v,op,n):
    g=uid(); add('conditional',WFControlFlowMode=0,GroupingIdentifier=g,WFInput={'Type':'Variable','Variable':v},WFCondition=op,WFNumberValue=str(n)); return g
def otherwise(g): add('conditional',WFControlFlowMode=1,GroupingIdentifier=g)
def endif(g): add('conditional',WFControlFlowMode=2,GroupingIdentifier=g)
def notify(body,title='台灣官方休假日更新'): add('notification',WFNotificationActionTitle=title,WFNotificationActionBody=body,WFNotificationActionSound=False)
def fail_if(v,op,n,message):
    g=ifnum(v,op,n);notify(message,'休假日資料驗證失敗');add('exit');endif(g)
def repeat(v):
    g=uid();add('repeat.each',WFControlFlowMode=0,GroupingIdentifier=g,WFInput=v);return g
def endrepeat(g): add('repeat.each',WFControlFlowMode=2,GroupingIdentifier=g)
def date(v): return add('date',WFDateActionMode='Specified Date',WFDateActionDate=text(v))
def find(start,last,marker=None):
    rows=[{'Property':'Start Date','Operator':1003,'Bounded':True,'Removable':False,'Values':{'Date':start,'AnotherDate':last}},
          {'Property':'Calendar','Operator':4,'Removable':True,'Values':{'Enumeration':{'WFSerializationType':'WFStringSubstitutableState','Value':var('目標行事曆名稱')}}},
          {'Property':'Is All Day','Operator':4,'Removable':True,'Values':{'Bool':True}}]
    if marker is not None:
        value=text(marker)
        rows.append({'Property':'Notes','Operator':99,'Removable':True,'Values':{'String':value}})
    return add('filter.calendarevents',WFContentItemInputParameter='Library',WFContentItemFilter={'WFSerializationType':'WFContentPredicateTableTemplate','Value':{'WFActionParameterFilterPrefix':1,'WFContentPredicateBoundedDate':False,'WFActionParameterFilterTemplates':rows}},WFContentItemLimitEnabled=False)

add('comment',WFCommentActionText='台灣休假日公開通用版 v1.0\n先在 iCloud 建立專用、名稱不重複的可寫入行事曆。安裝設定須填入完整名稱，並在新增行程選擇同一個行事曆。\n只同步今天起的政府行政機關休假日（含週末）。同日已有整日行程即略過；官方修訂僅清理有本捷徑標記的行程。\n不會替你建立行事曆或手機自動化。請先手動測試，再自行設定每月執行。')
configuration_index=len(actions)
calendar_name=add('gettext',WFTextActionText='請填入專用行事曆名稱')
put('目標行事曆名稱',calendar_name)
now=add('date',WFDateActionMode='Current Date')
today=add('format.date',WFDate=text(now),WFDateFormatStyle='Custom',WFDateFormat='yyyyMMdd',WFTimeFormatStyle='None',WFLocale='en_US_POSIX')
download=add('downloadurl',WFURL=FEED,WFHTTPMethod='GET')
feed=add('detect.dictionary',WFInput=download)
schema=get(feed,'schema')
fail_if(math(schema,'-',1),5,0,'GitHub 資料格式版本不符，未同步；既有行程保留。')
valid=get(feed,'valid_until_code')
fail_if(math(valid,'-',today),0,0,'GitHub 資料未涵蓋今天，請檢查專案 Actions 更新狀態；既有行程保留。')
holidays=get(feed,'holidays')
fail_if(count(holidays),0,1,'GitHub 休假日清單為空，未同步；既有行程保留。')
put('新增筆數',add('number',WFNumberActionNumber='0'))
put('略過筆數',add('number',WFNumberActionNumber='0'))
put('移除筆數',add('number',WFNumberActionNumber='0'))
loop=repeat(holidays)
day=put('休假日資料',var('Repeat Item'))
code=get(day,'date_code')
future=ifnum(math(code,'-',today),3,0)
start=date(get(day,'start'))
last=date(get(day,'last_second'))
existing=find(start,last)
missing=ifnum(count(existing),4,0)
title=get(day,'title'); notes=get(day,'notes')
add('addnewevent',WFCalendarItemTitle=text(title),WFCalendarItemStartDate=text(start),WFCalendarItemEndDate=text(start),WFCalendarItemAllDay=True,WFCalendarDescriptor=calendar,WFAlertTime='None',WFCalendarItemNotes=text(notes),ShowWhenRun=False)
put('新增筆數',math(var('新增筆數'),'+',1))
otherwise(missing)
put('略過筆數',math(var('略過筆數'),'+',1))
endif(missing);endif(future);endrepeat(loop)
cancelled=get(feed,'cancelled')
cleanup=repeat(cancelled)
day=put('官方修訂資料',var('Repeat Item'))
code=get(day,'date_code')
future=ifnum(math(code,'-',today),3,0)
start=date(get(day,'start'));last=date(get(day,'last_second'))
marker=get(day,'marker')
owned=find(start,last,marker)
n=count(owned)
hasowned=ifnum(n,2,0)
add('removeevents',WFInputEvents=owned,WFCalendarIncludeFutureEvents=False)
put('移除筆數',math(var('移除筆數'),'+',n))
endif(hasowned);endif(future);endrepeat(cleanup)
updated=get(feed,'generated_at')
notify(text('新增 ',var('新增筆數'),' 筆，已有略過 ',var('略過筆數'),' 筆，官方更正移除 ',var('移除筆數'),' 筆。\n資料最後驗證：',updated))
add('nothing')

w=copy.deepcopy(scaffold)
w['WFWorkflowActions']=actions
w['WFWorkflowName']=NAME
w['WFWorkflowTypes']=['WFWorkflowTypeShowInSearch']
w['WFWorkflowInputContentItemClasses']=[]
w['WFWorkflowIcon']={'WFWorkflowIconGlyphNumber':61440,'WFWorkflowIconStartColor':4282601983}
w['WFWorkflowMinimumClientVersion']=2600
w['WFWorkflowMinimumClientVersionString']='2600'
add_index=next(i for i,a in enumerate(actions) if a['WFWorkflowActionIdentifier'].endswith('.addnewevent'))
w['WFWorkflowImportQuestions']=[
 {'ActionIndex':configuration_index,'ParameterKey':'WFTextActionText','Category':'Parameter','Text':'先在 iCloud 建立專用且名稱不重複的行事曆，在這裡填入完整名稱（須與下一步選擇相同）。','DefaultValue':'台灣休假日'},
 {'ActionIndex':add_index,'ParameterKey':'WFCalendarDescriptor','Category':'Parameter','Text':'選擇上一個步驟填寫的同一個可寫入行事曆；不要選訂閱行事曆。','DefaultValue':{'Title':'','IsAllCalendar':False}}
]
w['WFQuickActionSurfaces']=[]
w.pop('WFWorkflowTriggers',None)
for k in ['WFWorkflowHasOutputFallback','WFWorkflowHasShortcutInputVariables']:w[k]=False
(BASE/'taiwan-holidays-public-unsigned.shortcut').write_bytes(plistlib.dumps(w,fmt=plistlib.FMT_BINARY))
(BASE/'taiwan-holidays-public.plist').write_bytes(plistlib.dumps(w,fmt=plistlib.FMT_XML))
print(json.dumps({'name':NAME,'actions':len(actions),'feed':FEED,'shortcut_executed':False},ensure_ascii=False))
