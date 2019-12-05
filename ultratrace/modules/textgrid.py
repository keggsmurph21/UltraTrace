from .base import Module
from .. import util
from ..util.logging import *
from ..widgets import CanvasTooltip

from tkinter import *
import decimal
import tempfile

LIBS_INSTALLED = False

try:
    from textgrid import TextGrid, IntervalTier, PointTier, Point # textgrid
    LIBS_INSTALLED = True
except ImportError as e:
    warn(e)

ALIGNMENT_TIER_NAMES = [ 'frames', 'all frames', 'dicom frames', 'ultrasound frames' ]

class TextGridModule(Module):
    '''
    Manages all the widgets related to TextGrid files, including the tier name
    and the text content of that tier at a given frame
    '''
    def __init__(self, app):
        '''
        Keep a reference to the master object for binding the widgets we create
        '''
        info( ' - initializing module: TextGrid' )
        self.app = app
        self.frame = Frame(self.app.BOTTOM)
        self.label_padx = 0
        self.canvas_frame = Frame(self.app.BOTTOM)#, padx=self.label_padx)
        self.frame.grid( row=1, column=0, sticky=NE)
        self.canvas_frame.grid(row=1, column=1 )
        self.TextGrid = None
        self.selectedTier = StringVar()
        self.tg_zoom_factor = 1.5
        self.canvas_width=800
        self.canvas_height=60
        self.collapse_height=15
        self.selectedIntvlFrames = []
        self.selectedItem = None
        self.start = 0
        self.end = 0
        self.current = 0
        self.frame_shift = DoubleVar()

        self.startup()

        platform = util.get_platform()
        #bindings
        if platform == 'Linux':
            self.app.bind("<Control-n>", self.getBounds)
            self.app.bind("<Control-a>", self.getBounds)
            self.app.bind("<Control-i>", self.getBounds)
            self.app.bind("<Control-o>", self.getBounds)
            self.app.bind("<Control-f>", self.openSearch)
            # Command is Alt in Linux, apparently
            self.app.bind("<Command-Up>", self.changeTiers)
            self.app.bind("<Command-Down>", self.changeTiers)
            self.app.bind("<Command-Left>", self.changeIntervals)
            self.app.bind("<Command-Right>", self.changeIntervals)
        elif platform == 'Darwin':
            self.app.bind("<Command-n>", self.getBounds)
            self.app.bind("<Command-a>", self.getBounds)
            self.app.bind("<Command-i>", self.getBounds)
            self.app.bind("<Command-o>", self.getBounds)
            self.app.bind("<Command-f>", self.openSearch)
            self.app.bind("<Option-Up>", self.changeTiers)
            self.app.bind("<Option-Down>", self.changeTiers)
            self.app.bind("<Option-Left>", self.changeIntervals)
            self.app.bind("<Option-Right>", self.changeIntervals)
        #defaults (Command/Alt everything)
        else:
            self.app.bind("<Command-n>", self.getBounds)
            self.app.bind("<Command-a>", self.getBounds)
            self.app.bind("<Command-i>", self.getBounds)
            self.app.bind("<Command-o>", self.getBounds)
            self.app.bind("<Command-f>", self.openSearch)
            self.app.bind("<Command-Up>", self.changeTiers)
            self.app.bind("<Command-Down>", self.changeTiers)
            self.app.bind("<Command-Left>", self.changeIntervals)
            self.app.bind("<Command-Right>", self.changeIntervals)

        # these aren't Praat-like
        self.app.bind("<Shift-Left>", self.getBounds)
        self.app.bind("<Shift-Right>", self.getBounds)



    def startup(self):
        '''

        '''
        if LIBS_INSTALLED:
            # default Label in case there are errors below
            self.TkWidgets = [{ 'label':Label(self.frame, text="Unable to load TextGrid file") }]
            # the Data module will pass this filename=None if it can't find an appropriate .TextGrid file
            filename = self.app.Data.getFileLevel( '.TextGrid' )
            # debug(filename)
            if filename:
                try:
                    # try to load up our TextGrid using the textgrid lib
                    self.TextGrid = self.fromFile( self.app.Data.unrelativize(filename) )
                except:
                    pass
            else:
                #debug(self.app.Audio.duration)
                minTime = 0.
                maxTime = self.app.Audio.duration
                self.TextGrid = TextGrid(maxTime=self.app.Audio.duration)
                self.TkWidgets = []
                frameTime = self.app.Data.getFileLevel("FrameTime")
                numberOfFrames = self.app.Data.getFileLevel("NumberOfFrames")
                framesTier = PointTier(name="frames", maxTime=maxTime)
                if frameTime is not None and numberOfFrames is not None:
                    for frameNum in range(1,numberOfFrames+1):
                        pointTime = (frameTime*frameNum)/1000
                        point = Point(pointTime,str(frameNum))
                        framesTier.addPoint(point)
                else:
                    for i, pointTime in enumerate([1.,2.,3.,4.]):
                        point = Point(pointTime,str(i))
                        framesTier.addPoint(point)
                self.TextGrid.tiers.append(framesTier)
                sentenceTier = IntervalTier("text")
                sentenceTier.add(minTime, maxTime, "text")
                self.TextGrid.tiers.append(sentenceTier)

            try:
                # reset default Label to actually be useful
                # self.TkWidgets = [{ 'label':Label(self.frame, text="TextGrid tiers:") }]
                self.TkWidgets = []
                # iterate the tiers
                try:
                    self.frameTierName = self.getFrameTierName()
                except:
                    self.genFramesTier()
                self.app.frames = len(self.TextGrid.getFirst(self.frameTierName))
                for tier in self.TextGrid.getNames():
                    if tier != self.frameTierName and tier != self.frameTierName + '.original':
                        # make some widgets for each tier
                        tierWidgets = self.makeTierWidgets( tier )
                        self.TkWidgets.append( tierWidgets )
                #make other widgets
                self.makeFrameWidget()
                self.makeTimeWidget()
                #put items on canvases
                self.fillCanvases()
                #calculate first and last frames
                self.firstFrame = int(self.TextGrid.getFirst(self.frameTierName)[0].mark) + 1
                self.startFrame = self.firstFrame
                self.lastFrame = int(self.TextGrid.getFirst(self.frameTierName)[-1].mark) + 1
                self.endFrame = self.lastFrame
            except Exception as e:
                error("exception: ", e)
                pass

            self.grid()

    def reset(self, event=None):
        '''
        Try to load a TextGrid file based on information stored in the metadata
        '''
        # for t in range(len(self.TkWidgets)):
        #   tierWidgets = self.TkWidgets[t]
        #   if 'canvas' in tierWidgets:
        #       tierWidgets['canvas-label'].config(width=self.app.LEFT.winfo_width())
        #       tierWidgets['canvas-label'].update()
        #   if 'frames' in tierWidgets:
        #       tierWidgets['frames-label'].config(width=self.app.LEFT.winfo_width())
        self.selectedIntvlFrames = []
        self.selectedItem = None
        #destroy
        # for wframe in [self.frame, self.canvas_frame]:
        #   for child in wframe.winfo_children():
        #       child.destroy()
        if LIBS_INSTALLED:
            # default Label in case there are errors below
            # self.TkWidgets = [{ 'label':Label(self.frame, text="Unable to load TextGrid file") }]
            # the Data module will pass this filename=None if it can't find an appropriate .TextGrid file
            filename = self.app.Data.getFileLevel( '.TextGrid' )
            # debug(filename)
            if filename:
                try:
                    # try to load up our TextGrid using the textgrid lib
                    self.TextGrid = self.fromFile(filename)
                    # reset default Label to actually be useful
                    # self.TkWidgets = [{ 'label':Label(self.frame, text="TextGrid tiers:") }]
                    # self.TkWidgets = []
                    # iterate the tiers
                    self.frameTierName = self.getFrameTierName()
                    self.app.frames = len(self.TextGrid.getFirst(self.frameTierName))
                    # for tier in self.TextGrid.getNames():
                    #   if tier != self.frameTierName and tier != self.frameTierName + '.original':
                    #       # make some widgets for each tier
                    #       tierWidgets = self.makeTierWidgets( tier )
                    #       self.TkWidgets.append( tierWidgets )
                    self.start = self.TextGrid.minTime
                    self.end = self.TextGrid.maxTime
                    self.current = self.TextGrid.getFirst(self.frameTierName)[self.app.frame-1].time
                    #make other widgets
                    # self.makeFrameWidget()
                    #reset offset
                    offset = self.app.Data.getFileLevel( 'offset' )
                    if offset != None:
                        self.frame_shift.set(offset)
                    else:
                        self.frame_shift.set(0)
                    # self.makeTimeWidget()
                    #put items on canvases
                    self.fillCanvases()
                    #calculate first and last frames
                    self.firstFrame = int(self.TextGrid.getFirst(self.frameTierName)[0].mark) + 1
                    self.startFrame = self.firstFrame
                    self.lastFrame = int(self.TextGrid.getFirst(self.frameTierName)[-1].mark) + 1
                    self.endFrame = self.lastFrame
                except:
                    pass
            # self.grid()

    def fromFile(self, filename):
        if LIBS_INSTALLED:
            try:
                return TextGrid.fromFile(self.app.Data.unrelativize(filename))
            except UnicodeDecodeError:
                pth = self.app.Data.unrelativize(filename)
                f = open(pth, 'rb')
                bytes = f.read()
                f.close()
                tmp = tempfile.NamedTemporaryFile()
                found = False
                for encoding in ['Windows-1251', 'Windows-1252', 'ISO-8859-1']:
                    try:
                        s = bytes.decode(encoding)
                        tmp.write(s.encode('utf-8'))
                        tmp.seek(0)
                        found = True
                        break
                    except Exception as e:
                        pass
                if not found:
                    raise
                else:
                    ret = TextGrid.fromFile(tmp.name)
                    tmp.close()
                    return ret
        else:
            error("can't load from file: textgrid lib not installed")
            return None

    def genFramesTier(self):
        self.frameTierName = 'frames'
        times = self.app.Dicom.getFrameTimes()
        tier = PointTier('frames')
        for f, t in enumerate(times):
            tier.addPoint(Point(t, str(f)))
        self.TextGrid.append(tier)
        self.TextGrid.write(self.app.Data.unrelativize(self.app.Data.getFileLevel( '.TextGrid' )))

    @staticmethod
    def isIntervalTier(tier):
        if LIBS_INSTALLED:
            return isinstance(tier, IntervalTier)
        else:
            error("can't check if IntervalTier: textgrid lib not installed")
            return False

    def shiftFrames(self):
        '''
        Replicate original TextGrid point tier (renamed [tiername].original)
        Shift points on TextGrid tier in accordance with self.frame_shift
            Shift value is relative to 0, i.e. inputting the same shift amount a second time will not change the shift
        Redisplay shifted points
        '''
        self.app.focus()
        shift = self.frame_shift.get()
        if type(shift) == float:
            self.app.Data.setFileLevel( 'offset', shift )
            # diff = shift - self.app.Data.data['offset']
            originalTier = self.TextGrid.getFirst(self.frameTierName+'.original')
            if originalTier: pass
            else:
                orig = copy.deepcopy(self.TextGrid.getFirst(self.frameTierName))
                orig.name += '.original'
                self.TextGrid.append(orig)
                originalTier = self.TextGrid.getFirst(self.frameTierName+'.original')

            oldTier = self.TextGrid.getFirst(self.frameTierName)
            allPoints = oldTier[:]
            for point in allPoints:
                oldTier.removePoint(point)

            for point in originalTier:
                new_time = point.time + decimal.Decimal(shift/1000) ## NOTE: currently in ms
                if self.TextGrid.minTime <= new_time <= self.TextGrid.maxTime:
                    self.TextGrid.getFirst(self.frameTierName).add(new_time, point.mark)

            # self.app.frames = len(self.TextGrid.getFirst(self.frameTierName))         #FIXME I feel like I shouldn't have to run the getFirst function every time, but I'm not sure when I have to go back to the original textgrid, and when I can just use a variable...
            self.firstFrame = int(self.TextGrid.getFirst(self.frameTierName)[0].mark) + 1
            self.lastFrame = int(self.TextGrid.getFirst(self.frameTierName)[-1].mark) + 1
            self.app.Data.data['offset'] = shift
            # self.frame_shift.set(shift)
            self.app.Data.write()
            # newTier.write(self.TextGrid.getFirst(self.frameTierName))
            self.fillCanvases()
            self.TextGrid.write(self.app.Data.unrelativize(self.app.Data.getFileLevel( '.TextGrid' )))


        #except ValueError:
        else:
            error('Not a float!')

    def makeTimeWidget(self):
        self.time_canvas = Canvas(self.canvas_frame, width=self.canvas_width, height=self.canvas_height/3, highlightthickness=0)
        s = self.time_canvas.create_text(3,0, anchor=NW, text=self.start)
        e = self.time_canvas.create_text(self.canvas_width,0, anchor=NE, text=self.end)
        c = self.time_canvas.create_text(self.canvas_width/2,0, anchor=N, text=self.current)
        self.TkWidgets.append({'times':self.time_canvas})

    def makeFrameWidget(self):
        '''
        makes frame widget
        '''
        #make regular frame stuff -- label and tier
        self.frames_canvas = Canvas(self.canvas_frame, width=self.canvas_width, height=self.canvas_height, background='gray', highlightthickness=0)
        frames_label = Canvas(self.frame, width=self.label_width, height=self.canvas_height, highlightthickness=0, background='gray')
        frames_label.create_text(self.label_width,0, anchor=NE, justify=CENTER,
                                 text='frames: ', width=self.label_width, activefill='blue')

        # make subframe to go on top of label canvas
        sbframe = Frame(frames_label)
        #put new widgets onto subframe
        offset = self.app.Data.getFileLevel( 'offset' )
        if offset != None:
            self.frame_shift.set(offset)
        go_btn = Button(sbframe, text='Offset', command=self.shiftFrames, takefocus=0)
        # minmax = len(self.app.Audio.sfile)*1000
        txtbox = Spinbox(sbframe, textvariable=self.frame_shift, width=7, from_=-10000000, to=10000000)
        txtbox.bind('<Escape>', lambda ev: sbframe.focus())
        txtbox.bind('<Return>', lambda ev: self.shiftFrames())
        go_btn.grid(row=0, column=0, sticky=E)
        txtbox.grid(row=0, column=1, sticky=E)
        # put subframe on canvas
        window = frames_label.create_window(self.label_width*.3,self.canvas_height/3, anchor=NW, window=sbframe)

        self.TkWidgets.append({'name':self.frameTierName,'frames':self.frames_canvas,
                               'frames-label':frames_label})

        self.frames_canvas.bind("<Button-1>", self.getClickedFrame)

    def getFrameTierName(self):
        '''
        Handle some inconsistency in how we're naming our alignment tier
        '''
        for name in ALIGNMENT_TIER_NAMES:
            if name in self.TextGrid.getNames():
                return name
        raise NameError( 'Unable to find alignment tier' )

    def getClickedFrame(self, event):
        '''
        Jumps to clicked frame
        '''
        item = self.my_find_closest(event.widget, event.x)
        self.setSelectedIntvlFrames((event.widget, item))
        frame = event.widget.gettags(item)[0][5:]
        self.app.frame = int(frame)
        if not frame in self.selectedIntvlFrames:
            self.selectedIntvlFrames = []
            self.wipeFill()
        self.app.framesUpdate()

    def makeTierWidgets(self, tier):
        '''
        Each tier should have two canvas widgets: `canvas-label` (the tier name),
        and `canvas` (the intervals on the tier with their marks)
        '''
        self.tier_pairs = {} #ends up being format {label: canvas}

        # self.app.Trace.frame.update()
        self.label_width=300#self.app.Trace.frame.winfo_width()+self.label_padx
        self.end = self.TextGrid.maxTime#float(self.TextGrid.maxTime)
        # self.first_frame = 1
        # self.last_frame = self.TextGrid.getFirst(self.frameTierName)[-1].mark
        tier_obj = self.TextGrid.getFirst(tier)
        widgets = { 'name':tier,
                         #'label':Label(self.frame, text=('- '+tier+':'), wraplength=200, justify=LEFT),
                         'canvas-label':Canvas(self.frame, width=self.label_width, height=self.canvas_height, highlightthickness=0),
                         # 'text' :Label(self.frame, text='', wraplength=550, justify=LEFT),
                         'canvas':Canvas(self.canvas_frame, width=self.canvas_width, height=self.canvas_height, background='gray', highlightthickness=0)}

        canvas = widgets['canvas']
        label = widgets['canvas-label']

        #builds tier label functionality
        label_text = label.create_text(self.label_width, self.canvas_height/2, anchor=E, justify=CENTER,
                                        text='temp', width=self.label_width/2, activefill='blue')

        canvas.bind("<Button-1>", self.genFrameList)
        label.bind("<Button-1>", self.genFrameList)
        label.bind("<Double-Button-1>", self.collapse)
        label.bind("<Button-4>", self.collapse)
        label.bind("<Button-5>", self.collapse)
        label.bind("<MouseWheel>", self.collapse)
        canvas.bind("<Button-4>", self.collapse)
        canvas.bind("<Button-5>", self.collapse)
        canvas.bind("<MouseWheel>", self.collapse)

        return widgets

    def changeIntervals(self,event):
        '''

        '''
        if self.selectedItem:
            duration = self.end - self.start

            # There might be a more efficient way to get the tier name:
            widg = self.selectedItem[0]
            itm = self.selectedItem[1]
            for el in self.TkWidgets:
                if widg in el.values():
                    tier_name = el['name']
                    break

            #finding Interval mintime and maxtime
            oldMinTime = None
            oldMaxTime = None
            q=0
            tags = widg.gettags(itm)
            while oldMinTime == None or oldMaxTime == None:
                if tags[q][:7] == 'minTime':
                    oldMinTime = float(tags[q][7:])
                elif tags[q][:7] == 'maxTime':
                    oldMaxTime = float(tags[q][7:])
                q+=1

            tier = self.TextGrid.getFirst(tier_name)
            intvl_i = tier.indexContaining(oldMaxTime-((oldMaxTime-oldMinTime)/2))

            if event.keysym == 'Left':
                new_intvl_i = intvl_i-1
            elif event.keysym == 'Right':
                new_intvl_i = intvl_i+1
            if 0 <= new_intvl_i < len(tier):
                #find characteristics of new adjacent interval
                newMinTime = tier[new_intvl_i].minTime
                newMaxTime = tier[new_intvl_i].maxTime
                itvlDuration = newMaxTime - newMinTime
                newCenter = newMinTime + itvlDuration/2

                #figure out new window parameters based on new interval
                start = newCenter - duration/2
                end = newCenter + duration/2
                if start < 0:
                    self.start = 0
                    self.end = duration
                elif end > self.TextGrid.maxTime:
                    self.start = self.TextGrid.maxTime - duration
                    self.end = self.TextGrid.maxTime
                else:
                    self.start = newCenter - duration/2
                    self.end = newCenter + duration/2
                relDuration = self.end - self.start

                # select new item
                rel_time = newCenter - self.start
                x_loc = float(rel_time/relDuration*self.canvas_width)
                item = self.my_find_closest(widg, x_loc)
                self.selectedItem = (widg, item)
                self.setSelectedIntvlFrames(self.selectedItem)

                self.fillCanvases()
                self.genFrameList(widg=widg, x_loc=x_loc)

    def changeTiers(self, event):
        '''

        '''
        index = None
        if self.selectedItem:
            for i, el in enumerate(self.TkWidgets):
                if self.selectedItem[0] in el.values():
                    index = i

            if index != None:
                if event.keysym == 'Up' and 'canvas' in self.TkWidgets[index-1]:
                    new_widg = self.TkWidgets[index-1]['canvas']
                elif event.keysym == 'Down' and 'canvas' in self.TkWidgets[index+1]:
                    new_widg = self.TkWidgets[index+1]['canvas']
                else:
                    return

                new_item = new_widg.find_withtag("frame"+str(self.app.frame))[0]
                self.selectedItem = (new_widg, new_item)

                self.fillCanvases()
                self.update()
                self.app.Spectrogram.update()

    def getMinMaxTime(self):
        '''
        Returns minTime and maxTime tags from selected interval
        If no minTime or maxTime, returns start or end time of viewed section of TextGrid
        '''
        start=None
        end=None

        for tag in self.selectedItem[0].gettags(self.selectedItem[1]):
            if tag[:7] == 'minTime':
                start = decimal.Decimal(tag[7:])
            elif tag[:7] == 'maxTime':
                end = decimal.Decimal(tag[7:])

        if start==None:
            start=self.start
        if end==None:
            end=self.end

        return (start,end)

    def getBounds(self, event):
        '''

        '''
        # debug(event.char, event.keysym, event.keycode)
        # debug(self.app.frame)
        f = decimal.Decimal(self.tg_zoom_factor)
        a = self.end - self.start
        z_out = (a-(a/f))/2
        z_in = ((f*a)-a)/2
        old_start = self.start
        old_end = self.end

        if event.keysym == 'n':
            if self.selectedItem:
                self.start, self.end = self.getMinMaxTime()
            # for tag in self.selectedItem[0].gettags(self.selectedItem[1]):
            #   if tag[:7] == 'minTime':
            #       self.start = decimal.Decimal(tag[7:])
            #   elif tag[:7] == 'maxTime':
            #       self.end = decimal.Decimal(tag[7:])
        if event.keysym == 'a':
            self.start = 0
            self.end = self.TextGrid.maxTime
        if event.keysym == 'o':
            self.start = self.start - z_in
            self.end = self.end + z_in
        if event.keysym == 'i':
            self.start = self.start + z_out
            self.end = self.end - z_out
        if event.keysym == 'Left':
            start = self.start - a/(10*f)
            end = self.end - a/(10*f)
            if (start < 0):
                self.start = 0
                self.end = a
            else:
                self.start = start
                self.end = end
        if event.keysym == 'Right':
            start = self.start + a/(10*f)
            end = self.end + a/(10*f)
            if end > self.TextGrid.maxTime:
                self.start = self.TextGrid.maxTime - a
                self.end = self.TextGrid.maxTime
            else:
                self.start = start
                self.end = end

        self.fillCanvases()

    def getTracedFrames(self,frames):
        '''

        '''
        frames = [frame[5:] for frame in frames] #to get rid of word "frame in tag"
        tracedFrames = []
        for trace in self.app.Data.data['traces']:
            tracedFrames = tracedFrames+self.app.Data.tracesExist(trace)

        return set(frames).intersection(tracedFrames)

    def fillCanvases(self):
        '''

        '''
        if self.start < 0:
            self.start = 0
        if self.end > self.TextGrid.maxTime:
            self.end = self.TextGrid.maxTime
        self.updateTimeLabels()

        if self.selectedItem:
            old_selected_tags = self.selectedItem[0].gettags(self.selectedItem[1])
        duration = self.end - self.start
        self.frameTier = self.TextGrid.getFirst(self.frameTierName)
        for el in self.TkWidgets:
            if 'name' in el:
                tier = self.TextGrid.getFirst(el['name'])
                # debug(tier)
            if 'canvas' in el:
                canvas = el['canvas']
                #remove previous intervals
                canvas.delete(ALL)
                #get starting interval
                i = tier.indexContaining(self.start)
                time = tier[i].maxTime
                frame_i = 0
                while i < len(tier) and tier[i].minTime <= self.end:
                    if self.start >= tier[i].minTime:
                        strtime = self.start
                    else:
                        strtime = tier[i].minTime
                    if self.end <= tier[i].maxTime:
                        time = self.end
                    length = time - strtime
                    pixel_length = length/duration*self.canvas_width

                    mod = length/2
                    rel_time = time-self.start
                    loc=(rel_time-mod)/duration*self.canvas_width

                    text = canvas.create_text(loc, self.canvas_height/2, justify=CENTER,
                                        text=tier[i].mark, width=pixel_length, activefill='blue')
                    minTimetag = "minTime"+str(tier[i].minTime)
                    maxTimetag = "maxTime"+str(tier[i].maxTime)
                    canvas.addtag_withtag(minTimetag, text)
                    canvas.addtag_withtag(maxTimetag, text)
                    #add containted frames to tags
                    while frame_i < len(self.frameTier) and self.frameTier[frame_i].time <= tier[i].maxTime:
                        if self.frameTier[frame_i].time >= tier[i].minTime:
                            canvas.addtag_withtag("frame"+self.frameTier[frame_i].mark, text)
                            if tier[i].mark != '':
                                el['canvas-label'].addtag_all("frame"+self.frameTier[frame_i].mark)
                        frame_i+=1
                    #pass on selected-ness
                    if self.selectedItem:
                        if self.selectedItem[0] != self.app.Spectrogram.canvas:
                            # old_selected_tags = self.selectedItem[0].gettags(self.selectedItem[1])
                            if minTimetag in old_selected_tags and maxTimetag in old_selected_tags:
                                self.selectedItem = (canvas, text)
                    #create line
                    loc=rel_time/duration*self.canvas_width
                    i+=1
                    if i < len(tier) and loc < self.canvas_width:
                        canvas.create_line(loc,0,loc,self.canvas_height, tags='line')
                        time = tier[i].maxTime #here so that loop doesn't run an extra time

                #fills labels with info about tiers w/traces
                self.updateTierLabels()

            elif 'frames' in el:
                frames = el['frames']
                i = 0
                frames.delete(ALL)
                first_frame_found = False
                while i < len(tier) and tier[i].time <= self.end :
                    # debug(tier[i].time, i,'frame time and frame number (line 1076)')
                    if tier[i].time >= self.start:
                        # x_coord = (tier[i].time-self.start)/duration*self.canvas_width
                        x_coord = ((tier[i].time-self.start)*self.canvas_width)/duration
                        #determine fill
                        if tier[i].mark in self.app.Data.getCurrentTraceTracedFrames():
                            fill = 'black'
                        else:
                            fill = 'gray50'
                        frame = frames.create_line(x_coord, 0, x_coord, self.canvas_height, tags="frame"+tier[i].mark, fill=fill)
                        if first_frame_found == False:
                            self.firstFrame = int(tier[i].mark) + 1
                            first_frame_found = True
                            self.frame_len = tier[i+1].time - tier[i].time
                        CanvasTooltip(frames, frame,text=tier[i].mark)
                    i+=1
                self.lastFrame = int(tier[i-1].mark)

        self.paintCanvases()
        try:
            self.app.Spectrogram.reset()
            # during startup this gets called before app.Spectrogram is initialized
        except AttributeError:
            pass

    def updateTimeLabels(self):
        '''

        '''
        self.current = self.TextGrid.getFirst(self.frameTierName)[self.app.frame-1].time
        self.TkWidgets[-1]['times'].itemconfig(1,text='{:.6f}'.format(self.start))
        self.TkWidgets[-1]['times'].itemconfig(2,text='{:.6f}'.format(self.end))
        self.TkWidgets[-1]['times'].itemconfig(3,text='{:.6f}'.format(self.current))

    def updateTierLabels(self):
        '''

        '''
        for el in self.TkWidgets:
            if 'canvas' in el:
                current_label = el['canvas-label'].find_all()[0]
                nonempty_frames = el['canvas-label'].gettags(current_label)
                el['canvas-label'].itemconfig(current_label,
                  text='{}:\n({}/{})'.format(el['name'],len(self.getTracedFrames(nonempty_frames)), len(nonempty_frames)))


    def my_find_closest(self, widg, x_loc):
        '''
        replaces TkInter's find_closest function, which is buggy, determines
        whether found item is text, line, or label, and returns corresponding item
        '''
        #could be more efficient FIXME
        maybe_item = None
        dist = 999999999999
        for el in widg.find_all():
            obj_x = widg.coords(el)[0]
            if abs(obj_x-x_loc) < dist:
                dist = abs(obj_x-x_loc)
                maybe_item = el

        if widg in self.tier_pairs.keys(): #on tier-label canvas
            #fill selected tier frames
            # self.setSelectedIntvlFrames(widg,item)
            item = maybe_item

        elif widg in self.tier_pairs.values(): #on canvas with intervals/frames
            if isinstance(maybe_item, int):
                # #if item found is a boundary
                # if len(widg.gettags(maybe_item)) == 0 or widg.gettags(maybe_item) == ('current',):
                if 'line' in widg.gettags(maybe_item):
                    #determine on which side of the line the event occurred
                    if widg.coords(maybe_item)[0] > x_loc:
                        item = maybe_item-1
                    else: #i.e. event was on line or to the right of it
                        item = maybe_item+1
                else:
                    item = maybe_item

                # self.setSelectedIntvlFrames(widg,item)
        else:
            item = maybe_item

        return item
    def setSelectedIntvlFrames(self,tupl):
        ''' '''
        widg,item=tupl
        self.selectedIntvlFrames = []
        for x in widg.gettags(item):
            if x[:5] == 'frame':
                self.selectedIntvlFrames.append(x[5:])

    def wipeFill(self):
        '''
        Turns selected frame and interval back to black
        '''
        for frame in range(1,self.app.frames+1):
            if str(frame) in self.app.Data.getCurrentTraceTracedFrames():
                fill = 'black'
            else:
                fill = 'gray50'
            self.frames_canvas.itemconfig('frame'+str(frame), fill=fill)
        if self.selectedItem:
            wdg,itm = self.selectedItem
            if wdg.type(itm) != 'text' and wdg.type(itm) != None:
                wdg,itm = self.app.Spectrogram.oldSelected
            wdg.itemconfig(itm, fill='black')
            if len(wdg.find_withtag(itm+1)) > 0:
                wdg.itemconfig(itm+1, fill='black')
            if len(wdg.find_withtag(itm-1)) > 0:
                wdg.itemconfig(itm-1, fill='black')
            #clicked tier label
            if wdg in self.tier_pairs.keys():
                wdg.itemconfig(1, fill='black')
                self.tier_pairs[wdg].itemconfig(ALL, fill='black')
                self.frames_canvas.itemconfig(ALL, fill='black')

    def genFrameList(self, event=None, widg=None, x_loc=None, SI=False):
        '''
        Upon click, reads frames within interval from the tags to the text item of that interval,
        and highlights text of clicked interval
        '''
        self.wipeFill()
        if event:
            widg=event.widget
            x_loc=event.x

        if SI==False:
            item = self.my_find_closest(widg, x_loc)
            self.selectedItem = (widg, item)
            self.setSelectedIntvlFrames(self.selectedItem)

        #automatically updates frame
        if not str(self.app.frame) in self.selectedIntvlFrames:
            if self.selectedIntvlFrames:
                new_frame = int(self.selectedIntvlFrames[0])
            else:
                frame = self.my_find_closest(self.frames_canvas,x_loc)
                framenum = self.frames_canvas.gettags(frame)[0][5:]
                new_frame = int(framenum)
            if self.firstFrame > new_frame:
                new_frame = self.firstFrame
            elif new_frame > self.lastFrame:
                new_frame = self.lastFrame
            self.app.frame = new_frame
            self.app.framesUpdate()
        else:
            self.paintCanvases()
            self.app.Spectrogram.update()

    def collapse(self, event):
        '''
        collapse or uncollapse selected tier
        '''
        if self.selectedItem != None:
            widg = self.selectedItem[0]
        else:
            widg = event.widget

        if event.num == 1:
            h = self.collapse_height
            if int(widg['height']) == h:
                h = self.canvas_height
        elif event.num == 4 or event.delta > 0:
            h = self.canvas_height
        else:
            h = self.collapse_height

        if int(widg['height']) == h:
            return
        elif h == self.canvas_height:
            mv = (self.canvas_height - self.collapse_height - 14) / 2
        else:
            mv = (self.collapse_height + 14 - self.canvas_height) / 2
        # manually shifting the text by 7 pixels is a rather ugly hack,
        # but it works - DS

        if widg in self.tier_pairs:
                l, c = widg, self.tier_pairs[widg]
        else:
                c = widg
                l = None
                for k in self.tier_pairs:
                        if self.tier_pairs[k] == widg:
                                l = k
                                break
        l.configure(height=h)
        c.configure(height=h)
        l.move('all', 0, mv)
        self.app.event_generate('<Configure>')

    def paintCanvases(self):
        '''

        '''
        if self.selectedItem:
            wdg,itm = self.selectedItem
            #paint selected
            if wdg.type(itm) == 'text':
                wdg.itemconfig(itm, fill='blue')
                #paint boundaries of selected
                if itm+1 in wdg.find_all():
                    wdg.itemconfig(itm+1, fill='blue')
                if itm-1 in wdg.find_all():
                    wdg.itemconfig(itm-1, fill='blue')
            if wdg in self.tier_pairs.keys(): #if on tier-label canvas
                canvas = self.tier_pairs[wdg]
                for el in canvas.find_all():
                    # #make all text intervals blue
                    # if canvas.type(canvas.find_withtag(el)) == 'text':
                    canvas.itemconfig(el, fill='blue')

            #paint frames
            frames = wdg.gettags(itm)
            for frame in frames:
                if frame[:5] == 'frame':
                    frame_obj = self.frames_canvas.find_withtag(frame)
                    #detect whether frame contains any traces
                    framenum = frame[5:]
                    if framenum in self.app.Data.getCurrentTraceTracedFrames():
                        fill = 'blue'
                    else:
                        fill = 'dodger blue'
                    self.frames_canvas.itemconfig(frame_obj, fill=fill)

        #current frame highlighted in red
        if self.app.frame:
            self.highlighted_frame = self.frames_canvas.find_withtag('frame'+str(self.app.frame))
            self.frames_canvas.itemconfig(self.highlighted_frame, fill='red')

    def update(self):
        '''

        '''
        # debug(self.frames_canvas)
        #create list of displayed frames' tags
        itrobj = []
        for itm in self.frames_canvas.find_all():
            itrobj += list(self.frames_canvas.gettags(itm))
        #if selected frame is out of view
        if "frame"+str(self.app.frame) not in itrobj:
            duration = self.end - self.start
            #recenter view on selected frame
            new_time = self.TextGrid.getFirst(self.frameTierName)[self.app.frame-1].time
            self.start = new_time - (duration/2)
            self.end = new_time + (duration/2)
            #redraw
            self.fillCanvases()
        self.wipeFill()
        #if selected frame outside selected interval, select interval on same tier containing frame
        if self.selectedItem:
            if self.selectedItem[0] in self.tier_pairs.keys() or self.selectedItem[0] in self.tier_pairs.values():
                if "frame"+str(self.app.frame) not in self.selectedItem[0].gettags(self.selectedItem[1]): #FIXME should also detect if on label canvas
                    widg = self.selectedItem[0]
                    if widg in self.tier_pairs:
                        widg = self.tier_pairs[widg]
                    new_interval = widg.find_withtag("frame"+str(self.app.frame))[0]
                    self.selectedItem = (self.selectedItem[0], new_interval)

        # repaint all frames
        self.paintCanvases()
        self.updateTimeLabels()

    def grid(self, event=None):
        '''
        Wrapper for gridding all of our Tk widgets.  This funciton assumes that the tiers (as
        specified in the actual TextGrid files) are in some sort of reasonable order, with the
        default label being drawn on top.
        '''
        for t in range(len(self.TkWidgets)):
            tierWidgets = self.TkWidgets[t]
            if 'label' in tierWidgets:
                tierWidgets['label'].grid(row=t, column=0, sticky=W)
            if 'frames' in tierWidgets:
                tierWidgets['frames'].grid(row=t, column=2, sticky=W, pady=self.app.pady)
                tierWidgets['frames-label'].grid(row=t, column=0, sticky=W, pady=self.app.pady)
            if 'canvas' in tierWidgets:
                tierWidgets['canvas'].grid(row=t, column=2, sticky=W, pady=self.app.pady/2)
                tierWidgets['canvas-label'].grid(row=t, column=0, sticky=W, pady=self.app.pady/2)
                self.tier_pairs[tierWidgets['canvas-label']] = tierWidgets['canvas']
            if 'times' in tierWidgets:
                tierWidgets['times'].grid(row=t, column=2, sticky=S)

    def grid_remove(self):
        raise NotImplementedError('cannot grid_remove the TextGridModule')

    def openSearch(self, event=None):
        self.app.Search.openSearch()