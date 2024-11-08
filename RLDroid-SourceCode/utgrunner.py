import uiautomator2 as u2
import random
import time
import xml.dom.minidom as minidom
from xml.dom.minidom import parseString

d = u2.connect('127.0.0.1:62001')
pack = d.info['currentPackageName']
crashList = []
height = d.info['displayHeight']
width = d.info['displayWidth']
mainAct = d.app_info(pack)['mainActivity']
fText = 'abc'
timeout = 60 * 5
waitTime = 0.6
rTime = 10  # response time of widget
frequencyCap = 4
visitMap = {}
stateList = []
tranList = []
epsilon = 0.8
alpha = 0.1
gamma = 0.9
q_l = -8.0  # lower boundary of q

class Event:
    def __init__(self, w_id, text, w_type, desc, w_img, e_type, q=0, r=0):
        self.w_id = w_id
        self.text = text
        self.w_type = w_type
        self.desc = desc
        self.w_img = w_img
        self.e_type = e_type
        self.q = q
        self.r = r

    def __eq__(self, other):
        if self.w_id == other.w_id and self.w_type == other.w_type and self.text == other.text and self.w_img == other.w_img and self.e_type == other.e_type:
            return True
        else:
            return False
class State:
    def __init__(self, image, act, doc_tree, label = pack):
        self.image = image
        self.act = act
        self.doc_tree = doc_tree
        self.event_list = []

    def getMaxQEvent(self) -> Event:
        if not self.event_list:
            return None
        else:
            max = self.event_list[0]
            for i in range(1,len(self.event_list)):
                e = self.event_list[i]
                if e.q > max.q:
                    max = e
            return max

    def getRandomEvent(self) -> Event:
        if not self.event_list:
            return None
        else:
            next = 0
            n = 1
            for i in range(len(self.event_list)):
                if random.random() < 1.0 / n:
                    next = i
                n = n + 1
            return self.event_list[next]


    def __eq__(self, other):
        if self.act == other.act and sameHierarchy(self.doc_tree,other.doc_tree):
            return True
        else:
            return False

class Transition:
    def __init__(self, src, tgt, event, label = pack):
        self.src = src
        self.tgt = tgt
        self.event = event

    def __eq__(self, other):
        if self.src == other.src and self.tgt == other.tgt and self.event == other.event:
            return True
        else:
            return False

def removeSysUiNode(domTree:minidom.Document)->minidom.Document:
    nodeList = domTree.getElementsByTagName('node')
    for node in nodeList:
        if node.getAttribute('package')=='com.android.systemui':
            parent = node.parentNode
            parent.removeChild(node)
    return domTree

def sameHierarchy(domTree1:minidom.Document, domTree2:minidom.Document)->bool:
    elements1 = domTree1.getElementsByTagName('node')
    elements2 = domTree2.getElementsByTagName('node')
    len1 = elements1.length
    len2 = elements2.length
    if len1==len2:
        for i in range(len1):
            ele1 = elements1.item(i)
            ele2 = elements2.item(i)
            comparedAttr1 = getComparedAttributes(ele1)
            comparedAttr2 = getComparedAttributes(ele2)
            if not comparedAttr1 == comparedAttr2:
                return False
        return True
    else:
        return False

def getComparedAttributes(element:minidom.Element):
    attrList = []
    attrList.append(element.getAttribute('resource-id'))
    attrList.append(element.getAttribute('class'))
    attrList.append(element.getAttribute('package'))
    attrList.append(element.getAttribute('content-desc'))
    attrList.append(element.getAttribute('checkable'))
    attrList.append(element.getAttribute('clickable'))
    attrList.append(element.getAttribute('scrollable'))
    attrList.append(element.getAttribute('long-clickable'))
    return attrList

def matchEvent(elements, event:Event):
    for element in elements:
        info = element.info
        #print(info)
        id = info.get('resourceName')
        type = info.get('className')
        text = info.get('text')
        desc = info.get('contentDescription')
        img = element.screenshot()
        if id == event.w_id and type == event.w_type and text == event.text and desc == event.desc and img == event.w_img:
            return element
    return None

def isCrash():
    crash_cmd = "logcat -d AndroidRuntime:E CrashAnrDetector:D ActivityManager:E SQLiteDatabase:E WindowManager:E ActivityThread:E Parcel:E *:F *:S"
    out = d.shell(crash_cmd).output
    if out.__contains__("--------- beginning of crash"):
        crashList.append(out)
        return True
    return False
    #return not sess.alive

def crash():
    crash_cmd = "logcat -d AndroidRuntime:E CrashAnrDetector:D ActivityManager:E SQLiteDatabase:E WindowManager:E ActivityThread:E Parcel:E *:F *:S"
    out = d.shell(crash_cmd).output
    if out.__contains__("--------- beginning of crash"):
        return True
    return False

def getCurrentAct():
    return d.app_current()['activity']


def isDialog():
    isDialog = False
    enabledView = d(enabled='true')[0]
    visBounds = enabledView.info['visibleBounds']
    curWidth = visBounds['right'] - visBounds['left']
    curHeight = visBounds['bottom'] - visBounds['top']
    if (width / 8 <= curWidth <= width / 4 * 3) or (height / 8 <= curHeight <= height / 4 * 3):
        isDialog = True
    return isDialog


def isMenu():
    isMenu = False
    enabledView = d(enabled='true')[0]
    visBounds = enabledView.info['visibleBounds']
    curWidth = visBounds['right'] - visBounds['left']
    curHeight = visBounds['bottom'] - visBounds['top']
    #isOriSize = not ((curHeight == height) and (curWidth == width))
    isOriSize = (curHeight <= 0.95 * height) and (curWidth <= 0.95 * width)
    hasListView = d(className='android.widget.ListView').exists
    hasRecyclerView = d(className='android.support.v7.widget.RecyclerView').exists
    hasList = hasListView or hasRecyclerView
    if isOriSize and hasList:
        isMenu = True
    return isMenu


def gotoAnotherApp():
    curPackage = d.app_current()['package']
    return curPackage != pack


def restartApp():
    d.app_stop(pack)
    d.app_start(pack,wait=True)


def back():
    backBefore = d.screenshot(format='opencv')
    d.press('back')
    sim = d.image.match(backBefore)['similarity']
    if sim >= 0.99:
        d.press('back')
    time.sleep(waitTime)

def executeEvent(element, event):
    type = element.info['className']
    if type == 'android.widget.EditText':
        element.set_text(fText)
    else:
        d.implicitly_wait(rTime)
        if event == 'click' or event == 'item_click':
            element.click()
        elif event == 'long_click' or event == 'item_long_click':
            element.long_click()
    time.sleep(waitTime)

def isEditText(element):
    type = element.info['className']
    return type == 'android.widget.EditText'

def findRandomElement(elements):
    e_index = random.randint(0, len(elements)-1)
    return elements[e_index]

def otherEvent():
    scroll = d(scrollable='true', instance=0)
    if scroll.exists:
        r = random.random()
        if r > 0.7:
            d.swipe_ext("down")
            longClickList = d(longClickable='true')
            if longClickList.exists:
                p_lc = random.random()
                if p_lc > 0.7:
                    lc_index = random.randint(0, len(longClickList)-1)
                    executeEvent(longClickList[lc_index],'long_click')
                else:
                    back()
            else:
                back()
        else:
            longClickList = d(longClickable='true')
            if longClickList.exists:
                p_lc = random.random()
                if p_lc > 0.7:
                    lc_index = random.randint(0, len(longClickList) - 1)
                    executeEvent(longClickList[lc_index], 'long_click')
                else:
                    back()
            else:
                back()

def getCurrentState():
    img = d.image
    act = getCurrentAct()
    hie = d.dump_hierarchy()
    raw_tree = parseString(hie)
    doc_tree = removeSysUiNode(raw_tree)
    state = State(img, act, doc_tree)
    return state
def getStateEvents(event_list, elements):
    for w in elements:
        w_id = w.info.get('resourceName')
        text = w.info.get('text')
        w_type = w.info.get('className')
        desc = w.info.get('contentDescription')
        w_img = w.screenshot()
        e_type = 'click'
        e = Event(w_id, text, w_type, desc, w_img, e_type)
        event_list.append(e)

#get the event info of an element
def getEvent(element, e_type = 'click'):
    id = element.info.get('resourceName')
    text = element.info.get('text')
    type = element.info.get('className')
    desc = element.info.get('contentDescription')
    img = element.screenshot()
    e = Event(id, text, type, desc, img, e_type)
    return e

def appendorFindState(state, elements):
    if not state in stateList:
        getStateEvents(state.event_list, elements)
        stateList.append(state)
    else:
        s_index = stateList.index(state)
        state = stateList[s_index]
    return state

def appendTransition(transition):
    if not transition in tranList:
        tranList.append(transition)
def explore():
    d.shell("logcat -c")
    startTime = time.time()
    endTime = startTime
    s_state = None
    t_state = None
    event = None
    while endTime - startTime <= timeout:
        elements = d(clickable='true')
        s_state = getCurrentState()
        s_state = appendorFindState(s_state, elements)
        if elements.exists:
            if not bool(visitMap):
                fir_element = elements[0]
                fir_dic = fir_element.info
                firAct = getCurrentAct()
                fir_dic['hostAct'] = firAct
                fir_info = str(fir_dic)
                event = getEvent(fir_element)
                executeEvent(fir_element,'click')
                next_state = getCurrentState()
                next_elements = d(clickable='true')
                next_state = appendorFindState(next_state, next_elements)
                transition = Transition(s_state, next_state, event)
                appendTransition(transition)
                firVisit = {'openType': 0, 'visit': True, 'frequency': 0}
                if isDialog() and (not crash()):
                    firVisit['openType'] = 1
                    firVisit['visit'] = False
                elif isMenu() and (not crash()):
                    firVisit['openType'] = 2
                    firVisit['visit'] = False
                nextFrequency = firVisit['frequency'] + 1;
                firVisit['frequency'] = nextFrequency
                visitMap[fir_info] = firVisit
            else:
                if gotoAnotherApp():
                    back()
                    curPack = d.app_current()['package']
                    if curPack == pack:
                        continue
                    else:
                        restartApp()
                        continue
                cele_index = 0
                for cele in elements:
                    hostAct = getCurrentAct()
                    isEdit = isEditText(cele)
                    cele_dic = cele.info
                    cele_dic['hostAct'] = hostAct
                    cele_info = str(cele_dic)
                    if(not cele_info in visitMap.keys()):
                        event = getEvent(cele)
                        executeEvent(cele, 'click')
                        next_state = getCurrentState()
                        next_elements = d(clickable='true')
                        next_state = appendorFindState(next_state, next_elements)
                        transition = Transition(s_state, next_state, event)
                        appendTransition(transition)
                        subVisit = {'openType':0,'visit':True,'frequency':0}
                        if isDialog() and (not isEdit) and (not crash()):
                            subVisit['openType'] = 1
                            subVisit['visit'] = False
                        elif isMenu() and (not isEdit) and (not crash()):
                            subVisit['openType'] = 2
                            subVisit['visit'] = False
                        nextFrequency = subVisit['frequency'] + 1
                        subVisit['frequency'] = nextFrequency
                        visitMap[cele_info] = subVisit
                        break
                    else:
                        dmVisit = visitMap[cele_info]
                        if not dmVisit['visit']:
                            event = getEvent(cele)
                            executeEvent(cele, 'click')
                            next_state = getCurrentState()
                            next_elements = d(clickable='true')
                            next_state = appendorFindState(next_state, next_elements)
                            transition = Transition(s_state, next_state, event)
                            appendTransition(transition)
                            dmFlag = True
                            dmElements = d(clickable='true')
                            for dmEle in dmElements:
                                dmEle_dic = dmEle.info
                                dmHostAct = getCurrentAct()
                                dmEle_dic['hostAct'] = dmHostAct
                                dmEle_info = str(dmEle_dic)
                                if(not dmEle_info in visitMap.keys()):
                                    dmFlag = False
                                    break
                                else:
                                    dmFlag = dmFlag and visitMap[dmEle_info]['visit']
                            nextFrequency = dmVisit['frequency'] + 1
                            dmVisit['frequency'] = nextFrequency
                            dmVisit['visit'] = dmFlag
                            if dmVisit['frequency'] > frequencyCap:
                                dmVisit['visit'] = True
                            break
                    if cele_index == len(elements) - 1:
                        curAct = getCurrentAct()
                        if ((pack + curAct) == mainAct) and (not isDialog()) and (not isMenu()):
                            lc_elements = d(longClickable = 'true')
                            if lc_elements.exists:
                                p_lc = random.random()
                                if p_lc >= 0.5:
                                    lc_index = random.randint(0, len(lc_elements)-1)
                                    event = getEvent(lc_elements[lc_index], 'long_click')
                                    executeEvent(lc_elements[lc_index], 'long_click')
                                    next_state = getCurrentState()
                                    next_elements = d(clickable='true')
                                    next_state = appendorFindState(next_state, next_elements)
                                    transition = Transition(s_state, next_state, event)
                                    appendTransition(transition)
                                    break
                                else:
                                    optElement = findRandomElement(elements)
                                    opt_hostAct = curAct
                                    opt_dic = optElement.info
                                    opt_dic['hostAct'] = opt_hostAct
                                    opt_str = str(opt_dic)
                                    opt_info = visitMap[opt_str]
                                    event = getEvent(optElement)
                                    executeEvent(optElement, 'click')
                                    next_state = getCurrentState()
                                    next_elements = d(clickable='true')
                                    next_state = appendorFindState(next_state, next_elements)
                                    transition = Transition(s_state, next_state, event)
                                    appendTransition(transition)
                                    opt_info['frequency'] = opt_info['frequency'] + 1
                                    break
                            else:
                                optElement = findRandomElement(elements)
                                opt_hostAct = curAct
                                opt_dic = optElement.info
                                opt_dic['hostAct'] = opt_hostAct
                                opt_str = str(opt_dic)
                                opt_info = visitMap[opt_str]
                                event = getEvent(optElement)
                                executeEvent(optElement, 'click')
                                next_state = getCurrentState()
                                next_elements = d(clickable='true')
                                next_state = appendorFindState(next_state, next_elements)
                                transition = Transition(s_state, next_state, event)
                                appendTransition(transition)
                                opt_info['frequency'] = opt_info['frequency'] + 1
                                # visitMap[opt_str] = opt_info
                                break
                        else:
                            #otherEvent()
                            back()
                            break
                    cele_index = cele_index + 1
        else:
            #otherEvent()
            back()
        if isCrash():
            d.shell("logcat -c")
            restartApp()
        endTime = time.time()
    for transition in tranList:
        s_page = transition.src
        t_page = transition.tgt
        event = transition.event
        print("{0}->{1}, event: {2}".format(s_page.act, t_page.act, event.e_type))


if __name__ == "__main__":
    explore()