#############################Load packages#########################
import cv2 #video and camera
import time #interation with time interval
import cognitive_face as CF #FaceAPI
import pydocumentdb.document_client as document_client #CosmosDB
from flask import Flask, redirect, Response, request, abort, render_template,render_template_string, send_from_directory
import base64 #encoding images before POST to gesture API
import requests #POST gesture API
import json #load respons from gesture API
from emoji.unicode_codes import UNICODE_EMOJI


#############################Initiation###########################
#Path to local storage
PATH="./static/photos/"
#Path to Intel haarcascade database
CascPath = "./static/haarcascade_frontalface_default.xml"

#face cognitive key
KEY='0b5d0258448344b18570768922e147d8'
BASE_URL='https://westeurope.api.cognitive.microsoft.com/face/v1.0'
CF.Key.set(KEY)
CF.BaseUrl.set(BASE_URL)

#gesturePAI
service_uri = "http://104.42.51.210/api/v1/service/emoji-handssvc/score"
auth_key = "jCl6LXwOOs2PCSLQmwo38tcVjZi2WDj2"
image_path = 'C:/Users/mzhang/Pictures/Camera Roll/thumbup.jpg'
headers = {'Content-Type': 'application/json', 'Authorization' : 'Bearer ' + auth_key}

#Initiate a Null model for one shop
shopNr=3
aShop="shop"+str(shopNr)
cameraNr=999
aCam="camera"+str(cameraNr)
#############################Functions###########################



#Capture video from camera, save each frame as jpeg
def GetFrame(vidcap,frameNr):
    success,image = vidcap.read() #initiate video capture
    cv2.imwrite(PATH+"stream/frame%d.jpg" % frameNr, image)     # save frame as JPEG file
    print('Read a new frame: ', success, frameNr)
    return success,image

#Detect if there is one or more faces in the frame or not, if yes, save the frames
def MultiFaceDetect(image,frameNr):
    # Create the haar cascade
    faceCascade = cv2.CascadeClassifier(CascPath)
    #set image to gray
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # Detect faces in the image as a rectagler (vertex,vertex,width, height)
    faces = faceCascade.detectMultiScale(
        gray,
        scaleFactor = 1.1,
        minNeighbors = 5,
        minSize = (30,30) #Define image quality
        )
    #Save the frame if there is at least one face larger than minSize
    if len(faces)>0:
        cv2.imwrite(PATH+"withface/frame%d.jpg" % frameNr, image) # save frame as JPEG file
    print("Found {0} faces!".format(len(faces)))
    return faces

#Get each area in the image where a face is located, Return the largest face
def GetDomFace(image,faces,frameNr):
    x, y, w, h = 0, 0, 0, 0
    if len(faces)==1:
        (x, y, w, h) =faces[0]
    else:
        for i in range(len(faces)-1):
            if faces[i][2]+faces[i][3]<=faces[i+1][2]+faces[i+1][3]:
                (x, y, w, h) =faces[i+1]
    #        # Draw a rectangle around the faces
    #        cv2.rectangle(image, (x, y), (x+w, y+h), (0, 255, 0), 2)
    #        cv2.imshow("image", image)
    #        cv2.waitKey(5000)
    #        cv2.destroyAllWindows()
    #Crop faces out of the image
    crop_image = image[y:y+h, x:x+w]
    cv2.imwrite(PATH+"faces/face"+str(frameNr)+".jpg", crop_image)     # save each face as a JPEG file
    return PATH+"faces/face"+str(frameNr)+".jpg"

#Verify whether the face is in the consented personal database
def VerifyFace():
    vidcap = cv2.VideoCapture(cv2.CAP_DSHOW+1) #+1 use the other camera than default camera
    frameNr = 0
    success = True
    while success and frameNr<5:
        success,image=GetFrame(vidcap,frameNr)#Get a frame from camera, valid image caputred= True
        if success==False:
            print("camera erorr, no video captured")
        else: 
            faces=MultiFaceDetect(image,frameNr)#Detect the regions in the image where faces are detected
            if len(faces)>0: 
                faceImagePath=GetDomFace(image,faces,frameNr)#Get the image of the largest face in the frame
                aFace = CF.face.detect(faceImagePath,attributes='emotion')#Call FaceAPI, return faceID and emotion
                #If a face is detected, look up in consented personID database
                if aFace!=[]:
                    faceID=aFace[0]['faceId']
                    identifyResult=CF.face.identify([faceID], aShop)#Lookup face in consented personID database
                    #If at least one personID candidate found with defined confidence,return personID and emotion 
                    if identifyResult[0]['candidates']!=[]: 
                        print("candidates found: ",identifyResult[0]['candidates'])
                        maxconfi=identifyResult[0]['candidates'][0]['confidence']
                        max_idx=0
                        for j in range(len(identifyResult[0]['candidates'])):
                            if identifyResult[0]['candidates'][j]['confidence']>maxconfi:
                                maxconfi=identifyResult[0]['candidates'][j]['confidence']
                                max_idx=j
                        print("max confidence:", maxconfi)
                        if maxconfi>=0.65:#Define confidence level of person re-identification
                            personID=identifyResult[0]['candidates'][max_idx]['personId']
                            emotionReply=aFace[0]['faceAttributes']['emotion']
                            emotionmax=max(emotionReply, key=emotionReply.get)
                            oldKey=list(emotionReply.keys())
                            newKey=['annoyed', 'curious','annoyed','surprised','happy','tired','sad','surprised'] 
                            for i in range(len(newKey)):
                                print(emotionmax,oldKey[i],newKey[i],emotionmax==oldKey[i])
                                if emotionmax==oldKey[i]:
                                    emotion=newKey[i]
                            print("reidentified"+personID+"confidently",emotion)
                            return personID,emotion

                    #If no personID candidate found with defined confidence,return [],[] (Attention! [] is different from None) 
                    else:
                        print("Person not registered or face not regonized")
                        return [],[]

                #If the object detected by haarcascada is not a face,frame capture continues with defined time interval
                else:
                    frameNr += 1
                    time.sleep(0.5)
                    print("It's not a face")

            #If no face in the frame, frame capture continues with defined time interval
            else:
                frameNr += 1
                time.sleep(2)
                print("No face captured")



#Get the hand gesture
def GetGesture():
    image_base64 = None
    vidcap = cv2.VideoCapture(cv2.CAP_DSHOW+1) #+1 use the other camera than default camera
    frameNr = 0
    success = True
    while success and frameNr<5:
        success,image=GetFrame(vidcap,frameNr)#Get a frame from camera, valid image caputred= True
        if success:
            cv2.imwrite(PATH+"gest/gest"+str(frameNr)+".jpg", image)#Save frame as a JPEG file
            #Send saved frame to gesture API
            image_path=PATH+"gest/gest"+str(frameNr)+".jpg"
            with open(image_path, "rb", ) as image_file:
                image_base64 = base64.encodebytes(image_file.read())
                image_json = json.dumps({ 'data' : str(image_base64, 'utf8') })
                resp = requests.post(service_uri, headers=headers, data=image_json)
                emoji=json.loads(resp.json())['emoji']
                #If a hand gesture recognized, return had gesture as str
                if emoji!=[]:
                    frameNr=99
                    return UNICODE_EMOJI[emoji[0]].replace(":","").replace("_"," ")
                #If no hand detected, continue capture frames 
                else:
                    frameNr+=1


#############################Flask APP###########################
                    
                    
                    
app = Flask(__name__)
@app.route('/')# if HTML contains forms, use GET and Post 
def welcome():
    personID,emotion =VerifyFace()
    #pref=GetPurchasePref(personID)
    return render_template('QSurveyWelcome.html',emotion=emotion)

@app.route('/q18',methods=['GET','POST'])
def q18():
    reply=GetGesture()
    print(reply)
    if reply=='thumbs up'or reply=='raised fist' or reply=='oncoming fist':
        return render_template('Q18plusGesture.html', reply='thumbs up')
    else:
        return render_template('QuitGesture.html', reply=reply)
    
@app.route('/qmember',methods=['GET','POST'])
def qmember():
    reply=GetGesture()
    print(reply)
    if reply=='thumbs up'or reply=='raised fist' or reply=='oncoming fist':
        return render_template('QMemberGesture.html', reply='thumbs up')
    else:
        return render_template('QuitGesture.html', reply=reply)

@app.route('/amember',methods=['GET','POST'])
def amember():
    reply=GetGesture()
    print(reply)
    if reply=='thumbs up'or reply=='raised fist' or reply=='oncoming fist':
        return render_template('AMemberGesture.html', reply='thumbs up')
    else:
        return render_template('QuitGesture.html', reply=reply)

if __name__ == '__main__':
  app.run(host="127.0.0.1", debug=True)
