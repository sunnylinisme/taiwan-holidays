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

def chars(v):return add('count',Input=v,WFCountType='Characters')
add('comment',WFCommentActionText='台灣休假日公開通用版 v3.1\n每次先說明用途，再用唯讀的「取得即將到來的行程」詢問日曆。只選一個可寫入、名稱唯一的專用日曆，勿選「所有行事曆」。確認目標後才下載及查重。\n此內建方式須從一筆既有未來行程讀取所選日曆名稱；沒有未來行程會安全停止，無法初始化空白日曆。不會為了選擇而新增或刪除行程，不保存選擇。\n同日已有整日行程即略過；缺少才新增。新增後核對實際日曆，不符即停止。官方更正僅清理所選日曆的標記行程。請勿同時執行兩次。')
add('alert',WFAlertActionTitle='選擇本次同步的行事曆',WFAlertActionMessage='接下來請選擇本次要同步「台灣休假日」的行事曆。\n只選一個可寫入的日曆，勿選「所有行事曆」。已有的整日休假日會直接略過。\n此步驟只讀取一筆既有未來行程來辨識日曆，不會新增或刪除。若日曆沒有未來行程，將安全停止。',WFAlertActionCancelButtonShown=True)
selected=add('getupcomingevents',WFGetUpcomingItemCalendar=token({'Type':'Ask'}),WFGetUpcomingItemCount=1,WFDateSpecifier='Any Day')
fail_if(count(selected),4,0,'所選日曆沒有可讀取的未來行程，無法辨識目標。本次未新增或刪除任何行程。此內建方式無法初始化空白日曆。')
put('目標行事曆名稱',add('gettext',WFTextActionText=text(add('properties.calendarevents',WFInput=selected,WFContentItemPropertyName='Calendar'))))
fail_if(chars(var('目標行事曆名稱')),0,1,'無法辨識所選日曆名稱，本次未新增或刪除任何行程。')
add('alert',WFAlertActionTitle='確認本次同步目標',WFAlertActionMessage=text('本次將同步休假日至「',var('目標行事曆名稱'),'」。\n同日已有整日行程會直接略過，缺少才新增。\n若這不是你要的日曆，請取消。'),WFAlertActionCancelButtonShown=True)
now=add('date',WFDateActionMode='Current Date')
today=add('format.date',WFDate=text(now),WFDateFormatStyle='Custom',WFDateFormat='yyyyMMdd',WFTimeFormatStyle='None',WFLocale='en_US_POSIX')
feed=add('detect.dictionary',WFInput=add('downloadurl',WFURL=FEED,WFHTTPMethod='GET'))
fail_if(math(get(feed,'schema'),'-',1),5,0,'GitHub 資料格式版本不符，未同步。')
fail_if(math(get(feed,'valid_until_code'),'-',today),0,0,'GitHub 資料未涵蓋今天，請檢查專案 Actions；既有行程保留。')
holidays=get(feed,'holidays')
fail_if(count(holidays),0,1,'GitHub 休假日清單為空，未同步。')
for n in ['新增筆數','略過筆數','移除筆數']:put(n,add('number',WFNumberActionNumber='0'))
# A calendar variable must resolve to plain text. A dictionary becomes JSON text, not a calendar descriptor.
descriptor=var('目標行事曆名稱')
descriptor['Value']['Aggrandizements']=[{'Type':'WFCoercionVariableAggrandizement','CoercionItemClass':'WFStringContentItem'}]
loop=repeat(holidays)
day=put('休假日資料',loop_item(loop))
code=get(day,'date_code')
future=ifnum(math(code,'-',today),3,0)
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
endif(missing);endif(future);endrepeat(loop)
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
print(json.dumps({'name':NAME,'version':'3.1','actions':len(actions),'setup_questions':0,'runtime_calendar_prompt':1,'shortcut_executed':False},ensure_ascii=False))
