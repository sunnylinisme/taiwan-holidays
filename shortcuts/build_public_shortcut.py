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

STORAGE_KEY='TW-DGPA-TargetCalendar-v2'
def chars(v):return add('count',Input=v,WFCountType='Characters')
def dictionary_text(key,value):
    k={'WFSerializationType':'WFTextTokenString','Value':{'string':key,'attachmentsByRange':{}}}
    v=text(value)
    if isinstance(v,str):v={'WFSerializationType':'WFTextTokenString','Value':{'string':v,'attachmentsByRange':{}}}
    return add('dictionary',WFItems={'WFSerializationType':'WFDictionaryFieldValue','Value':{'WFDictionaryFieldValueItems':[{'WFItemType':0,'WFKey':k,'WFValue':v}]}})
add('comment',WFCommentActionText='台灣休假日公開通用版 v2.0（iOS 27 以上）\n第一次執行才詢問日曆，之後用捷徑內建儲存記住選擇。安裝不用設定，不預選日曆，不建立設定行程或外部設定檔。\n第一次會同步第一筆真正的未來休假日以取得你選的日曆名稱；同日已有整日行程時，只移除本次剛建立的重複行程。可能出現系統刪除許可提示。\n請選可寫入的專用日曆，各帳號間避免同名。日後可在此捷徑的「儲存空間」刪除 TW-DGPA-TargetCalendar-v2，下次會重新詢問。\n只處理今天起的政府行政機關休假日（含週末）；已有整日行程即略過。請勿同時執行兩次。')
now=add('date',WFDateActionMode='Current Date')
today=add('format.date',WFDate=text(now),WFDateFormatStyle='Custom',WFDateFormat='yyyyMMdd',WFTimeFormatStyle='None',WFLocale='en_US_POSIX')
feed=add('detect.dictionary',WFInput=add('downloadurl',WFURL=FEED,WFHTTPMethod='GET'))
fail_if(math(get(feed,'schema'),'-',1),5,0,'GitHub 資料格式版本不符，未同步。')
fail_if(math(get(feed,'valid_until_code'),'-',today),0,0,'GitHub 資料未涵蓋今天，請檢查專案 Actions；既有行程保留。')
holidays=get(feed,'holidays')
fail_if(count(holidays),0,1,'GitHub 休假日清單為空，未同步。')
for n in ['新增筆數','略過筆數','移除筆數','本次首次新增日期碼']:put(n,add('number',WFNumberActionNumber='0'))
saved=add('getstoredcontent',WFStoredContentKey=STORAGE_KEY,WFStoredContentGlobalValue=False)
put('目標行事曆名稱',saved)
setup=ifnum(chars(var('目標行事曆名稱')),0,1)
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
seed=add('addnewevent',WFCalendarItemTitle=text(get(first,'title')),WFCalendarItemStartDate=text(seed_start),WFCalendarItemEndDate=text(seed_start),WFCalendarItemAllDay=True,WFCalendarDescriptor=token({'Type':'Ask'}),WFAlertTime='None',WFCalendarItemNotes=text(get(first,'notes')),ShowWhenRun=False)
put('目標行事曆名稱',add('properties.calendarevents',WFInput=seed,WFContentItemPropertyName='Calendar'))
fail_if(chars(var('目標行事曆名稱')),0,1,'無法取得選定日曆名稱，尚未儲存選擇。請檢查剛新增的休假日。')
existing_seed=find(seed_start,seed_last)
duplicate=ifnum(count(existing_seed),2,1)
add('removeevents',WFInputEvents=seed,WFCalendarIncludeFutureEvents=False)
otherwise(duplicate)
put('新增筆數',math(var('新增筆數'),'+',1))
put('本次首次新增日期碼',get(first,'date_code'))
endif(duplicate)
add('setstoredcontent',WFStoredContentKey=STORAGE_KEY,WFStoredContentGlobalValue=False,WFInput=text(var('目標行事曆名稱')))
endif(setup)
fail_if(chars(var('目標行事曆名稱')),0,1,'尚未設定目標日曆，本次未繼續同步。')
descriptor=dictionary_text('Title',var('目標行事曆名稱'))
descriptor['Value']['Aggrandizements']=[{'Type':'WFCoercionVariableAggrandizement','CoercionItemClass':'WFDictionaryContentItem'}]
loop=repeat(holidays)
day=put('休假日資料',loop_item(loop))
code=get(day,'date_code')
future=ifnum(math(code,'-',today),3,0)
not_seed=ifnum(math(code,'-',var('本次首次新增日期碼')),5,0)
start=date(get(day,'start'));last=date(get(day,'last_second'))
existing=find(start,last)
missing=ifnum(count(existing),4,0)
add('addnewevent',WFCalendarItemTitle=text(get(day,'title')),WFCalendarItemStartDate=text(start),WFCalendarItemEndDate=text(start),WFCalendarItemAllDay=True,WFCalendarDescriptor=descriptor,WFAlertTime='None',WFCalendarItemNotes=text(get(day,'notes')),ShowWhenRun=False)
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
print(json.dumps({'name':NAME,'version':'2.0','actions':len(actions),'setup_questions':0,'runtime_calendar_prompt':1,'shortcut_executed':False},ensure_ascii=False))
