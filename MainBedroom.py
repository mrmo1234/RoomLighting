#Room lighting and sunrise and sunset sim - Mark O'Dell Started 20/04/2017

#Add a working offline sunrise calculator
#Add more fade pattans
#Add Strobe pattans
#Nighttime def not working

#ServerState and modeseleact need to be pieped in ClientConnectionThread!

#Finish def drawNow(self,): Verable conversion so that it can be changed like the strips

#REFINE the cycaling on the buttons to take into account the device

#Setter - The Trasparancey and target value may change and to enable self timeouts

#modeselect may need to be converted to an object

#Finish Config and State save

##        red,green,blue = TargetValue #Make 255,255,255 into 24-bit RGB color value
##        self.TargetValue24bit = (red << 16)| (green << 8) | blue


#Imports
import time
import datetime
import os
#from Sun import Sun
import socket
import sys
import threading
import multiprocessing.pool
import json
import os.path
import signal
import ConfigParser


import numpy as np
from numpy import where, clip, round, nan_to_num
from collections import deque
import decoder
import fft




#Try critical imports that are likely to be missing
try:
    import ntplib
    ntplibPresent = True
except:
    print("Error importing ntplib! Is it installed?")
    ntplibPresent = False
try:
    import requests
    requestsPresent = True
except:
    print("Error importing requests! Is it installed?")
    requestsPresent = False
try:
    import Adafruit_PCA9685
    Adafruit_PCA9685Present = True
except:
    print("Error importing Adafruit_PCA9685! Is it installed?")
    Adafruit_PCA9685Present = False
try:
    from neopixel import *
    neopixelPresent = True
except:
    print("Error importing neopixel! You need sudo!")
    neopixelPresent = False
try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    GPIOPresent = True
except:
    GPIOPresent = False


#Need to add drawMovingSeg to below defs handalinmg of "Effect"
#State tracker and effect oprateor for the NeoPixel LED strip - Multiple effects can be on the same strip.
class NeoPixelEffectTracker(object):
    def __init__(self,strip,):
        self.strip = strip
        self.CurrentValue = (0,0,0)
        self.TargetValue = (0,0,0)
        self.Effect = None
        self.EffectCompleate = True
        self.RangeStart = 0
        self.RangeEnd = 0
        self.TransitionTime = 0
        self.TransitionTimeLeft = 0
        self.timeout = None
        self.BaseValue = None
        self.StartTransparency = 1
        self.EndTransparency = 0
        self.wheelpoint = 0
        self.DrawOnMutable = 1

    def drawNow(self,):
        if self.Effect == "drawLine_NeoPixel":
            self.drawLine_NeoPixel()
        elif self.Effect == "drawTransparentLine_NeoPixel":
            self.drawTransparentLine_NeoPixel()
        elif self.Effect == "drawFadeTransparentLine_NeoPixel":
            self.drawFadeTransparentLine_NeoPixel()
        elif self.Effect == "drawRainbowCycle":
            self.drawRainbowCycle()
        elif self.Effect == "drawRainbow":
            self.drawRainbow()
        elif self.Effect == "drawOnMutableLine_NeoPixel":
            self.drawOnMutableLine_NeoPixel()
        elif self.Effect == "Done":
            pass
        elif self.Effect == None:
            pass
        else:
            print ("self.Effect '"+str(self.Effect)+"' did not match any available effects!")
            
        

#NEED TO GET THIS WORKING, The Trasparancey and target value may change and to enable self timeouts
##    @property
##    def TargetValue(self):
##        return self.TargetValueTEMP
##
##    @TargetValue.setter
##    def TargetValue(self, NewTargetValue = "WAS NOT SET @setter"):
##        if NewTargetValue != self.ValueLastSet:
##            print ("CHANGED! NewTargetValue = " + str(NewTargetValue) + " self.ValueLastSet = " + str(self.ValueLastSet))
##            self.ValueLastSet = NewTargetValue
##            self.ValueLastSetTime = time.time()
##            self.TargetValueTEMP = NewTargetValue
##            self.effectStartValue = self.CurrentValue
##            print ("CHANGED! self.effectStartValue = " + str(self.effectStartValue))

#   Needs TargetValue, RangeStart,RangeEnd,timeout = None
    def drawLine_NeoPixel(self,):#Uses less CPU then drawTransparentLine_NeoPixel
        for i in range(self.RangeStart,self.RangeEnd+1):#The +1 is needed for base 1 indexing
            self.strip.setPixelColorRGB(i,*self.TargetValue)
        self.Effect = "Done"

#   Needs TargetValue, RangeStart,RangeEnd,timeout = None,DrawOnMutable
    def drawOnMutableLine_NeoPixel(self,):
        for i in range(self.RangeStart,self.RangeEnd+1):#The +1 is needed for base 1 indexing
            if not i%self.DrawOnMutable: #i%12 throws out a reminder, It will be 0 when a multiple of 12. "if not" picks up that 0
                self.strip.setPixelColorRGB(i,*self.TargetValue)
        self.Effect = "Done"
        

#   Needs TargetValue, RangeStart,RangeEnd,transparency = 0.5,timeout = None,BaseValue = None
    def drawTransparentLine_NeoPixel(self,):
        for i in range(self.RangeStart,self.RangeEnd+1):#The +1 is needed for base 1 indexing
            if self.BaseValue == None:
                BaseValue = self.strip.getPixelColor(i)
                #24-bit RGB color value into 255,255,255
                B1 =  BaseValue & 255
                G1 = (BaseValue >> 8) & 255
                R1 = (BaseValue >> 16) & 255
            else:
                R1,G1,B1 = BaseValue
            R2,G2,B2 = self.TargetValue
            CalculatedColour = int((1-self.StartTransparency)*R1 + self.StartTransparency*R2),int((1-self.StartTransparency)*G1 + self.StartTransparency*G2),int((1-self.StartTransparency)*B1 + self.StartTransparency*B2)
            print ("CalculatedColour = "+str(CalculatedColour))
            print (i,CalculatedColour)
            self.strip.setPixelColorRGB(i,*CalculatedColour)
        self.Effect = "Done"

#   Needs TargetValue,RangeStart,RangeEnd,StartTransparency = 0.5,EndTransparency = 1,timeout = None,BaseValue = None
    def drawFadeTransparentLine_NeoPixel(self,):
        for i in range(self.RangeStart,self.RangeEnd+1):#The +1 is needed for base 1 indexing
            LEDPos_value = float(i)
            LEDPos_min = float(self.RangeStart)
            LEDPos_max = float(self.RangeEnd)
            TransVal_min = float(self.StartTransparency)
            TransVal_max = float(self.EndTransparency)

            if self.StartTransparency < self.EndTransparency:
                currentTransparency = ((LEDPos_value-LEDPos_min)/(LEDPos_max-LEDPos_min))*(TransVal_max-TransVal_min)+TransVal_min
            else:
                currentTransparency = ((LEDPos_value-LEDPos_min)/(LEDPos_max-LEDPos_min))*(TransVal_max-TransVal_min)+TransVal_min
                currentTransparency = currentTransparency-TransVal_max

            print ("LEDPos_value = "+ str(LEDPos_value))
            print ("LEDPos_min = "+ str(LEDPos_min))
            print ("LEDPos_max = "+ str(LEDPos_max))
            print ("TransVal_min = "+ str(TransVal_min))
            print ("TransVal_max = "+ str(TransVal_max))
            print ('currentTransparency = '+ str(currentTransparency))
            
            if self.BaseValue == None:
                BaseValue = self.strip.getPixelColor(i)
                #24-bit RGB color value into 255,255,255
                B1 =  BaseValue & 255
                G1 = (BaseValue >> 8) & 255
                R1 = (BaseValue >> 16) & 255
            else:
                R1,G1,B1 = BaseValue
            R2,G2,B2 = self.TargetValue
            CalculatedColour = int((1-currentTransparency)*R1 + currentTransparency*R2),int((1-currentTransparency)*G1 + currentTransparency*G2),int((1-currentTransparency)*B1 + currentTransparency*B2)
            print ("CalculatedColour = "+str(CalculatedColour))
            self.strip.setPixelColorRGB(i,*CalculatedColour)
        self.Effect = "Done"
        
#   Needs firstLEDpos,LastLEDpos
    def drawRainbowCycle(self,):
        if self.RangeStart == None: self.RangeEnd = self.strip.numPixels()#THIS MAY NOT WORK TEST
        numberOfPixels = self.RangeEnd - self.RangeStart
        #Draw rainbow that uniformly distributes itself across all pixels.
        if self.wheelpoint > 256: self.wheelpoint = 0
        self.wheelpoint = self.wheelpoint+1
        for i in range(self.RangeStart,self.RangeEnd):
            self.strip.setPixelColor(i, wheel((int(i * 256 / numberOfPixels) + self.wheelpoint) & 255))
            
    def drawRainbow(self,):
        if self.wheelpoint > 256: self.wheelpoint = 0 #Resets to 0 when it hits the end
        self.wheelpoint = self.wheelpoint+1 #Incramnets Rainbow colour by one
        for i in range(self.RangeStart,self.RangeEnd):
                self.strip.setPixelColor(i, wheel((self.wheelpoint) & 255))
			
#State tracker and effect oprateor for the PWM module LEDs
class LEDinterface(object):
    def __init__(self,PCA9685Channel, LEDAlias, CurrentValue = 0, TargetValue = 0, ChangeMethod = "Done", Bit = 12, TransitionTime = 0, TransitionTimeLeft = 0, ValueLastSet = None,ValueLastSetTime = time.time()):
        self.PCA9685Channel = PCA9685Channel
        self.LEDAlias = LEDAlias
        self.ChangeMethod = "Done"
        self.Bit = Bit
        self.TransitionTime = TransitionTime
        self.TransitionTimeLeft = TransitionTimeLeft
        self.ValueLastSet = ValueLastSet
        self.CurrentValue = CurrentValue
        self.TargetValue = TargetValue
        self.TargetValueTEMP = TargetValue

    @property
    def TargetValue(self):#This runns everytime 
        return self.TargetValueTEMP

    @TargetValue.setter
    def TargetValue(self, NewTargetValue = "WAS NOT SET @setter"):
        if NewTargetValue != self.ValueLastSet:
            print (self.LEDAlias+" CHANGED! NewTargetValue = " + str(NewTargetValue) + " self.ValueLastSet = " + str(self.ValueLastSet))
            self.ValueLastSet = NewTargetValue
            self.ValueLastSetTime = time.time()
            self.TargetValueTEMP = NewTargetValue #NewTargetValue has to be placed into a TEMP Var
            #Trying to place it in TargetValue will just re-run this @TargetValue.setter
            #What is returned by @property is what comes out of the setter
            self.effectStartValue = self.CurrentValue
            print (self.LEDAlias+" CHANGED! self.effectStartValue = " + str(self.effectStartValue))

    
    #Apply Vals to PWM
    #def writeValto_externalPWM(self):

    #def AnimationStep_externalPWM(self):
        
    def writeValtoexternalPWM(self):
        #Need to split this into a "Animation step" and "writeout" defs
        
        if self.CurrentValue == self.TargetValue: return None # No point if it is the value
        if self.ChangeMethod == 'Instant':
            try:
                externalPWM.set_pwm(self.PCA9685Channel,0,self.TargetValue)
                self.CurrentValue = self.TargetValue
            except Exception as errorData:
                print("FAILED WRITE TO I2C (Instant)")
                if PCA9685Present == False:
                    print ("There is no PCA9685 connected!")
                else:
                    print("Channel: "+str(self.PCA9685Channel) + ", Value: " + str(self.TargetValue))
                    print("\r\n"+str(errorData)+"\r\n")
        elif self.ChangeMethod == 'Fade':
            if self.CurrentValue > self.TargetValue: #Fade Down

                target = self.TargetValue
                current = self.CurrentValue
                settime = self.ValueLastSetTime
                transitiontime = self.TransitionTime
                effectStartValue = self.effectStartValue

                endTime = settime + transitiontime

                #DOWN
                starttime = time.time()
                
                timeleft = endTime - time.time()

                if timeleft == 0:
                    current = target
                else:
                    timeleftCoefficient  = transitiontime/timeleft
                    percentiageleft = 100/timeleftCoefficient
                    TransitionTargetCoefficient = effectStartValue/100
                    
                    current=TransitionTargetCoefficient*percentiageleft
                
                
##                print ("led at " + str(timeleft) + " is " + str(current))
##
##                print ("settime "+str(settime))
##                print ("endTime "+str(endTime))
##                print ("timeleft "+str(timeleft))
##                print ("percentiageleft "+str(percentiageleft))
##                print ("target "+str(target))
##                print ("current "+str(current))
##                print ("----------------------------------------")
##
##                print ("Finished after " + str(time.time() - starttime) + " Seconds")
                try:
                    externalPWM.set_pwm(self.PCA9685Channel,0,int(current))
                    self.CurrentValue = current
                except Exception as errorData:
                    print("FAILED WRITE TO I2C (Fade Down)")
                    if PCA9685Present == False:
                        print ("There is no PCA9685 connected!")
                    else:
                        print("Channel: "+str(self.PCA9685Channel) + ", Value: " + str(self.TargetValue))
                        print("\r\n"+str(errorData)+"\r\n")
                
                if current < target:
                    self.CurrentValue = self.TargetValue
                    self.ChangeMethod = 'Done'
                
            
            elif self.CurrentValue < self.TargetValue:#Fade Up

                target = self.TargetValue
                current = self.CurrentValue
                settime = self.ValueLastSetTime
                transitiontime = self.TransitionTime

                endTime = settime + transitiontime

                #UP
                starttime = time.time()
                timeleft = endTime - time.time()

                if timeleft == 0:
                    current = target
                else:
                    timeleftCoefficient  = transitiontime/timeleft
                    percentiageleft = 100/timeleftCoefficient

                    ledValtoGo = target - self.effectStartValue
                    targetCoefficient=ledValtoGo/100
                    valueleft=targetCoefficient*percentiageleft

                    current = target - valueleft
                
##                print ("led at " + str(timeleft) + " is " + str(current))
##
##                print ("settime "+str(settime))
##                print ("endTime "+str(endTime))
##                print ("timeleft "+str(timeleft))
##                print ("percentiageleft "+str(percentiageleft))
##                print ("targetCoefficient "+str(targetCoefficient))
##                print ("target "+str(target))
##                print ("ledValtoGo "+str(ledValtoGo))
##                print ("current "+str(current))
##                print ("----------------------------------------")
##
##                print ("Finished after " + str(time.time() - starttime) + " Seconds")

                
                self.CurrentValue = current
                
                if current > target:
                    self.CurrentValue = self.TargetValue
                    self.ChangeMethod = 'Done'

#This needs to be moved into it's own def
##            elif self.ChangeMethod == 'Rainbow':
##                if self.RangeStart == None: self.RangeEnd = self.strip.numPixels()#THIS MAY NOT WORK TEST
##                numberOfPixels = self.RangeEnd - self.RangeStart
##                #Draw rainbow that uniformly distributes itself across all pixels.
##                if self.wheelpoint > 256: self.wheelpoint = 0
##                self.wheelpoint = self.wheelpoint+1
##                for i in range(self.RangeStart,self.RangeEnd):
##                    self.strip.setPixelColor(i, wheel((int(i * 256 / numberOfPixels) + self.wheelpoint) & 255))
                    
            else:
                print ("self.TargetValue <= self.CurrentValue OR self.CurrentValue < self.TargetValue FAILED")
        elif self.ChangeMethod == 'Done':
            pass
        else:
            print ("ChangeMethod Failed to match anything in writeValtoexternalPWM!!!")
        
        if self.CurrentValue > 4095: self.CurrentValue = 4095 #Filter out over max
        if self.CurrentValue <= 0.9: self.CurrentValue = 0 #Filter out negative values
        try:
            externalPWM.set_pwm(self.PCA9685Channel,0,int(self.CurrentValue))
            #print (str(self.CurrentValue) + " Written to pwm")
        except Exception as errorData:
                print ("FAILED WRITE TO I2C (Fade Up)")
                if PCA9685Present == False:
                    print ("There is no PCA9685 connected!")
                else:
                    print("\r\n"+str(errorData)+"\r\n")

#Created to keep track of mode and perform tasks based on mode - Currently unused.
class modeStateTracker:
    def __init__(self,):
        self.CurentSelectedModeIndex = 0
        self.MaxModesIndex = -1
        self.modes = []
        
    def addmode(self,addedmode):
        self.modes.append(addedmode)
        self.MaxModesIndex = self.MaxModesIndex + 1

    def removemode(self,modetoberemoved):
        try:
            self.modes.remove(modetoberemoved)
            self.MaxModesIndex = self.MaxModesIndex - 1
            if self.CurentSelectedModeIndex > self.MaxModesIndex:
                self.CurentSelectedModeIndex = self.CurentSelectedModeIndex - 1
            return True
        except:
            return False
    
    def CurentSelectedMode(self,):
        return self.modes[self.CurentSelectedModeIndex]

    def ListModes (self,):
        return self.modes
    
    def NextMode(self,):
        if self.CurentSelectedModeIndex < self.MaxModesIndex:
            self.CurentSelectedModeIndex = self.CurentSelectedModeIndex + 1
        else:
            self.CurentSelectedModeIndex = 0
            
    def PrevMode(self,):
        if self.CurentSelectedModeIndex == 0:
            self.CurentSelectedModeIndex = self.MaxModesIndex
        else:
            self.CurentSelectedModeIndex = self.CurentSelectedModeIndex - 1

#Unfinished - Intended to be a substitute for when no NeoPixel hardware is present
class Adafruit_NeoPixelDUMMY:
    def begin(self,):
        return False
    def show(self,):
        return False
    def setPixelColorRGB(self,):
        return False
    def setPixelColor(self,):
        return False
    def numPixels(self,):
        return 1
    
#Set starting variables, None of the globals are needed but it helps keep track of what needs to be global in defs
setsecSTARTED = False

global keepgoing
keepgoing = True

global currentHour
currentHour = None

global currentMinute
currentMinute = None

global timeTempChecked
timeTempChecked = 0.1

global timeSunChecked
timeSunChecked = 0.1

global matpresstime
matpresstime = 0.1

endtime = 0
starttime = 0
timeToLoop = 0.0113880634308



global lastButtonBeforeMatPress
lastButtonBeforeMatPress = None

current_temperatures = None
last_current_temperatures = None

#Server status - At startup
ServerState = {
    "StartUpTime":time.time(),
    "FilePlaying":"None",
    "FilePlayingExtension":"None",
    "StartFilePlayTime":0,
    "ServerTimeSyncAccuracy":0,
    "ServerVersion":0}

global lastButtonPressed #Possible States - mode, onOff, mat

global modeselect

global lightsOn #Possible modes - True, False

global LEDsecR
global LEDsecG
global LEDsecB
global LEDTerW
global LEDQuatW
global LEDQuinW


#Defs for drawing LEDs
#This needs to be converted in to an effect and moved into the NeoPixelEffectTracker Class
def drawClock (strip,firstLEDpos=0,Inverted = False,MarkerColour = (1,1,1),HourColour = (1,0,0),MinutesColour = (0,1,0)):#GRB 
    #This is made to be 144 Pixels long
    #Inverted = True #force inverted
    currentHour, currentMinute, currentSecond = getTheTime()#Get the time (Once) and return in ints
    if currentHour > 12:#Converts time past 12 into 
        PM = True
        currentHour = currentHour - 12
    #currentHour = 5 #Time override
    #currentMinute = currentSecond #Time override
    #firstLEDpos = 144

    if Inverted == False: # Normal I.E. 1 to 144
        lastLEDpos=firstLEDpos+144
        totalLEDs= lastLEDpos-firstLEDpos
        lightthisrange=currentHour*12 # Converts number of hours into number of Hour Segments that shold be lit
        for i in range(firstLEDpos,lastLEDpos):
            for j in range (lightthisrange):
                strip.setPixelColorRGB(j+firstLEDpos,*HourColour)#GRB Draw hour
        lastled = j+1
        
        for i in range(lastled,(lastled+12)):
            strip.setPixelColorRGB(i+firstLEDpos,0,0,0)#GRB Blanks LED incase Miniuts somehow goes down.
            
        for n in range(lastled,(lastled+12)):
            lightrange = currentMinute/5
            if n <= lastled+lightrange:
                strip.setPixelColorRGB(n+firstLEDpos,*MinutesColour)#GRB Draws leds that should be lit for minutes
                
        for i in range(0,144):        
                if not i%12: #i%12 throws out a reminder, It will be 0 when a multiple of 12. "if not" picks up that 0
                    strip.setPixelColorRGB(firstLEDpos+i,*MarkerColour)#GRB White hour marker

        strip.setPixelColorRGB(totalLEDs+firstLEDpos,*MarkerColour)#End White hour marker
    else: #Inverted draw direction
        
        #Work out our length
        hourlength = currentHour*12
        lastHourpos=firstLEDpos-hourlength
        for ledpos in range(firstLEDpos,lastHourpos,-1):#Draw hour
            strip.setPixelColorRGB(ledpos,*HourColour)#GRB 

        EndLEDpos = firstLEDpos-144

        firstMinPOS = lastHourpos-1
        minutelength = currentMinute/5
        lastMinpos = lastHourpos-minutelength

        for ledpos in range(firstMinPOS,firstMinPOS-12,-1):#Blanks LED when Minutes goes down.
            strip.setPixelColorRGB(ledpos,0,0,0)#GRB 
        
        for ledpos in range(firstMinPOS,lastMinpos-1,-1):#Draw Minutes
            strip.setPixelColorRGB(ledpos,*MinutesColour)#GRB
        
        for ledpos in range(0,144):#White hour marker      
            if not ledpos % 12: #i%12 throws out a reminder, It will be 0 when a multiple of 12. "if not" picks up that 0
                strip.setPixelColorRGB(firstLEDpos-ledpos,*MarkerColour)#GRB
        strip.setPixelColorRGB(EndLEDpos,*MarkerColour)#End White hour marker #* extrats the tuples from MarkerColour

        
#This needs to be converted in to an effect and moved into the NeoPixelEffectTracker Class
def drawToAllNeopixelLED(strip,colourToDraw=(0,0,0)):
    for i in range (strip.numPixels()):
        strip.setPixelColorRGB(i,*colourToDraw)
    
def drawNight():
    global keepgoing
    global LEDsecR
    global LEDsecG
    global LEDsecB
    global LEDTerW
    global LEDQuatW
    global LEDQuinW
    
    if keepgoing == False: return
    
    drawToAllNeopixelLED(primeNeopixelLED,(0,0,1))#GRB
    
    LEDTerW.ChangeMethod = 'Instant'
    LEDTerW.TargetValue = 0

    LEDsecR.ChangeMethod = 'Instant'
    LEDsecR.TargetValue = 0
    
    LEDsecG.ChangeMethod = 'Instant'
    LEDsecG.TargetValue = 0


    LEDsecB.ChangeMethod = 'Instant'
    LEDsecB.TargetValue = 41
    LEDsecB.Bit = 12

def allLEDsOff():
    global LEDsecR
    global LEDsecG
    global LEDsecB
    global LEDTerW
    global LEDQuatW
    global LEDQuinW

    #Turn off Prime
    drawToAllNeopixelLED(primeNeopixelLED)#Passing only strip blanks all to 0

    if PCA9685Present == False: return
    #Turn off Ter
    LEDTerW.ChangeMethod = 'Instant'
    LEDTerW.TargetValue = 0
    
    #Turn off Sec
    LEDsecR.ChangeMethod = 'Instant'
    LEDsecR.TargetValue = 0
    
    LEDsecG.ChangeMethod = 'Instant'
    LEDsecG.TargetValue = 0

    LEDsecB.ChangeMethod = 'Instant'
    LEDsecB.TargetValue = 0
            
#Defs for calaulaions, desisions and mathmathics

#Used as part of the rainbow effects
def wheel(pos):
	"""Generate rainbow colors across 0-255 positions."""
	if pos < 85:
		return Color(pos * 3, 255 - pos * 3, 0)
	elif pos < 170:
		pos -= 85
		return Color(255 - pos * 3, 0, pos * 3)
	else:
		pos -= 170
		return Color(0, pos * 3, 255 - pos * 3)

#Based on the coleacted info on button, time and state vars what should we do?
def actionLogic():
    global keepgoing
    global lightsOn
    global timeTempChecked
    global modeselect
    global LEDsecR
    global LEDsecG
    global LEDsecB
    global LEDTerW
    global LEDQuatW
    global LEDQuinW
    global matpresstime
    global lastButtonPressed
    global lastButtonBeforeMatPress
    global tempSensors
    global async_result
    global current_temperatures
    global last_current_temperatures
    global parent_conn_Temp
    
    keepgoing = True
    
    if modeselect["DeviceInControl"] == True: # This blocks timmed events when a device is in control
        return
    
    #If device is not in control, This is the Code to trigger at a time
    currentHour, currentMinute, currentSecond = getTheTime()
    
    modeselect['modeselect'] = "Nighttime" #Force Always night
##    if 1 <= currentHour <= 8:
##        modeselect['modeselect'] = "Nighttime"
##    elif 9 <= currentHour <= 16:
##        modeselect['modeselect'] = "Daytime"
##    elif 17 <= currentHour <= 10:
##        modeselect['modeselect'] = "Evening"
##    elif 19 <= currentHour <= 24:
##        modeselect['modeselect'] = "Nighttime"
##    elif 0 <= currentHour <= 0:
##        modeselect['modeselect'] = "Nighttime"
##    else:
##        pass
    
    if lastButtonPressed == "mode":
        if (modeselect['modeselect'] == "Birthday"):
            if Birthday == "party":
                #Turn off Ter
                LEDTerW.ChangeMethod = 'Instant'
                LEDTerW.TargetValue = 0
                #Turn off Sec
                LEDsecR.ChangeMethod = 'Instant'
                LEDsecR.TargetValue = 0
                
                LEDsecG.ChangeMethod = 'Instant'
                LEDsecG.TargetValue = 0

                LEDsecB.ChangeMethod = 'Instant'
                LEDsecB.TargetValue = 0
                #Run the rainbow
                effectTrackerRainbow1.rainbowCycle(0,10)
                effectTrackerRainbow2.rainbowCycle(10,20)
                effectTrackerRainbow3.rainbowCycle(20,30)
                effectTrackerRainbow4.rainbowCycle(30,40)
                effectTrackerRainbow5.rainbowCycle(40,50)
                effectTrackerRainbow6.rainbowCycle(50,60)
            else:
                allLEDsOff()
                print (str(Birthday)+" Birthday did not match any of the ifs!")
        elif (modeselect['modeselect'] == "Daytime"):
            if modeselect['Daytime'] == "off":
                allLEDsOff()
                lightsOn = True #This make it so that the on/off button always flips what the mode is doing
            elif modeselect['Daytime'] == "lighting":
                #Turn On TerWhite
                LEDTerW.ChangeMethod = 'Instant'
                LEDTerW.TargetValue = 4095
                LEDTerW.Bit = 12
                lightsOn = False #This make it so that the on/off button always flips what the mode is doing
            else:
                print (str(modeselect['Daytime'])+" modeselect['Daytime'] did not match any of the ifs!")
        elif (modeselect['modeselect'] == "Evening"):
            if modeselect['Evening'] == "sunset":
                pass
            elif modeselect['Evening'] == "off":
                pass
            else:
                print (str(modeselect['Evening'])+" modeselect['Evening'] did not match any of the ifs!")
            #Turn off Ter
            LEDTerW.ChangeMethod = 'Instant'
            LEDTerW.TargetValue = 0
            #Turn off Prime
            drawToAllNeopixelLED(primeNeopixelLED)#Passing only strip blanks all to 0
            #Do night
            setsecNight ()
        elif (modeselect['modeselect'] == "Nighttime"):
            lightsOn = True #Effetivly defines what the on/off button should do, In this case turn lights on.
            if modeselect['Nighttime'] == "off":
                allLEDsOff()
                
            elif modeselect['Nighttime'] == "clock":
                #Dim blue on
                LEDsecB.ChangeMethod = 'Instant'
                LEDsecB.TargetValue = 41
                LEDsecB.Bit = 12

                drawToAllNeopixelLED(primeNeopixelLED)#Blanks when used this way

                #Blue background on neopix - This must be drawn before the clock
                effectTracker1.Effect = "drawOnMutableLine_NeoPixel"
                effectTracker1.TargetValue = (0,0,1)
                effectTracker1.RangeStart = 0
                effectTracker1.RangeEnd = 443
                effectTracker1.StartTransparency = 1
                effectTracker1.DrawOnMutable = 2

                effectTracker1.drawNow()
                
                #Where to draw clock
                firstLEDpos=373
                drawClock (primeNeopixelLED,firstLEDpos,True)

                
                
                #Fade off TerW
                LEDTerW.ChangeMethod = 'Fade'
                LEDTerW.TargetValue = 0
                LEDTerW.Bit = 12
                LEDTerW.TransitionTime = 1
                
            elif modeselect['Nighttime'] == "night":
                #Turn off Ter
                LEDTerW.ChangeMethod = 'Fade'
                LEDTerW.TargetValue = 0

                #Turn off LEDQuatW
                LEDQuatW.ChangeMethod = 'Fade'
                LEDQuatW.TargetValue = 0
                
                #Turn off Sec
                LEDsecR.ChangeMethod = 'Instant'
                LEDsecR.TargetValue = 0
                
                LEDsecG.ChangeMethod = 'Instant'
                LEDsecG.TargetValue = 0
                
                #Dim blue on
                LEDsecB.ChangeMethod = 'Instant'
                LEDsecB.TargetValue = 41
                LEDsecB.Bit = 12

                #Neopixel blue
                effectTracker1.Effect = "drawLine_NeoPixel"
                effectTracker1.TargetValue = (0,0,1)
                effectTracker1.RangeStart = 0
                effectTracker1.RangeEnd = 447

    
    #effectTracker1.drawNow()
            else:
                print (str(modeselect['Nighttime'])+" Nighttime did not match any of the ifs!")
        else:
            print (str(modeselect['modeselect'])+" modeselect['modeselect'] did not match any of the ifs!")
            allLEDsOff()
    elif lastButtonPressed == "onOff":
        if lightsOn == True:
            
            #Turn on Ter
            LEDTerW.ChangeMethod = 'Fade'
            LEDTerW.TargetValue = 4095
            LEDTerW.Bit = 12
            LEDTerW.TransitionTime = 2

            #Turn on LEDQuatW
            LEDQuatW.ChangeMethod = 'Fade'
            LEDQuatW.TargetValue = 4095
            LEDQuatW.Bit = 12
            LEDQuatW.TransitionTime = 2

            
            #Turn off Sec
            LEDsecR.ChangeMethod = 'Instant'
            LEDsecR.TargetValue = 0
            
            LEDsecG.ChangeMethod = 'Instant'
            LEDsecG.TargetValue = 0

            LEDsecB.ChangeMethod = 'Instant'
            LEDsecB.TargetValue = 0
            
            drawToAllNeopixelLED(primeNeopixelLED)#Passing only strip blanks all to 0
        else:

            #Fade off TerW
            LEDTerW.ChangeMethod = 'Fade'
            LEDTerW.TargetValue = 0
            LEDTerW.Bit = 12
            LEDTerW.TransitionTime = 2

            #Turn off LEDQuatW
            LEDQuatW.ChangeMethod = 'Fade'
            LEDQuatW.TargetValue = 0
            LEDQuatW.Bit = 12
            LEDQuatW.TransitionTime = 2
            
            #Turn off Sec
            LEDsecR.ChangeMethod = 'Instant'
            LEDsecR.TargetValue = 0
            
            LEDsecG.ChangeMethod = 'Instant'
            LEDsecG.TargetValue = 0

            LEDsecB.ChangeMethod = 'Instant'
            LEDsecB.TargetValue = 0
            
            drawToAllNeopixelLED(primeNeopixelLED)#Passing only strip blanks all to 0
            
    elif lastButtonPressed == "mat":
        LEDTerW.ChangeMethod = 'Fade'
        #LEDTerW.TargetValue = 2095
        LEDTerW.TargetValue = 512
        LEDTerW.Bit = 12
        LEDTerW.TransitionTime = .5
        
        if 60 <= (time.time() - matpresstime): #300 is 5 Min
            print (time.time())
            print (matpresstime)
            print (time.time() - matpresstime)
            lastButtonPressed = lastButtonBeforeMatPress
            print ("6 sec has passed since matpresstime #3642")
    else:
        print ("Nothing matched ifs in lastButtonPressed!")

    #Temp sencing
    #if 300 <= (time.time() - timeTempChecked): #300 is 5 Min
    if 60 <= (time.time() - timeTempChecked): #300 is 5 Min
        timeTempChecked = time.time()#Updates the time, Effectively resetting the clock until next measurement
        print ("Update temps now!")
        tempSensors = getTempSensorList()
        #multiprocessing way
        #This indent needs to be in a timmed IF
        parent_conn_Temp, child_conn_Temp = multiprocessing.Pipe()
        p = multiprocessing.Process(target=updateTemp, args=(tempSensors,child_conn_Temp,))
        p.start()

        tempSensorsGet = threading.Thread(target=tempSensorsGetThread,)
        tempSensorsGet.start()
        
    if enableTemperatureLogging == True and current_temperatures != last_current_temperatures :
        last_current_temperatures = current_temperatures
        file_name = time.strftime("%Y-%m-%d")
        if not os.path.exists("TemperatureLog"):
            os.makedirs("TemperatureLog")
        
        if os.path.isfile("TemperatureLog/"+file_name+".txt") == False:
            
            TemperatureLog = open("TemperatureLog/"+file_name+".txt","w")
        else:
            TemperatureLog = open("TemperatureLog/"+file_name+".txt","a")
        print (json.dumps(current_temperatures))
        TemperatureLog.write(json.dumps(current_temperatures)+"\r\n")
        TemperatureLog.close()

#Get Sunset and rise times
def getSunTimes(coords):
    getSunTimes(coords)
    sun = Sun()
    
    # Sunrise time UTC (decimal, 24 hour format)
    #print sun.getSunriseTime( coords )['decimal']
    #print str(1+(sun.getSunriseTime( coords )['decimal']))
    # Sunset time UTC (decimal, 24 hour format)
    #print sun.getSunsetTime( coords )['decimal']


    if 300 <= (time.time() - timeSunChecked): #300 is 5 Min
        timeSunChecked = time.time()#Updates the time, Effectively resetting the clock until next measurement       
        request = requests.get('http://api.sunrise-sunset.org/json?lat='+str(longitude)+'&lng='+str(latitude)+'&formatted=0')
        timestring = str(request.content)
        
        utcsunrise = timestring[34:39]
        utcsunset = timestring[71:76]
        utcmorning = timestring[182:187]
        utcnight = timestring[231:236]
    
    #print ("utcsunrise= "+utcsunrise)
    #print ("utcsunset= "+utcsunset)
    #print ("utcmorning= "+utcmorning)
    #print ("utcnight= "+utcnight)
    return 


#Get Sensor data
# Pass to this the Sensor ID as a dictionary {'28-0416a42e03ff': None}, it will retuen a dictionary {'28-0416a42e03ff': 22.75}
def updateTemp (tempSensorList,child_conn):
    global tempSensors
    temp_c_List = {}
    for i in tempSensorList:
        deviceDIR = "/sys/bus/w1/devices/"+i+"/w1_slave"
        filepresent = os.path.isfile(deviceDIR)
        if filepresent == True:
            file=open(deviceDIR,'r')
            w1_slaveData = file.readlines()
            if w1_slaveData[0].strip()[-3:] != 'YES':
                print ("ERROR w1_slaveData for "+i+" is "+w1_slaveData[0].strip()[-3:])
                temp_c_List[i] = None
            if str(w1_slaveData[0].strip()[:26]) == "00 00 00 00 00 00 00 00 00":
                print (i+" Not Connected to 1W Bus! Data 00 00 00 00 00 00 00 00 00")
                temp_c_List[i] = None
            elif str(w1_slaveData[0].strip()[:26]) == "ff ff ff ff ff ff ff ff ff":
                print (i+" Not Connected to 1W Bus! Data ff ff ff ff ff ff ff ff ff")
                temp_c_List[i] = None
            else:
                equals_pos = w1_slaveData[1].find('t=')
                if equals_pos != -1:
                    temp_string = w1_slaveData[1][equals_pos+2:]
                    temp_cI = float(temp_string) / 1000.0
                    temp_c_List[i] = temp_cI
            file.close()
        else:
            print ("There is no file for "+i)
            temp_c_List[i] = None
    tempSensorList = temp_c_List
    tempSensorList["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
    child_conn.send(tempSensorList)#Send the data back to the main process
    child_conn.close()

def getTempSensorList():
    tempSensors={}
    devicesDIR = os.listdir("/sys/bus/w1/devices/")
    for i in devicesDIR:
        iStriped = i[:2]
        if iStriped == "28":
            tempSensors[i]= None
    return tempSensors

def tempSensorsGetThread():
    global current_temperatures
    global parent_conn_Temp
    try:
        current_temperatures = parent_conn_Temp.recv()
    except EOFError:
        print ("parent_conn_Temp.recv() EOF found")
        modeselect["DeviceInControl"] = False

def animationFileRead(child_conn_animationFileRead,ServerState):
    mediaPath = "MusicAnimationFiles/"+ServerState["FilePlaying"]+ServerState["FilePlayingExtension"]
    config_filename = mediaPath + ".cfg"
    cache_filename = mediaPath + ".fft"
    
    matrix_buffer = deque([], 1000)
    
    attenuate_pct = 0.0
    sd_low = 0.5
    sd_high = 0.75

    FFTconfig = ConfigParser.RawConfigParser(allow_no_value=True)
    with open(config_filename) as f:
        FFTconfig.readfp(f)
        chunk_size = FFTconfig.getint('fft', 'chunk_size')
        sample_rate = FFTconfig.getint('fft', 'sample_rate')
        total_frames = FFTconfig.getint('fft', 'total_frames')
        audio_length = FFTconfig.getint('fft', 'audio_length')
        chunks_per_sec = FFTconfig.getint('fft', 'chunks_per_sec')
        min_frequency = FFTconfig.getfloat('fft', 'min_frequency')
        max_frequency = FFTconfig.getfloat('fft', 'max_frequency')
        gpio_len = FFTconfig.getint('fft', 'gpio_len')
        num_channels = FFTconfig.getint('fft', 'num_channels')
        
    cache_matrix = np.loadtxt(cache_filename)
    
    # get std from matrix / located at index 0
    std = np.array(cache_matrix[0])

    # get mean from matrix / located at index 1
    mean = np.array(cache_matrix[1])
    
    # delete mean and std from the array
    cache_matrix = np.delete(cache_matrix, 0, axis=0)
    cache_matrix = np.delete(cache_matrix, 0, axis=0)
    
    cache_matrix_length = len(cache_matrix)
    
    #chunks_per_sec = ((16 * num_channels * sample_rate) / 8) / chunk_size
    print("chunks_per_sec: "+str(chunks_per_sec))
    print("std: " + str(std))
    print("mean: " + str(mean))
    
    #true_chunks_per_sec = (total_frames / num_channels) / audio_length
    true_chunks_per_sec = cache_matrix_length / audio_length
    
    row = 0
    matrix = cache_matrix[0]

    

    print ("cache_matrix_length = " + str(cache_matrix_length))
    print ("total_frames = " + str(total_frames))
    duration_of_chunk = float(1) / true_chunks_per_sec
    
    while row <= cache_matrix_length:
        time.sleep(0.02)#This is to save CPU Cycles and allows other threads to run
        # Control lights with cached timing values
        if time.time() >= ServerState["StartFilePlayTime"]:
#            print ("Time = "+ str(time.time()))
#            print ("ServerState +  row/true_chunks_per_sec")
#            print (ServerState["StartFilePlayTime"] +(safe_div(row,true_chunks_per_sec)))
#            print ("row = " + str(row))
#            print ("true_chunks_per_sec = " + str(true_chunks_per_sec))
#            (true_chunks_per_sec / float(60))
#            if time.time() >= (ServerState["StartFilePlayTime"] + (safe_div(row,(true_chunks_per_sec / float(60))))):
#        
            if time.time() >= ServerState["StartFilePlayTime"] + (row * duration_of_chunk):
                print ("   time.time() = "+str(time.time()))
                print ("If time result = "+str(ServerState["StartFilePlayTime"] + (row * duration_of_chunk)))
                print ("   (row * dur) = " + str(row * duration_of_chunk))
                print ("           row = "+str(row))
                if row < len(cache_matrix):
                    matrix = cache_matrix[row]
                if matrix is None:
                    print ("Out of data in cache_matrix")

                matrix_buffer.appendleft(matrix) # What is this doing?
                
                
                brightness = matrix - mean + (std * 0.5)
                brightness = (brightness / (std * (sd_low + sd_high)))* (1.0 - (attenuate_pct / 100.0))
                
                # insure that the brightness levels are in the correct range
                brightness = clip(brightness, 0.0, 1.0)
                # brightness = round(brightness, decimals=3)
                brightness = nan_to_num(brightness)
                #print (str(brightness))
                brightness = brightness.tolist()
                child_conn_animationFileRead.send(brightness)
                print ("animationFileRead just pushed anothe value")
                # Read next chunk of data from music mediaPath
                #data = music_file.readframes(chunk_size) ## Don't need to pull in sound data
                #time.sleep((float(1)/chunks_per_sec)*2)# First atempt at timming (too fast)
                
                row += 1
    print ("Looped out of while")
    
    
    if ServerState[".roomaniFilePresent"] == True:
        pass
    if os.path.exists("MusicAnimationFiles/"+ServerState["FilePlaying"]+".roomani"):
        timingFile = open("MusicAnimationFiles/"+ServerState["FilePlaying"]+".roomani", "r")
        print ("animationFileRead Found "+ (ServerState["FilePlaying"]))
        EOFfound = False
    else:
        if ServerState[".roomaniFilePresent"] == True:
            print ("animationFileRead is unable to locate " + (ServerState["FilePlaying"])+ ", This should have been caught before now!")
        EOFfound = True
    
    line = None
    if EOFfound == False: line = timingFile.readline()
    while EOFfound == False:
        #print ("while EOFfound in animationFileRead tick")
        time.sleep(0.01)#This is to save CPU Cycles and allows other threads to run
        if line != "":
            timestamp,instructionselect,instructiondata = line.split('#')
            if time.time() >= float(timestamp)+ServerState["StartFilePlayTime"]:
                print ("instructionselect = "+instructionselect)
                print (line)

                child_conn_animationFileRead.send(line)#Send data to main process
                
                line = timingFile.readline()
        else:
            EOFfound = True
            modeselect["DeviceInControl"] = False
            modeselect["DeviceActive"] = False
            timingFile.close()
            
def animationFileSet():# This runs as a thread to avoid hanging on .recv()
    global LEDsecR
    global LEDsecG
    global LEDsecB
    global LEDTerW
    global LEDQuatW
    global LEDQuinW
    global modeselect
    global effectTracker1
    global effectTracker2
    global effectTracker3
    global effectTracker4
    global effectTracker5
    global effectTracker6
    global effectTracker7
    global effectTracker8
    global effectTracker8
    global effectTracker9
    
    print ("animationFileSet running")
    
    while modeselect["DeviceInControl"] == True:
        print ("animationFileSet tick")
        time.sleep(0.01)#This is to save CPU Cycles and allows other threads to run
        #Read the data form animationFileRead using this end of the process pipe
        try:
            line = parent_conn_animationFileRead.recv()
            print ("animationFileSet just pulled a line")
            #print ("Datatype of line is " + str(type(line)))
        except EOFError:
            print ("parent_conn_animationFileRead.recv() EOF found")
            modeselect["DeviceInControl"] = False
        if line != "" and type(line) == str:
            timestamp,instructionselect,instructiondata = line.split('#')
            if instructionselect == "LEDsecR":
                LEDsecR.update(json.loads(instructiondata))
            elif instructionselect == "LEDsecG":
                LEDsecG.update(json.loads(instructiondata))
            elif instructionselect == "LEDsecB":
                LEDsecB.update(json.loads(instructiondata))
            elif instructionselect == "LEDTerW":
                LEDTerW.update(json.loads(instructiondata))
            elif instructionselect == "LEDQuatW":
                LEDQuatW.update(json.loads(instructiondata))
            elif instructionselect == "LEDQuinW":
                LEDQuinW.update(json.loads(instructiondata))
                
            elif instructionselect == "effectTracker1":
                effectTracker1.update(json.loads(instructiondata))
            elif instructionselect == "effectTracker2":
                effectTracker2.update(json.loads(instructiondata))
            elif instructionselect == "effectTracker3":
                effectTracker3.update(json.loads(instructiondata))
            elif instructionselect == "effectTracker4":
                effectTracker4.update(json.loads(instructiondata))
            else:
                print ("The file instructionselect did not match any known LEDs or Effects!")
        elif type(line) is list:
            #print ("elif line is list") 
            print (str(line))
            #print ("line [0] = " + str(line[0]))
            effectTracker1.Effect = "drawLine_NeoPixel"
            effectTracker1.TargetValue = (0,int(line[0]* 255),0)
            effectTracker1.RangeStart = 0
            effectTracker1.RangeEnd = 2
            
            effectTracker2.Effect = "drawLine_NeoPixel"
            effectTracker2.TargetValue = (0,int(line[1]* 255),0)
            effectTracker2.RangeStart = 3
            effectTracker2.RangeEnd = 5
            
            effectTracker3.Effect = "drawLine_NeoPixel"
            effectTracker3.TargetValue = (0,int(line[2]* 255),0)
            effectTracker3.RangeStart = 6
            effectTracker3.RangeEnd = 8
            
            effectTracker4.Effect = "drawLine_NeoPixel"
            effectTracker4.TargetValue = (0,int(line[3]* 255),0)
            effectTracker4.RangeStart = 9
            effectTracker4.RangeEnd = 12
            
            effectTracker5.Effect = "drawLine_NeoPixel"
            effectTracker5.TargetValue = (0,int(line[4]* 255),0)
            effectTracker5.RangeStart = 13
            effectTracker5.RangeEnd = 15
            
            effectTracker6.Effect = "drawLine_NeoPixel"
            effectTracker6.TargetValue = (0,int(line[5]* 255),0)
            effectTracker6.RangeStart = 16
            effectTracker6.RangeEnd = 18

            effectTracker7.Effect = "drawLine_NeoPixel"
            effectTracker7.TargetValue = (0,int(line[6]* 255),0)
            effectTracker7.RangeStart = 19
            effectTracker7.RangeEnd = 21

            effectTracker8.Effect = "drawLine_NeoPixel"
            effectTracker8.TargetValue = (0,int(line[7]* 255),0)
            effectTracker8.RangeStart = 22
            effectTracker8.RangeEnd = 24
            
            effectTracker1.drawNow()
            effectTracker2.drawNow()
            effectTracker3.drawNow()
            effectTracker4.drawNow()
            effectTracker5.drawNow()
            effectTracker6.drawNow()
            effectTracker7.drawNow()
            effectTracker8.drawNow()
            
            primeNeopixelLED.show()
        else:
            print ("parent_conn_animationFileRead: Had unknown data in it!")
    print ("animationFileSet ended")  

def genarateFFTfile(mediaPath):
    FFTconfig = ConfigParser.RawConfigParser(allow_no_value=True)
    
    config_filename = mediaPath + ".cfg"
    cache_filename = mediaPath + ".fft"
    force_header = False
    
    if any([ax for ax in [".mp4", ".m4a", ".m4b"] if ax in mediaPath]):
        force_header = True

    music_file = decoder.open(mediaPath, force_header)
    
    sample_rate = music_file.getframerate()
    num_channels = music_file.getnchannels()

    fft_calc = fft.FFT(chunk_size,
                            sample_rate,
                            gpio_len,
                            min_frequency,
                            max_frequency,
                            custom_channel_mapping,
                            custom_channel_frequencies)

    chunks_per_sec = ((16 * num_channels * sample_rate) / 8) / chunk_size

    # Output a bit about what we're about to Process
    audio_length = str(music_file.getnframes() / sample_rate)
    print ("Processing: " + mediaPath + " (" + audio_length + " sec)")
    
    # create empty array for the cache_matrix
    cache_matrix = np.empty(shape=[0,gpio_len]) #"gpio_len" is cm.hardware.gpio_len here, I think thats the chaneals
    cache_found = False
    
    matrix_buffer = deque([], 1000)

    # Process audio mediaPath
    row = 0
    data = music_file.readframes(chunk_size)

    total_frames = music_file.getnframes()
    
    print ("Generating FFT file")
    while data != '':
        # Compute FFT in this chunk, and cache results
        matrix = fft_calc.calculate_levels(data)

        # Add the matrix to the end of the cache
        cache_matrix = np.vstack([cache_matrix, matrix])
        data = music_file.readframes(chunk_size)
    data = ''
    cache_found = False
    play_now = False
    print "\nSaving sync file"
    
    #Save matrix, std, and mean to cache_filename for use during future playback
    # Compute the standard deviation and mean values for the cache
    mean = np.empty(gpio_len, dtype='float32')
    std = np.empty(gpio_len, dtype='float32')

    for pin in range(0, gpio_len):
            std[pin] = np.std([item for item in cache_matrix[:, pin] if item > 0])
            mean[pin] = np.mean([item for item in cache_matrix[:, pin] if item > 0])
            
    # Add mean and std to the top of the cache
    cache_matrix = np.vstack([mean, cache_matrix])
    cache_matrix = np.vstack([std, cache_matrix])

    # Save the cache using numpy savetxt
    np.savetxt(cache_filename, cache_matrix)

    # Save fft config
    #Inside fft_calc.save_config()

    if FFTconfig.has_section("fft"):
        FFTconfig.remove_section("fft")

    FFTconfig.add_section("fft")
    FFTconfig.set('fft', '# DO NOT EDIT THIS SECTION')
    FFTconfig.set('fft', '# EDITING THIS SECTION WILL CAUSE YOUR FFT FILE TO BE INVALID')
    FFTconfig.set('fft', 'chunk_size', str(chunk_size))
    FFTconfig.set('fft', 'sample_rate', str(sample_rate))
    FFTconfig.set('fft', 'total_frames', str(total_frames))
    FFTconfig.set('fft', 'audio_length', str(audio_length))
    FFTconfig.set('fft', 'chunks_per_sec', str(chunks_per_sec))
    FFTconfig.set('fft', 'gpio_len', str(gpio_len))
    FFTconfig.set('fft', 'min_frequency', str(min_frequency))
    FFTconfig.set('fft', 'max_frequency', str(max_frequency))

    if isinstance(custom_channel_mapping, list):
        FFTconfig.set('fft', 'custom_channel_mapping', str(custom_channel_mapping)[1:-1])
    else:
        FFTconfig.set('fft', 'custom_channel_mapping', str(custom_channel_mapping))

    if isinstance(custom_channel_frequencies, list):
        FFTconfig.set('fft', 'custom_channel_frequencies', str(custom_channel_frequencies)[1:-1])
    else:
        FFTconfig.set('fft', 'custom_channel_frequencies', str(custom_channel_frequencies))

    FFTconfig.set('fft', 'num_channels', str(num_channels))

    with open(config_filename, "w") as f:
        FFTconfig.write(f)


    cm_len = str(len(cache_matrix))
    print ("Cached sync data written to '." + cache_filename + "' [" + cm_len + " rows]")
    #print ("Cached FFTconfig data written to '." + fft_calc.config_filename)
    cache_matrix = None

#Actions when buttions are pressed
def onOffBedsidebutton(channel):
    print ("channel pressed ="+str(channel))
    global keepgoing
    keepgoing = False
    global lightsOn
    global lastButtonPressed
    global modeselect
    if GPIO.input(channel)== True:#This is to try and filter out falce positives, It assumes the input is pullup
        print ("Ignored!")
        return
    if lastButtonPressed == "onOff":
        lightsOn = not lightsOn #Toggles lightsOn
    lastButtonPressed = "onOff"
    modeselect["DeviceInControl"] = False

def modeBedsidebutton(channel):
    print ("channel pressed ="+str(channel))
    global keepgoing
    keepgoing = False
    global lastButtonPressed
    global modeselect
    global lightsOn
    if GPIO.input(channel)== True:#This is to try and filter out falce positives, It assumes the input is pullup
        print ("Ignored!")
        return
    if lastButtonPressed == "mode":

        LightingModes.NextMode()#New mode traker
        
        if (modeselect['modeselect'] == "Birthday"):
            if Birthday == "party":
                pass
            else:
                print (str(Birthday)+" Birthday did not match any of the ifs! (in modeBedsidebutton)")
        elif (modeselect['modeselect'] == "Daytime"):
            if modeselect['Daytime'] == "off":
                modeselect['Daytime'] = "lighting"
            elif modeselect['Daytime'] == "lighting":
                modeselect['Daytime'] = "off"
            else:
                print (str(modeselect['Daytime'])+" modeselect['Daytime'] did not match any of the ifs! (in modeBedsidebutton)")
        elif (modeselect['modeselect'] == "Evening" or modeselect['Evening'] == "device"):########REFINE THIS
            if modeselect['Evening'] == "sunset":
                modeselect['Evening'] = "off"
            elif modeselect['Evening'] == "off":
                modeselect['Evening'] = "sunset"
            elif modeselect['Evening'] == "sunset":
                if modeselect["DeviceActive"] == True and modeselect["DeviceInControl"] == False:
                    modeselect['Evening'] = "device"
                    modeselect["DeviceInControl"] = True
                else:
                    modeselect['modeselect'] = "Evening"
                
                         
            else:
                print (str(modeselect['Evening'])+" modeselect['Evening'] did not match any of the ifs! (in modeBedsidebutton)")
        elif (modeselect['modeselect'] == "Nighttime"):
            if modeselect['Nighttime'] == "off":
                modeselect['Nighttime'] = "night"
            elif modeselect['Nighttime'] == "clock":
                modeselect['Nighttime'] = "off"
            elif modeselect['Nighttime'] == "night":
                modeselect['Nighttime'] = "clock"
            else:
                print (str(modeselect['Nighttime'])+" Nighttime did not match any of the ifs! (in modeBedsidebutton)")
        else:
            print (str(modeselect['modeselect'])+" modeselect['modeselect'] did not match any of the ifs! (in modeBedsidebutton)")
        
    lastButtonPressed = "mode"
    modeselect["DeviceInControl"] = False

def modeMatbutton(channel):
    global keepgoing
    global lastButtonPressed #Possible modes - mode, onOff, mat
    global matpresstime
    global lastButtonBeforeMatPress

    print ("channel pressed ="+str(channel))
    if GPIO.input(channel)== False:#This is to try and filter out falce positives, It assumes the input is pulldown
        print ("Ignored!")
        return
    
    keepgoing = False
    
    
    matpresstime = time.time()#Updates the time
    
    if lastButtonPressed != "mat": lastButtonBeforeMatPress = lastButtonPressed
    
    lastButtonPressed = "mat" ########### FIX THIS ITS NOT APPLYING!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

#gets the time and splits it into three variables
def getTheTime(): 
    #today = str(datetime.date.today())
    localtime = str(datetime.datetime.now().time())
    currentHour = int(localtime[:2])
    currentMinute = int(localtime[3:5])
    currentSecond = int(localtime[6:8])
    return currentHour, currentMinute, currentSecond

def NetworkReceiveData(conn):
    data = None
    data = conn.recv(4096)#SR2
    recvAttempt = 1
    #We don't know if we have all the data from just one try
    while (data.decode("ascii"))[-2:] != "\r\n":#Looking for EOL, Keep receiving until we find it.
        data = data+conn.recv(4096)
        if recvAttempt >= 5:#We will only try 5 times.
            print ("Failed to get all data after "+str(recvAttempt)+" Trys.")
            print ("Data Receved - "+str(data))
            recvAttempt = 1
            break
        recvAttempt = recvAttempt + 1
    data = data.decode("ascii")#Convert from Binary to ascii
    print ("Data Receved: "+data)
    return data

def NetworkSendData(conn,data):
    conn.sendall(data+b'\r\n')
    
#Function for handling connections. This will be used to create threads
def ClientConnectionThread(conn,connaddress):
    global LEDsecR
    global LEDsecG
    global LEDsecB
    global LEDTerW
    global LEDQuatW
    global LEDQuinW
    global effectTracker1
    global effectTracker2
    global effectTracker3
    global effectTracker4
    global effectTracker5
    global effectTracker6
    global effectTracker7
    global effectTracker8
    global effectTracker8
    global effectTracker9
    global modeselect
    global parent_conn_animationFileRead
    
    #Get the true time and work out offset
    #Commented out time update, The is fine for testing
    #The Pi OS does a NTP sync at boot anyway.
##    try:
##        print ("Server Getting Network time")
##        c = ntplib.NTPClient()
##        timeServerResponse = c.request('uk.pool.ntp.org', version=3)
##        print ("timeServerResponse.tx_time= "+str(timeServerResponse.tx_time))
##        timeCorrection = timeServerResponse.offset
##        print ("timeCorrection= "+str(timeCorrection))
##        ServerState["ServerTimeSyncAccuracy"] = timeServerResponse.root_delay
##        print ("ServerTimeSyncAccuracy= "+str(ServerState["ServerTimeSyncAccuracy"]))
##    except:
##        print ("TIME SERVER FAILED")
##        ServerTimeSyncAccuracy = 1000
##        timeCorrection = 0
    ServerState["ServerTimeSyncAccuracy"] = 0
    timeCorrection = 0
    
    #Sending current status to connected client
    NetworkSendData(conn,b'[STAT]'+ json.dumps(ServerState)) #SS1
    
    while True: #Looped so the client issue more than one command.
        print ("while True in ClientConnectionThread tick")
        
        #Receiving data from client
        data = NetworkReceiveData(conn)
        #Check data is formed properly, can assume EOL is there
        if data[:6] == "[COMM]":
            ClientCommand = json.loads(data[6:])
            if ClientCommand["StartFilePlayTime"] >= (time.time() + timeCorrection)+3:
                if os.path.exists("MusicAnimationFiles/"+ClientCommand["FilePlaying"]+".roomani"):
                    #timingFile = open("MusicAnimationFiles/"+ClientCommand["FilePlaying"]+".roomani", "r")
                    print ("ClientConnectionThread Found "+ (ClientCommand["FilePlaying"]+".roomani"))
                    #We fould the file, read it in to serverstate and ACKN
                    ServerState["StartFilePlayTime"] = ClientCommand["StartFilePlayTime"]
                    ServerState["FilePlaying"] = ClientCommand["FilePlaying"]
                    ServerState["FilePlayingExtension"] = ClientCommand["FilePlayingExtension"]
                    ServerState[".roomaniFilePresent"] = True
                    modeselect["DeviceInControl"] = True
                    modeselect["DeviceActive"] = True
                    
                    #Start a Process to read and change the Vars in a timmed way
                    parent_conn_animationFileRead, child_conn_animationFileRead = multiprocessing.Pipe()
                    p = multiprocessing.Process(target=animationFileRead, args=(child_conn_animationFileRead,ServerState,))
                    p.start()
                    
                    #Start a thread to set the LEDs based on what animationFileRead reads
                    setAniFileCommands = threading.Thread(target=animationFileSet,)
                    setAniFileCommands.start()

                    data = b"[ACKN]Playback Thread Started"
                elif os.path.exists("MusicAnimationFiles/"+ClientCommand["FilePlaying"]+ClientCommand["FilePlayingExtension"]+".fft"):
                    print ("Found .fft FFT file")
                    data = b"[ACKN]Playback Thread Started of FFT file"
                    ServerState["StartFilePlayTime"] = ClientCommand["StartFilePlayTime"]
                    ServerState["FilePlaying"] = ClientCommand["FilePlaying"]
                    ServerState["FilePlayingExtension"] = ClientCommand["FilePlayingExtension"]
                    ServerState[".roomaniFilePresent"] = False
                    #Start a Process to read and change the Vars in a timmed way
                    parent_conn_animationFileRead, child_conn_animationFileRead = multiprocessing.Pipe()
                    p = multiprocessing.Process(target=animationFileRead, args=(child_conn_animationFileRead,ServerState,))
                    p.start()
                    
                    #Start a thread to set the LEDs based on what animationFileRead reads
                    setAniFileCommands = threading.Thread(target=animationFileSet,)
                    setAniFileCommands.start()
                    
                    ServerState[".roomaniFilePresent"] = False
                    modeselect["DeviceInControl"] = True
                    modeselect["DeviceActive"] = True
                elif os.path.exists("MusicAnimationFiles/"+ClientCommand["FilePlaying"]+ClientCommand["FilePlayingExtension"]):
                    data = b"[NACK]Wait. Need to genarate FFT file!"
                    NetworkSendData(conn,data)
                    genarateFFTfile("MusicAnimationFiles/"+ClientCommand["FilePlaying"]+ClientCommand["FilePlayingExtension"])
                    data = None
                    data = b"[ACKN]Done. Resubmit request!"
                    NetworkSendData(conn,data)
                else:
                    print ("ClientConnectionThread is unable to locate " + (ServerState["FilePlaying"]))
                    data = b"[NACK]No Animation or Media files found on the Server!"
                    print ("Server Sent back: "+str(data))
            else:
                data = b"[NACK]That start time is too close or in the past! Requested start time: "+str(ClientCommand["StartFilePlayTime"])+" Current time on Server: "+str(time.time())
                print ("Server Sent back: "+str(data))
        elif data[:6] == "[PULL]":
            print ("Client Requeted data, This is not working yet")
            data = b"[NACK]Client Requeted data, This is not working yet"
        elif data[:6] == "[PUSH]":
            data = b"[ACNK]Ready to receave Data File"
        else:
            print ("Start of data lacked an instruction type")
            data = b"[NACK]Start of data lacked an instruction type"
        
        #Send back ACK or Data
        NetworkSendData(conn,data)
    #came out of loop
    print ("Disconnecting from "+connaddress)
    conn.close()
    print ("Session to "+connaddress+" closed cleanly")
    modeselect["DeviceInControl"] = False
    modeselect["DeviceActive"] = False

def serverthread(s):
    global serverthread_loop
    #now keep talking with the client
    serverthread_loop = True
    while serverthread_loop == True:
        #wait to accept a connection - blocking call
        conn, addr = s.accept()
        connaddress = addr[0] + ':' + str(addr[1])
        print ('Connected with ' + connaddress)
        #start new thread takes 1st argument as a function name to be run, second is the tuple of arguments to the function.
        t = threading.Thread(target=ClientConnectionThread, args=(conn,connaddress))
        t.start()
    s.close()
    
def signal_handler(signal, frame):
    global serverthread_loop
    global loop
    print ("Ctrl+C Detected")
    serverthread_loop = False
    loop = False
    keepgoing = False

def safe_div(x,y):
    if y==0: return 0
    return x/y
    
    
    
    
if __name__ == '__main__':
    
    #Config Management
    config = ConfigParser.RawConfigParser(allow_no_value=True)
    filepresent = False
    ConfigReadAttempts = 0

    while filepresent == False and ConfigReadAttempts < 3:
        ConfigReadAttempts += 1
        RoomLightingConfigPath = "RoomLightingConfig.cfg"
        filepresent = os.path.isfile(RoomLightingConfigPath)
        if filepresent == True:
            with open(RoomLightingConfigPath) as f:
                config.readfp(f)
                lastButtonPressed = config.get('Startup_State', 'lastButtonPressed')
                
                longitude = config.getfloat('Location', 'longitude')
                latitude = config.getfloat('Location', 'latitude')
                
                modeselect = {
                "modeselect":config.get('modeselect', 'modeselect'),
                "Daytime":config.get('modeselect', 'Daytime'),
                "Evening":config.get('modeselect', 'Evening'),
                "Nighttime":config.get('modeselect', 'Nighttime'),
                "Birthday":config.get('modeselect', 'Birthday'),
                "DeviceInControl":config.getboolean('modeselect', 'DeviceInControl'),
                "DeviceActive":config.getboolean('modeselect', 'DeviceActive'),
                }
                
                lightsOn = config.getboolean('lightsOn', 'lightsOn')
                
                enableTemperatureLogging = config.getboolean('TemperatureLogging', 'enableTemperatureLogging')
                tempSystem_ID = config.get('TemperatureLogging', 'tempSystem_ID')
                tempInside1_ID = config.get('TemperatureLogging', 'tempInside1_ID')
                tempOutsideSunshine_ID = config.get('TemperatureLogging', 'tempOutsideSunshine_ID')
                tempOutside1_ID = config.get('TemperatureLogging', 'tempOutside1_ID')
                
                server_enabled = config.getboolean('Networking', 'server_enabled')
                SVR_HOST = config.get('Networking', 'SVR_HOST')
                SVR_PORT = config.getint('Networking', 'SVR_PORT')
                
                power3_3vPresent_GPIO = config.getint('GPIO','power3_3vPresent_GPIO')
                onOffBedsidebutton_GPIO = config.getint('GPIO','onOffBedsidebutton_GPIO')
                modeBedsidebutton_GPIO = config.getint('GPIO','modeBedsidebutton_GPIO')
                onOffDoorbutton_GPIO = config.getint('GPIO','onOffDoorbutton_GPIO')
                modeDoorbutton_GPIO = config.getint('GPIO','modeDoorbutton_GPIO')
                matButton_GPIO = config.getint('GPIO','matButton_GPIO')
                
                externalPWMfrequency = config.getint('PCA9685', 'externalPWMfrequency')
                
                LED_COUNT = config.getint('Neopixel', 'LED_COUNT')
                LED_PIN = config.getint('Neopixel', 'LED_PIN')
                LED_FREQ_HZ = config.getint('Neopixel', 'LED_FREQ_HZ')
                LED_DMA = config.getint('Neopixel', 'LED_DMA')
                LED_BRIGHTNESS = config.getint('Neopixel', 'LED_BRIGHTNESS')
                LED_INVERT = config.getboolean('Neopixel', 'LED_INVERT')
                
                chunk_size = config.getint('FFT_Auto_Settings', 'chunk_size')
                gpio_len = config.getint('FFT_Auto_Settings', 'gpio_len')
                min_frequency = config.getfloat('FFT_Auto_Settings', 'min_frequency')
                max_frequency = config.getfloat('FFT_Auto_Settings', 'max_frequency')
                custom_channel_mapping = config.getint('FFT_Auto_Settings', 'custom_channel_mapping')
                custom_channel_frequencies = config.getint('FFT_Auto_Settings', 'custom_channel_frequencies')
                
                
        else: #If there is no config file, make one....
            print ("Can't find Config file "+RoomLightingConfigPath+"!\nCreating one filled with defaults...")
            try:
                config.add_section("Startup_State")
                config.set('Startup_State', 'lastButtonPressed', str("onOff")) #Possible States - mode, onOff, mat
                
                config.add_section("Location")
                config.set('Location', 'longitude', str("51.0"))#Changed for public release
                config.set('Location', 'latitude', str("-0.3"))#Changed for public release
                """
                longitude = 51.000000 #Changed for public release
                latitude = -0.000000 #Changed for public release
                """
                
                config.add_section("modeselect")
                config.set('modeselect', 'modeselect', str("Daytime"))#Possible modes - Birthday, Daytime, Evening, Nighttime, DeviceInControl
                config.set('modeselect', 'Daytime', str("off"))#Possible modes - party
                config.set('modeselect', 'Evening', str("sunset"))#Possible modes - off, sunset
                config.set('modeselect', 'Nighttime', str("night"))#Possible modes - off, clock, night
                config.set('modeselect', 'Birthday', str("party"))
                config.set('modeselect', 'DeviceInControl', str("false"))
                config.set('modeselect', 'DeviceActive', str("false"))
                """
                modeselect = {
                      "modeselect":"Daytime",#Possible modes - Birthday, Daytime, Evening, Nighttime, DeviceInControl
                      "Daytime":"off", #Possible modes - party
                      "Evening":"sunset",#Possible modes - off, sunset
                      "Nighttime":"night",#Possible modes - off, clock, night
                      "Birthday":"party",
                      "DeviceInControl":False,
                      "DeviceActive":False
                      }
                """
                
                config.add_section("lightsOn")
                config.set('lightsOn', 'lightsOn', str("False"))
                """
                lightsOn = False
                """
                config.add_section("TemperatureLogging")
                config.set('TemperatureLogging', 'enableTemperatureLogging', str(True))
                config.set('TemperatureLogging', 'tempSystem_ID', str("28-0416a42e03ff"))
                config.set('TemperatureLogging', 'tempInside1_ID', str("28-0416a4b211ff"))
                config.set('TemperatureLogging', 'tempOutsideSunshine_ID', str("28-0416a49b3eff"))
                config.set('TemperatureLogging', 'tempOutside1_ID', str("28-0516a42148ff"))
                """
                enableTemperatureLogging = True
                tempSystem_ID = "28-0416a42e03ff"
                tempInside1_ID = "28-0416a4b211ff"
                tempOutsideSunshine_ID = "28-0416a49b3eff"
                tempOutside1_ID = "28-0516a42148ff"
                """
                
                config.add_section("Networking")
                config.set('Networking', 'server_enabled', str("True"))
                config.set('Networking', 'SVR_HOST', str(""))
                config.set('Networking', 'SVR_PORT', str("8888"))
                """
                server_enabled = False
                SVR_HOST = ''   # Symbolic name meaning all available interfaces
                SVR_PORT = 8888
                """
                
                config.add_section("GPIO")
                config.set('GPIO', 'power3_3vPresent_GPIO', str("27"))
                config.set('GPIO', 'onOffBedsidebutton_GPIO', str("14"))
                config.set('GPIO', 'modeBedsidebutton_GPIO', str("23"))
                config.set('GPIO', 'onOffDoorbutton_GPIO', str("22"))
                config.set('GPIO', 'modeDoorbutton_GPIO', str("24"))
                config.set('GPIO', 'matButton_GPIO', str("17"))
                """
                power3_3vPresent_GPIO = 27
                onOffBedsidebutton_GPIO = 14
                modeBedsidebutton_GPIO = 23
                onOffDoorbutton_GPIO = 22
                modeDoorbutton_GPIO = 24
                matButton_GPIO = 17
                """
                
                config.add_section("PCA9685")
                config.set('PCA9685', 'externalPWMfrequency', str("1000"))
                
                config.add_section("Neopixel")
                config.set('Neopixel', 'LED_COUNT', str("60"))
                config.set('Neopixel', 'LED_PIN', str("18"))
                config.set('Neopixel', 'LED_FREQ_HZ', str("800000"))
                config.set('Neopixel', 'LED_DMA', str("10"))
                config.set('Neopixel', 'LED_BRIGHTNESS', str("255"))
                config.set('Neopixel', 'LED_INVERT', str("False"))
                """
                #Primary Neopixel LED strip configuration:
                LED_COUNT      = 447      # Number of LED pixels.
                LED_PIN        = 18      # GPIO pin connected to the pixels (must support PWM!).
                LED_FREQ_HZ    = 800000  # LED signal frequency in hertz (usually 800khz)
                LED_DMA        = 10     # DMA channel to use for generating signal (try 5) (5 WILL CORRUPT THE SD CARD!!! Use 10!!)
                LED_BRIGHTNESS = 255     # Set to 0 for darkest and 255 for brightest
                LED_INVERT     = False   # True to invert the signal (when using NPN transistor level shift)
                """
                
                config.add_section("FFT_Auto_Settings")
                config.set('FFT_Auto_Settings', 'chunk_size', str(2048))
                config.set('FFT_Auto_Settings', 'gpio_len', str(8))
                config.set('FFT_Auto_Settings', 'min_frequency', str(20.0))
                config.set('FFT_Auto_Settings', 'max_frequency', str(15000.0))
                config.set('FFT_Auto_Settings', 'custom_channel_mapping', str(0))
                config.set('FFT_Auto_Settings', 'custom_channel_frequencies', str(0))
                
                with open(RoomLightingConfigPath, "w") as f:
                    config.write(f)
                
            except:
                print ("Can't Create file! Check file permissions!")
           
        

    
    coords = {'longitude' : longitude, 'latitude' : latitude }
    
    #Setup Voltage Presence Detector
    GPIO.setup(power3_3vPresent_GPIO, GPIO.IN)

    #Setup LEDs

    #Initialise addon PWM board - This was added to avoid pi pwm flickering issues
    #I2C bus uses GPIO 2 & GPIO 3
    try: 
        # Initialise the PCA9685 using the default address (0x40).
        externalPWM = Adafruit_PCA9685.PCA9685()
        # Alternatively specify a different address and/or bus:
        #externalPWM = Adafruit_PCA9685.PCA9685(address=0x41, busnum=2)

        # Set frequency
        externalPWM.set_pwm_freq(externalPWMfrequency)

        #Pulse length out of 4095
        externalPWM.set_pwm(0,0,0)#(PIN,start PWN at, end PWM at)
        ##  These  are used to define targeted values that the defs then work to using their methods
        PCA9685Present = True
    except Exception as e:
        print(e)
        print("Failed to find PCA9685 on the I2C bus!")
        if GPIO.input(power3_3vPresent_GPIO)==False: print ("Probably because there is no voltage on 3.3V Line") 
        print("Functions that use PCA9685 will not run!")
        PCA9685Present = False

    LEDsecR = LEDinterface(4,"LEDsecR")#Pass PCA9685Channel
    LEDsecG = LEDinterface(5,"LEDsecG")
    LEDsecB = LEDinterface(3,"LEDsecB")
    LEDTerW = LEDinterface(0,"LEDTerW")
    LEDQuatW = LEDinterface(1,"LEDQuatW")
    LEDQuinW = LEDinterface(2,"LEDQuinW")

    """ Now using config file
    #Primary Neopixel LED strip configuration:
    LED_COUNT      = 447      # Number of LED pixels.
    LED_PIN        = 18      # GPIO pin connected to the pixels (must support PWM!).
    LED_FREQ_HZ    = 800000  # LED signal frequency in hertz (usually 800khz)
    LED_DMA        = 10     # DMA channel to use for generating signal (try 5) (5 WILL CORRUPT THE SD CARD!!! Use 10!!)
    LED_BRIGHTNESS = 255     # Set to 0 for darkest and 255 for brightest
    LED_INVERT     = False   # True to invert the signal (when using NPN transistor level shift)
    """

    # Create Primary NeoPixel object with appropriate configuration.
    if neopixelPresent == True:
        primeNeopixelLED = Adafruit_NeoPixel(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS)
    else:
        primeNeopixelLED = Adafruit_NeoPixelDUMMY()

    # Intialize the library (must be called once before other functions).
    primeNeopixelLED.begin()

    #Setup Buttons an Inputs
    #On/Off Bedside button
    GPIO.setup(onOffBedsidebutton_GPIO, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.add_event_detect(onOffBedsidebutton_GPIO, GPIO.FALLING, callback=onOffBedsidebutton, bouncetime=500)

    #Mode Bedside Button
    GPIO.setup(modeBedsidebutton_GPIO, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.add_event_detect(modeBedsidebutton_GPIO, GPIO.FALLING, callback=modeBedsidebutton, bouncetime=500)


    #On/Off Door button
    GPIO.setup(onOffDoorbutton_GPIO, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.add_event_detect(onOffDoorbutton_GPIO, GPIO.FALLING, callback=onOffBedsidebutton, bouncetime=400)

    #Mode Door Button
    GPIO.setup(modeDoorbutton_GPIO, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.add_event_detect(modeDoorbutton_GPIO, GPIO.FALLING, callback=modeBedsidebutton, bouncetime=400)

    #Mode Mat Button
    GPIO.setup(matButton_GPIO, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.add_event_detect(matButton_GPIO, GPIO.RISING, callback=modeMatbutton, bouncetime=500) #needs a 1k Pulldown not 10k

    #Setup Thermometers - 1W Bus has to be on GPIO4! - Use "ls /sys/bus/w1/devices" in terminal to get IDs
    tempSensors = getTempSensorList()

    #Setup Server if enabled
    if server_enabled == True:
        #Start Server to receave remote commands
        
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print ('Socket created')

        #Bind socket to local host and port
        try:
            s.bind((SVR_HOST, SVR_PORT))
            
        except():
            print ('Bind failed')
             
        print ('Socket bind complete')

        #Start listening on socket
        s.listen(10)
        print ('Socket now listening')

        #Start Server
        st = threading.Thread(target=serverthread, args=(s,))
        st.start()

    #Setup Mode Tracker objects
    LightingModes = modeStateTracker()
    LightingModes.addmode("Daytime")
    LightingModes.addmode("Evening")
    LightingModes.addmode("Nighttime")
    LightingModes.addmode("Birthday")

    SubDaytimeLightingModes = modeStateTracker()
    SubDaytimeLightingModes.addmode("LightsOn")
    SubDaytimeLightingModes.addmode("Clock")
    SubDaytimeLightingModes.addmode("LightsOff")

    SubDaytimeLightingModes = modeStateTracker()
    SubDaytimeLightingModes.addmode("LightsOn")
    SubDaytimeLightingModes.addmode("Clock")
    SubDaytimeLightingModes.addmode("LightsOff")

    #Start NeoPixel Effect Trackers
    effectTracker1 = NeoPixelEffectTracker(primeNeopixelLED)
    effectTracker2 = NeoPixelEffectTracker(primeNeopixelLED)
    effectTracker3 = NeoPixelEffectTracker(primeNeopixelLED)
    effectTracker4 = NeoPixelEffectTracker(primeNeopixelLED)
    effectTracker5 = NeoPixelEffectTracker(primeNeopixelLED)
    effectTracker6 = NeoPixelEffectTracker(primeNeopixelLED)
    effectTracker7 = NeoPixelEffectTracker(primeNeopixelLED)
    effectTracker8 = NeoPixelEffectTracker(primeNeopixelLED)
    effectTracker9 = NeoPixelEffectTracker(primeNeopixelLED)
    
    
    signal.signal(signal.SIGINT, signal_handler) #Catch Ctrl+C
    loop = True
    
    while loop == True:
        #print ("while _main_ tick")
        starttime = time.time() #Needed to calculate some of the timed fade effects
        
        actionLogic() #THIS IS THE MAIN CODE TO ACT ON HOW THE VARABLES HAVE BEEN SET
        
        LEDsecR.writeValtoexternalPWM()
        LEDsecG.writeValtoexternalPWM()
        LEDsecB.writeValtoexternalPWM()
        LEDTerW.writeValtoexternalPWM()
        LEDQuatW.writeValtoexternalPWM()
        LEDQuinW.writeValtoexternalPWM()

        #effectTracker1.drawNow()
        #effectTracker2.drawNow()
        #effectTracker3.drawNow()
        #effectTracker4.drawNow()
        #effectTracker5.drawNow()
        #effectTracker6.drawNow()
        #effectTracker7.drawNow()
        #effectTracker8.drawNow()

        #Added for test
        #effectTrackerRainbow.drawNow()
        
        #primeNeopixelLED.show()
        
        time.sleep(0.01)#sleeping for a milisec to save CPU cycles and allow other threads to run
        endtime = time.time()
        timeToLoop = endtime - starttime
    #Exit
    GPIO.cleanup()
    print ('Exiting\nThreads may take time to loop out.')
