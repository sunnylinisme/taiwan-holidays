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
def find(start,last,marker=None,configured=True):
    rows=[{'Property':'Start Date','Operator':1003,'Bounded':True,'Removable':False,'Values':{'Date':start,'AnotherDate':last}},
          {'Property':'Calendar','Operator':4,'Removable':True,'Values':{'Enumeration':{'WFSerializationType':'WFStringSubstitutableState','Value':var('目標行事曆名稱')}}},
          {'Property':'Is All Day','Operator':4,'Removable':True,'Values':{'Bool':True}}]
    if not configured: rows=[r for r in rows if r['Property']!='Calendar']
    if marker is not None:
        value=text(marker)
        rows.append({'Property':'Notes','Operator':99,'Removable':True,'Values':{'String':value}})
    return add('filter.calendarevents',WFContentItemInputParameter='Library',WFContentItemFilter={'WFSerializationType':'WFContentPredicateTableTemplate','Value':{'WFActionParameterFilterPrefix':1,'WFContentPredicateBoundedDate':False,'WFActionParameterFilterTemplates':rows}},WFContentItemLimitEnabled=False)

CONFIG_MARKER='TW-DGPA-PUBLIC-CONFIG-V1:20000101'
add('comment',WFCommentActionText='台灣休假日公開通用版 v1.1\n安裝時只選一次可寫入的專用行事曆，不必輸入名稱。首次執行會在 2000/1/1 建立「休假日同步設定（請保留）」整日行程，之後由它取得日曆名稱。\n請保留設定行程，不要移到其他日曆；所有帳號間請避免同名日曆。更換目標日曆前，先刪除舊設定行程，再重新安裝並選擇新日曆。每人只使用一份公開通用版。\n只處理今天起的政府行政機關休假日（含週末）；同日已有整日行程即略過。請勿同時啟動兩次。\n官方修訂只清理有本捷徑標記的行程。手機每月排程自行設定。')
now=add('date',WFDateActionMode='Current Date')
today=add('format.date',WFDate=text(now),WFDateFormatStyle='Custom',WFDateFormat='yyyyMMdd',WFTimeFormatStyle='None',WFLocale='en_US_POSIX')
feed=add('detect.dictionary',WFInput=add('downloadurl',WFURL=FEED,WFHTTPMethod='GET'))
fail_if(math(get(feed,'schema'),'-',1),5,0,'GitHub 資料格式版本不符，未同步。')
fail_if(math(get(feed,'valid_until_code'),'-',today),0,0,'GitHub 資料未涵蓋今天，請檢查專案 Actions；既有行程保留。')
holidays=get(feed,'holidays')
fail_if(count(holidays),0,1,'GitHub 休假日清單為空，未同步。')
for n in ['新增筆數','略過筆數','移除筆數']:put(n,add('number',WFNumberActionNumber='0'))
put('目標行事曆名稱',add('gettext',WFTextActionText=''))
config_start=date('2000-01-01T00:00:00+08:00');config_last=date('2000-01-01T23:59:59+08:00')
anchors=put('設定行程',find(config_start,config_last,CONFIG_MARKER,configured=False))
anchor_count=put('設定行程數',count(anchors))
fail_if(anchor_count,2,1,'找到多筆休假日同步設定，為避免寫錯日曆，本次停止。請只保留目標日曆中 2000/1/1 的一筆設定行程。')
has_anchor=ifnum(anchor_count,4,1)
put('目標行事曆名稱',add('properties.calendarevents',WFInput=anchors,WFContentItemPropertyName='Calendar'))
endif(has_anchor)
config={'date_code':20000101,'title':'休假日同步設定（請保留）','start':'2000-01-01T00:00:00+08:00','last_second':'2000-01-01T23:59:59+08:00','notes':CONFIG_MARKER+'\n台灣休假日同步設定：此行程所在日曆是同步目標。請保留，不要移動。\n若要更換日曆，刪除此設定行程後重新安裝捷徑並選擇新日曆。\nhttps://github.com/sunnylinisme/taiwan-holidays'}
put('待同步項目',add('detect.dictionary',WFInput=add('gettext',WFTextActionText=json.dumps(config,ensure_ascii=False))))
add('appendvariable',WFVariableName='待同步項目',WFInput=holidays)
loop=repeat(var('待同步項目'))
day=put('休假日資料',var('Repeat Item'))
code=get(day,'date_code');start=date(get(day,'start'));last=date(get(day,'last_second'))
put('應新增',add('number',WFNumberActionNumber='0'))
is_config=ifnum(math(code,'-',20000101),4,0)
no_anchor=ifnum(var('設定行程數'),4,0)
put('應新增',add('number',WFNumberActionNumber='1'))
endif(no_anchor)
otherwise(is_config)
future=ifnum(math(code,'-',today),3,0)
existing=find(start,last)
missing=ifnum(count(existing),4,0)
put('應新增',add('number',WFNumberActionNumber='1'))
otherwise(missing)
put('略過筆數',math(var('略過筆數'),'+',1))
endif(missing);endif(future);endif(is_config)
should_add=ifnum(var('應新增'),4,1)
title=get(day,'title');notes=get(day,'notes')
add_index=len(actions)
new=add('addnewevent',WFCalendarItemTitle=text(title),WFCalendarItemStartDate=text(start),WFCalendarItemEndDate=text(start),WFCalendarItemAllDay=True,WFCalendarDescriptor=calendar,WFAlertTime='None',WFCalendarItemNotes=text(notes),ShowWhenRun=False)
put('目標行事曆名稱',add('properties.calendarevents',WFInput=new,WFContentItemPropertyName='Calendar'))
not_config=ifnum(math(code,'-',20000101),5,0)
put('新增筆數',math(var('新增筆數'),'+',1))
endif(not_config);endif(should_add);endrepeat(loop)
cleanup=repeat(get(feed,'cancelled'))
day=put('官方修訂資料',var('Repeat Item'))
future=ifnum(math(get(day,'date_code'),'-',today),3,0)
start=date(get(day,'start'));last=date(get(day,'last_second'))
owned=find(start,last,get(day,'marker'));n=count(owned)
hasowned=ifnum(n,2,0)
add('removeevents',WFInputEvents=owned,WFCalendarIncludeFutureEvents=False)
put('移除筆數',math(var('移除筆數'),'+',n))
endif(hasowned);endif(future);endrepeat(cleanup)
notify(text('目標：',var('目標行事曆名稱'),'\n新增 ',var('新增筆數'),' 筆，已有略過 ',var('略過筆數'),' 筆，官方更正移除 ',var('移除筆數'),' 筆。\n資料最後驗證：',get(feed,'generated_at')))
add('nothing')
w=copy.deepcopy(scaffold)
w.update(WFWorkflowActions=actions,WFWorkflowName=NAME,WFWorkflowTypes=['WFWorkflowTypeShowInSearch'],WFWorkflowInputContentItemClasses=[],WFWorkflowIcon={'WFWorkflowIconGlyphNumber':61440,'WFWorkflowIconStartColor':4282601983},WFWorkflowMinimumClientVersion=2600,WFWorkflowMinimumClientVersionString='2600',WFQuickActionSurfaces=[],WFWorkflowHasOutputFallback=False,WFWorkflowHasShortcutInputVariables=False)
w['WFWorkflowImportQuestions']=[{'ActionIndex':add_index,'ParameterKey':'WFCalendarDescriptor','Category':'Parameter','Text':'選擇專用、可寫入的行事曆（沒有就先在 iCloud 建立）。不用填名稱。所有帳號間請避免同名日曆。','DefaultValue':{'Title':'','IsAllCalendar':False}}]
(BASE/'taiwan-holidays-public-unsigned.shortcut').write_bytes(plistlib.dumps(w,fmt=plistlib.FMT_BINARY))
(BASE/'taiwan-holidays-public.plist').write_bytes(plistlib.dumps(w,fmt=plistlib.FMT_XML))
print(json.dumps({'name':NAME,'version':'1.1','actions':len(actions),'setup_questions':1,'shortcut_executed':False},ensure_ascii=False))
