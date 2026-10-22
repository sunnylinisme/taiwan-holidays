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

add('comment',WFCommentActionText='台灣休假日公開通用版 v1.3\n安裝只選一次可寫入的專用行事曆，不必輸入名稱。不建立設定行程或設定檔。\n透過「取得我的捷徑」讀取此捷徑「新增行程」已保存的日曆選擇，讓查重、清理與新增共用設定。首次需允許讀取捷徑；不會執行其他捷徑。\n請保留名稱「更新台灣休假日（公開通用版）」，並只保留一份；各帳號間請避免同名日曆。讀取設定失敗會在寫入前停止，不改用預設日曆。\n只處理今天起的政府行政機關休假日（含週末）；同日已有整日行程即略過。請勿同時啟動兩次。手機每月排程自行設定。')
for n in ['符合名稱捷徑數','設定讀取成功數']:put(n,add('number',WFNumberActionNumber='0'))
put('目標行事曆名稱',add('gettext',WFTextActionText=''))
all_shortcuts=add('getmyworkflows')
self_loop=repeat(all_shortcuts)
candidate=put('候選捷徑',loop_item(self_loop))
shortcut_name=add('getitemname',WFInput=candidate)
name_matches=add('text.match',text=text(shortcut_name),WFTextActionText=text(shortcut_name),WFMatchTextPattern='^更新台灣休假日（公開通用版）$',WFMatchTextCaseSensitive=True,ShowWhenRun=False)
selected=ifnum(count(name_matches),4,1)
put('符合名稱捷徑數',math(var('符合名稱捷徑數'),'+',1))
put('本捷徑動作',get(add('detect.dictionary',WFInput=candidate),'WFWorkflowActions'))
endif(selected);endrepeat(self_loop)
fail_if(var('符合名稱捷徑數'),5,1,'找不到唯一的公開通用版。請保留原名稱「更新台灣休假日（公開通用版）」並只保留一份；本次沒有同步。')
put('讀取動作數',count(var('本捷徑動作')))
action_loop=repeat(var('本捷徑動作'))
action=put('候選動作',loop_item(action_loop))
identifier=get(action,'WFWorkflowActionIdentifier')
matching=add('text.match',text=text(identifier),WFTextActionText=text(identifier),WFMatchTextPattern='^is\\.workflow\\.actions\\.addnewevent$',WFMatchTextCaseSensitive=True,ShowWhenRun=False)
selected_action=ifnum(count(matching),4,1)
descriptor=get(get(action,'WFWorkflowActionParameters'),'WFCalendarDescriptor')
put('目標行事曆名稱',get(descriptor,'Title'))
put('設定讀取成功數',math(var('設定讀取成功數'),'+',1))
endif(selected_action);endrepeat(action_loop)
fail_if(var('設定讀取成功數'),5,1,text('無法讀取唯一的新增行程設定（找到 ',var('設定讀取成功數'),' 個／共 ',var('讀取動作數'),' 個動作）。請回報此數字；本次沒有同步。'))
fail_if(add('count',Input=var('目標行事曆名稱'),WFCountType='Characters'),0,1,'行事曆設定為空，請重新安裝並選擇可寫入的日曆；本次沒有同步。')
now=add('date',WFDateActionMode='Current Date')
today=add('format.date',WFDate=text(now),WFDateFormatStyle='Custom',WFDateFormat='yyyyMMdd',WFTimeFormatStyle='None',WFLocale='en_US_POSIX')
feed=add('detect.dictionary',WFInput=add('downloadurl',WFURL=FEED,WFHTTPMethod='GET'))
fail_if(math(get(feed,'schema'),'-',1),5,0,'GitHub 資料格式版本不符，未同步。')
fail_if(math(get(feed,'valid_until_code'),'-',today),0,0,'GitHub 資料未涵蓋今天，請檢查專案 Actions；既有行程保留。')
holidays=get(feed,'holidays')
fail_if(count(holidays),0,1,'GitHub 休假日清單為空，未同步。')
for n in ['新增筆數','略過筆數','移除筆數']:put(n,add('number',WFNumberActionNumber='0'))
loop=repeat(holidays)
day=put('休假日資料',loop_item(loop))
code=get(day,'date_code')
future=ifnum(math(code,'-',today),3,0)
start=date(get(day,'start'));last=date(get(day,'last_second'))
existing=find(start,last)
missing=ifnum(count(existing),4,0)
title=get(day,'title');notes=get(day,'notes')
add_index=len(actions)
add('addnewevent',WFCalendarItemTitle=text(title),WFCalendarItemStartDate=text(start),WFCalendarItemEndDate=text(start),WFCalendarItemAllDay=True,WFCalendarDescriptor=calendar,WFAlertTime='None',WFCalendarItemNotes=text(notes),ShowWhenRun=False)
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
w.update(WFWorkflowActions=actions,WFWorkflowName=NAME,WFWorkflowTypes=['WFWorkflowTypeShowInSearch'],WFWorkflowInputContentItemClasses=[],WFWorkflowIcon={'WFWorkflowIconGlyphNumber':61440,'WFWorkflowIconStartColor':4282601983},WFWorkflowMinimumClientVersion=2600,WFWorkflowMinimumClientVersionString='2600',WFQuickActionSurfaces=[],WFWorkflowHasOutputFallback=False,WFWorkflowHasShortcutInputVariables=False)
w['WFWorkflowImportQuestions']=[{'ActionIndex':add_index,'ParameterKey':'WFCalendarDescriptor','Category':'Parameter','Text':'選擇專用、可寫入的行事曆（沒有就先在 iCloud 建立）。不用填名稱，也不建立設定行程。各帳號間請避免同名日曆。','DefaultValue':{'Title':'','IsAllCalendar':False}}]
(BASE/'taiwan-holidays-public-unsigned.shortcut').write_bytes(plistlib.dumps(w,fmt=plistlib.FMT_BINARY))
(BASE/'taiwan-holidays-public.plist').write_bytes(plistlib.dumps(w,fmt=plistlib.FMT_XML))
print(json.dumps({'name':NAME,'version':'1.3','actions':len(actions),'setup_questions':1,'shortcut_executed':False},ensure_ascii=False))
