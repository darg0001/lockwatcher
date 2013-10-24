'''
Created on 1 Sep 2013

@author: Nia Catlin
'''

import os, subprocess, multiprocessing, threading
from lockwatcher import fileconfig
from lockwatcher import hardwareconfig

dbusobj = None
shuttingDown = False
emailAlert = False

#have to spawn a nonroot process to do it
def lockProcess():
    if fileconfig.DESK_UID != None:
        os.setuid(fileconfig.DESK_UID)
        
    lockProgram = fileconfig.LOCKCMD
    try:
        if lockProgram != None:
            subprocess.call(lockProgram.split(' '))
    except:
        pass
    
    try:
        os.system('qdbus org.kde.screensaver /ScreenSaver Lock') 
    except:
        pass
    
    try:
        os.system('qdbus org.kde.screensaver /ScreenSaver Lock') 
    except:
        pass
    
def lockScreen():
    try:
        P = multiprocessing.Process(target=lockProcess)
        P.start()
    except:
        return False
    return True 

def standardShutdown():
    global shuttingDown
    if shuttingDown == True: return
    shuttingDown = True
    
    unmountEncrypted()
    os.system('/sbin/shutdown -P') #poweroff at the end   

TCUSED = False
DMUSED = True
#dismount encrypted containers    
def unmountEncrypted():
    #doesnt seem to have purge or wipecache options on linux
    if os.path.exists(fileconfig.config['TRIGGERS']['tc_path']):
        subprocess.call(["/usr/bin/truecrypt","--dismount","--force"], shell=True, timeout=2)
    
    if fileconfig.config['TRIGGERS']['dismount_dm'] == 'True':
        devlist = os.listdir('/dev/mapper')
        for dev in devlist:
            if 'crypt' in dev: #can parallelise this a bit
                #not sure how best to do this - area is in use so cryptsetup fails, does dmsetup clear key?
                try:
                    subprocess.call(["/sbin/cryptsetup","remove","crypt"], shell=True, timeout=1)
                    subprocess.call(["/sbin/dmsetup","remove","-f","crypt"], shell=True, timeout=2)
                except: continue
        

#encrypted drives can be specified because they are dismounted after writing
#set to none to disable log writing
LOGFILE = None

class execScript(object):
    def __init__(self, script):
        self.cmd = script
        self.process = None

    def run(self, timeout):
        def target():
            self.process = subprocess.Popen(self.cmd, shell=True)
            self.process.communicate()

        thread = threading.Thread(target=target)
        thread.start()

        thread.join(float(timeout))
        
        #try to terminate it but we don't really care, shutdown is going to happen anyway
        if thread.is_alive():
            self.process.terminate()
            thread.join()

#destroy data, deny access, poweroff
#takes as arguments a message for the logfile and the status of the screen lock
def emergency(device=None):
    #device change events fire quite rapidly 
    #pnly need to call this once
    config = fileconfig.config
    
    global shuttingDown
    if shuttingDown == True: return
    else: shuttingDown = True
    
    #encase everything in a try->except>pass block
    #so if anything fails we skip straight to poweroff
    
    try: 
    
        #disable the device before it can touch memory
        if device != None and os.path.exists(device):
            device = device.split('/')
            deviceEnableSwitch = "/%s/%s/%s/%s/enable"%(device[1],device[2],device[3],device[4])
            print('writing 0 to ',deviceEnableSwitch)
            fd = open(deviceEnableSwitch,'w')
            fd.write('0')
            fd.close()
            
        
        lockStatus = hardwareconfig.checkLock()
        if lockStatus == False: lockScreen()
        
        unmountEncrypted() 
        
        if config['TRIGGERS']['exec_shellscript'] == 'True':
            timeLimit = float(fileconfig.config['TRIGGERS']['script_timeout'])
            thread = execScript('/etc/lockwatcher/sd.sh')
            thread.run(timeout=timeLimit)
            
    except:
        pass
    
    subprocess.call(['/sbin/poweroff','-f'])
    