#Karinthy Bot (aka Karesz)  By Barni
import sys, os, discord, requests, json
from discord.ext import tasks
from discord.utils import get
from datetime import datetime, timedelta,date

## Parameters for "Karinthy 9.EK" server
if str(sys.argv).find('devmode') < 0:
    _CLASSNAME_ = "9.EK"
    _CLASSTABLE_ = "9ek_timetable.json"
    _ALIASESFILE_ = "aliases.json"
    _ENTRIESFILE_ = "seenEntries.txt"
    _SERVERNAME_ = "Karinthy 9/E"
    _CHANNELNAME_ = "orarend"
    _DEVCHANNEL_ = "bot-dev"
    _ROLENAMES_ = {
        'Media':"Média",
        'Info':"Infó",
        'Halado':"Haladó Angol",
        'Kezdo':"Kezdő Angol",
        'All': "User",
        'Unknown':'Unknown'
    }
## Developer Server
## Parameters for "Nightjar" server
else:
    _CLASSNAME_ = "9.EK"
    _CLASSTABLE_ = "9ek_timetable.json"
    _ALIASESFILE_ = "aliases.json"
    _ENTRIESFILE_ = "seenEntries.json"
    _SERVERNAME_ = "Nightjar©®™"
    _CHANNELNAME_ = "bot-test"
    _DEVCHANNEL_ = "bot-test"
    _ROLENAMES_ = {
        'Media':"Media",
        'Info':"Info",
        'Halado':"HaladoAngol",
        'Kezdo':"KezdoAngol",
        'All': "Member",
        'Unknown':'Unknown'
        }

## Used for generating messages from entries
dayLocaleDict = {
  "Monday": "Hétfőn ",
  "Tuesday": "Kedden ",
  "Wednesday": "Szerdán ",
  "Thursday": "Csütörtökön ",
  "Friday": "Pénteken ",
  "Saturday": "Szombaton ",
  "Sunday": "Vasárnap ",
}

## dummy function because 'devErrorMsg' is defined below in the bot section
async def botDevErrorMsg(title, msg):
    await devErrorMsg(title, msg)


#######################
#####  TIMETABLE  #####
#######################

## Reads the '<class>_timetable.json' and determines
## which groups to ping for a specific lesson

class TimeTable:
    ## Read & parse json
    def __init__(self):
        file = open(_CLASSTABLE_,mode='r',encoding='utf-8')
        jsonData = json.loads(file.read())
        self.jsonTable = jsonData['Table']
        self.jsonTeachers = jsonData['Teachers']
        file.close()
        print("Loaded Timetable data")
    
    def teacherToAcronym(self, teacher):
        for short, name in self.jsonTeachers.items():
            if name == teacher:
                return short
                break
        return None

    def acronymToTeacher(self, acronym):
        for short, name in self.jsonTeachers.items():
            if short == acronym:
                return name
                break
        return None

    def isMatchingSubjectName(self, name,alias):
        name = name.lower().strip()
        alias = alias.lower().strip()

        ## Load aliases.json to try to match the lesson name
        file = open(_ALIASESFILE_, mode='r', encoding='utf-8')
        aliases = json.loads(file.read())["subjects"]
        file.close()
        
        for l in aliases:
            if l[0] == name:
                for i in l:
                    if (i == alias):
                        return True
        return False

    async def getGroupForLesson(self, day, lessonNum, subject, teacher):
        lessonNum = str(lessonNum)

        ## Return without other logic, when 'All'
        if "All" in self.jsonTable[day][lessonNum]:
            return "All"

        ## Info/Media
        ## I/M groups are differentiated by subject
        if "Info" in self.jsonTable[day][lessonNum]:
            if self.isMatchingSubjectName(self.jsonTable[day][lessonNum]['Info']['subject'], subject):
                return "Info"
            if self.isMatchingSubjectName(self.jsonTable[day][lessonNum]['Media']['subject'], subject):
                return "Media"


        ## Halado/Kezdo
        ## English groups are differentiated by teacher
        elif "Halado" in self.jsonTable[day][lessonNum]:
            ## Convert Teacher name to acronym
            t = teacherToAcronym(teacher)
            if t == None:
                print("Teacher name not in Table:", teacher)
            else:
                teacher = t

            if self.jsonTable[day][lessonNum]['Halado']['teacher'] == teacher:
                return "Halado"
            elif self.jsonTable[day][lessonNum]['Kezdo']['teacher'] == teacher:
                return "Kezdo"

        # TODO make this less of an absolute clusterfuck
        print(f"Can't parse lesson from this information: '{day}' '{lessonNum}' '{subject}' '{teacher}'")
        j = self.jsonTable[day][lessonNum]
        msg = "Can't parse lesson from given data:\n'{d}'\n'{n}'\n'{s}'\n'{t}'".format(d=day,n=lessonNum,s=subject,t=teacher)

        await botDevErrorMsg("Timetable lesson parse error!",msg)
        await botDevErrorMsg("Timetable lesson parse info:", json.dumps(j, indent=4))
        return "Unknown"

       
####################
#####  WEBAPI  #####
####################

## Requests from Karinthy's site and processes
## the substitution entries and can generate HUN message

class WebApi:
    seenEntries = []
    
    def __init__(self):
        self.UpdateRequest()

    def loadEntries(self):
        try:
            file = open(_ENTRIESFILE_, mode='r', encoding='utf-8')
            for l in file.readlines():
                self.seenEntries.append(l.strip('\n'))
            file.close()
            print("Loaded seen entries")
        except Exception as e:
            print(e)
            print("Couldn't find '", _ENTRIESFILE_, "'. History will not be loaded :(")

    def saveEntries(self):
        try:
            file = open(_ENTRIESFILE_, mode='w', encoding='utf-8')
            for i in self.seenEntries:
                file.write(i)
                file.write('\n')
            file.close()
            print("Saved seen entries")
        except Exception as e:
            print(e)
            print("Couldn't write '" + _ENTRIESFILE_ + "'. History will not be saved :(")

    def localDayNameFromDate(self, datestr):
        dt_obj = datetime.strptime(datestr, '%Y-%m-%d')
        return (dayLocaleDict[dt_obj.strftime('%A')])
    
    def UpdateRequest(self):
        self.today = date.today()
        self.request = json.loads(requests.get('https://admin.karinthy.hu/api/substitutions').text)['substitutions']
        print('WebApi update fetch')

    def getNumArticle(self, n):
        n = int(n)
        if n == 1 or n == 5:
            return 'az'
        return 'a'

    ## Used for unknown entry type and for storing entries in the 'seenEntries'
    def defEntryFormat(self, entry):
        return "[{d}] [{l}. óra] [{s}] [\"{c}\"] [Helyettesítő: {t}]".format(d=entry['day'],l=entry['lesson'],\
                                                    s=entry['subject'],t=entry['substitutingTeacher'],c=entry['comment'])

    def getMsgFromEntry(self, entry):
        msg = ""

        ## Start with the entry day name
        if entry['day'] == str(self.today):        
            msg += 'Ma '
        elif entry['day'] == str(self.today + timedelta(days=1)):
            msg += 'Holnap '
        else:
            msg += self.localDayNameFromDate(entry['day'])

        ## Article before lesson number
        msg += self.getNumArticle(entry['lesson']) + ' '

        ## sentence based on what type of entry it is
        match entry['comment']:
            case 'később jön': # később jön
                msg += "{l}. órára ({s}) ne gyere be.".format(l=entry['lesson'],s=entry['subject'])
            case 'hazamegy': # hazamegy
                msg += "{l}. óráról ({s}) haza lehet menni.".format(l=entry['lesson'],s=entry['subject'])
            case 'önálló munka': # önálló munka
                msg += "{l}. órán ({s}) önálló munka lesz.".format(l=entry['lesson'],s=entry['subject'])
            case 'ebédel': # ebédel
                msg += "{l}. órára ({s}) helyett ebéd.".format(l=entry['lesson'],s=entry['subject'])
            case '': # no comment -> default substitution
                if entry['substitutingTeacher'] != '':
                    msg += "{l}. órát ({s}) {t} helyettesíti.".format(l=entry['lesson'],s=entry['subject'],t=entry['substitutingTeacher'])
                else:
                     msg = self.defEntryFormat(entry)       
                    
            case _: # Unknown comment type, print as normal substitution if there's a substituting teacher
                if entry['substitutingTeacher'] != '':
                    msg += "{l}. órát ({s}) {t} helyettesíti.".format(l=entry['lesson'],s=entry['subject'],t=entry['substitutingTeacher'])
                else:
                     msg = self.defEntryFormat(entry)
        return msg

    def getAllEntriesForClass(self, classname):
        l = []
        for i in self.request:
             if i['class'] == classname:
                 l.append(i)
        return l


    def getNewEntriesForClass(self, classname):
        l = []
        for i in self.request:
             if i['class'] == classname and (self.defEntryFormat(i) not in self.seenEntries):
                 self.seenEntries.append(self.defEntryFormat(i))
                 l.append(i)
        return l


###################
####### BOT #######
###################

TOKEN = ""
with open("secret.txt", "r") as f:
    TOKEN = f.read() 

GUILD = _SERVERNAME_
client = discord.Client(intents = discord.Intents.default())

guild = None
channel = None
devchannel = None
roleTable = {"Unknown":""}
webAPI = WebApi()
webAPI.loadEntries()
timetable = TimeTable()

@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord!')
    global guild
    global channel
    global devchannel
    
    #set guild
    for g in client.guilds:
        if g.name == GUILD:
            guild = g
            break
    roles = await guild.fetch_roles()

    #get IDs for roles
    for roleKey, roleName in _ROLENAMES_.items():        
        for role in roles:
            if role.name == roleName:
                roleTable[roleName] = role.id
                
    #get channels
    channel = discord.utils.get(guild.channels, name=_CHANNELNAME_)
    devchannel = discord.utils.get(guild.channels, name=_DEVCHANNEL_)
    #embed = discord.Embed(title="Bot Started", url="http://ezamedia.hu", color=discord.Color.blue())
    #await devchannel.send(embed=embed)
    await client.change_presence(activity=discord.Game(name="The misguided sanctions destroy us!"))
    updateTask.start()

async def devErrorMsg(title, msg):
    embed = discord.Embed(title=title, color=discord.Color.red())
    embed.add_field(name="Error Message:", value=msg)
    await devchannel.send(embed=embed)

@tasks.loop(minutes=10)
async def updateTask():
    
    webAPI.UpdateRequest()
    entries = webAPI.getNewEntriesForClass(_CLASSNAME_)

    for entry in entries:

        #Set color
        c = discord.Color.blue()
        match entry['comment']:
            case 'később jön':
                c = discord.Color.green()
            case 'önálló munka':
                c = discord.Color.red()
            case 'hazamegy':
                c = discord.Color.green()
        mention = ""
        try:
            mention = "<@&" + str(roleTable[_ROLENAMES_[await timetable.getGroupForLesson(
                    datetime.strptime(entry['day'], '%Y-%m-%d').strftime('%A'),
                    entry['lesson'],
                    entry['subject'],
                    entry['missingTeacher'])]]) + ">"
        except Exception as e:
            print(e)
        if mention == "<@&>": #Empty mention (unknown)
            print("Unable to determine group: " + webAPI.defEntryFormat(entry))
            mention = ""
        
        embed = discord.Embed(title=webAPI.getMsgFromEntry(entry), url="https://apps.karinthy.hu/helyettesites/", description=mention, color=c)
        embed.add_field(name="Óra", value=(str(entry['lesson']) + '. ' + entry['subject']), inline=True)

        if entry['room'] != '':
            embed.add_field(name="Terem", value=entry['room'], inline=True)
        if entry['comment'] != '':
            embed.add_field(name="Comment", value=entry['comment'], inline=True)
        if entry['substitutingTeacher'] != '':
            embed.add_field(name="Helyettesítő Tanár", value=entry['substitutingTeacher'], inline=True)
        if entry['missingTeacher'] != '':
            embed.add_field(name="Hiányzó Tanár", value=entry['missingTeacher'], inline=True)

        await channel.send(embed=embed)
    webAPI.saveEntries()
    
client.run(TOKEN)
