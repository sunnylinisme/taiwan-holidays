import copy, json, plistlib, uuid
from pathlib import Path

BASE = Path(__file__).resolve().parent
scaffold = {'WFWorkflowClientVersion':'2600', 'WFWorkflowActions':[]}
calendar = {'Title':'', 'IsAllCalendar':False}
NAME = '更新台灣休假日（公開通用版）'
FEED = 'https://raw.githubusercontent.com/sunnylinisme/taiwan-holidays-shortcuts/main/data/holidays.json'
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
def loop_item(g):
    action=next(a for a in actions if a['WFWorkflowActionParameters'].get('GroupingIdentifier')==g and a['WFWorkflowActionParameters'].get('WFControlFlowMode')==0)
    return token({'Type':'ActionOutput','OutputUUID':action['WFWorkflowActionParameters']['UUID'],'OutputName':'Repeat Item'})
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

def chars(v):return add('count',Input=v,WFCountType='Characters')
add('comment',WFCommentActionText='台灣休假日公開通用版 v3.2\n每次執行都詢問行事曆，不儲存選擇、不預選日曆、不建立設定行程。請選可寫入且名稱唯一的專用日曆。\n原生選擇器附在第一筆真正休假日的新增動作：若同日已有整日行程，只移除本次新建副本並計為略過，保留原有行程。可能出現刪除許可提示；若拒絕或中斷，請檢查該日是否留下副本。\n後續日期同日已有整日行程就略過；新增後核對實際日曆，不符即停止。只處理今天起的政府行政機關休假日（含週末）。請勿同時執行兩次。每月自動化仍需你選日曆。')
now=add('date',WFDateActionMode='Current Date')
today=add('format.date',WFDate=text(now),WFDateFormatStyle='Custom',WFDateFormat='yyyyMMdd',WFTimeFormatStyle='None',WFLocale='en_US_POSIX')
feed=add('detect.dictionary',WFInput=add('downloadurl',WFURL=FEED,WFHTTPMethod='GET'))
fail_if(math(get(feed,'schema'),'-',1),5,0,'GitHub 資料格式版本不符，未同步。')
fail_if(math(get(feed,'valid_until_code'),'-',today),0,0,'GitHub 資料未涵蓋今天，請檢查專案 Actions；既有行程保留。')
holidays=get(feed,'holidays')
fail_if(count(holidays),0,1,'GitHub 休假日清單為空，未同步。')
for n in ['新增筆數','略過筆數','移除筆數','本次首次新增日期碼']:put(n,add('number',WFNumberActionNumber='0'))
put('已找到初始化日期',add('number',WFNumberActionNumber='0'))
search=repeat(holidays)
candidate=put('初始化候選日期',loop_item(search))
not_yet=ifnum(var('已找到初始化日期'),4,0)
future=ifnum(math(get(candidate,'date_code'),'-',today),3,0)
put('初始化休假日',candidate)
put('已找到初始化日期',add('number',WFNumberActionNumber='1'))
endif(future);endif(not_yet);endrepeat(search)
fail_if(var('已找到初始化日期'),4,0,'目前資料沒有今天起的休假日，未開始設定，也未新增行程。請等官方公布新年度資料。')
first=var('初始化休假日')
seed_start=date(get(first,'start'));seed_last=date(get(first,'last_second'))
add('alert',WFAlertActionTitle='選擇本次同步的行事曆',WFAlertActionMessage='接下來請選擇本次要加入「台灣國定假日」的行事曆。\n空白日曆也可以使用；已有休假日會保留。\n選擇時會先新增第一筆真正的休假日；若同日已有整日行程，只刪除這次新建的副本。請讓刪除步驟完成。',WFAlertActionCancelButtonShown=True)
seed=add('addnewevent',WFCalendarItemTitle=text(get(first,'title')),WFCalendarItemStartDate=text(seed_start),WFCalendarItemEndDate=text(seed_start),WFCalendarItemAllDay=True,WFCalendarDescriptor=token({'Type':'Ask'}),WFAlertTime='None',WFCalendarItemNotes=text(get(first,'notes')),ShowWhenRun=False)
put('目標行事曆名稱',add('properties.calendarevents',WFInput=seed,WFContentItemPropertyName='Calendar'))
fail_if(chars(var('目標行事曆名稱')),0,1,'無法取得這次選定的日曆名稱，已停止。請檢查剛新增的休假日。')
existing_seed=find(seed_start,seed_last)
duplicate=ifnum(count(existing_seed),2,1)
add('removeevents',WFInputEvents=seed,WFCalendarIncludeFutureEvents=False)
put('略過筆數',math(var('略過筆數'),'+',1))
otherwise(duplicate)
put('新增筆數',math(var('新增筆數'),'+',1))
endif(duplicate)
put('本次首次新增日期碼',get(first,'date_code'))
fail_if(chars(var('目標行事曆名稱')),0,1,'尚未設定目標日曆，本次未繼續同步。')
# A calendar variable must resolve to plain text. A dictionary becomes JSON text, not a calendar descriptor.
descriptor=var('目標行事曆名稱')
descriptor['Value']['Aggrandizements']=[{'Type':'WFCoercionVariableAggrandizement','CoercionItemClass':'WFStringContentItem'}]
loop=repeat(holidays)
day=put('休假日資料',loop_item(loop))
code=get(day,'date_code')
future=ifnum(math(code,'-',today),3,0)
not_seed=ifnum(math(code,'-',var('本次首次新增日期碼')),5,0)
start=date(get(day,'start'));last=date(get(day,'last_second'))
existing=find(start,last)
missing=ifnum(count(existing),4,0)
created=add('addnewevent',WFCalendarItemTitle=text(get(day,'title')),WFCalendarItemStartDate=text(start),WFCalendarItemEndDate=text(start),WFCalendarItemAllDay=True,WFCalendarDescriptor=descriptor,WFAlertTime='None',WFCalendarItemNotes=text(get(day,'notes')),ShowWhenRun=False)
actual=add('gettext',WFTextActionText=text(add('properties.calendarevents',WFInput=created,WFContentItemPropertyName='Calendar')))
g=uid()
add('conditional',WFControlFlowMode=0,GroupingIdentifier=g,WFInput={'Type':'Variable','Variable':actual},WFCondition=5,WFConditionalActionString=text(var('目標行事曆名稱')))
notify(text('新增行程的日曆與選擇不符，已停止後續同步。\n預期：',var('目標行事曆名稱'),'\n實際：',actual,'\n請檢查這次剛新增的一筆行程。'),'休假日同步已停止')
add('exit');endif(g)
put('新增筆數',math(var('新增筆數'),'+',1))
otherwise(missing)
put('略過筆數',math(var('略過筆數'),'+',1))
endif(missing);endif(not_seed);endif(future);endrepeat(loop)
cleanup=repeat(get(feed,'cancelled'))
day=put('官方修訂資料',loop_item(cleanup))
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
w.update(WFWorkflowClientVersion='5037.0.19',WFWorkflowActions=actions,WFWorkflowName=NAME,WFWorkflowTypes=['WFWorkflowTypeShowInSearch'],WFWorkflowInputContentItemClasses=[],WFWorkflowIcon={'WFWorkflowIconGlyphNumber':61440,'WFWorkflowIconStartColor':4282601983},WFWorkflowMinimumClientVersion=900,WFWorkflowMinimumClientVersionString='900',WFQuickActionSurfaces=[],WFWorkflowHasOutputFallback=False,WFWorkflowHasShortcutInputVariables=False,WFWorkflowImportQuestions=[])
(BASE/'taiwan-holidays-public-unsigned.shortcut').write_bytes(plistlib.dumps(w,fmt=plistlib.FMT_BINARY))
(BASE/'taiwan-holidays-public.plist').write_bytes(plistlib.dumps(w,fmt=plistlib.FMT_XML))
print(json.dumps({'name':NAME,'version':'3.2','actions':len(actions),'setup_questions':0,'runtime_calendar_prompt':1,'shortcut_executed':False},ensure_ascii=False))
