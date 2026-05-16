import os
import cv2			# camera access and using the video
import time			# used for sleeping
import logging 			# data for the console
import multiprocessing as mp	# runs the camera on serparate process to be effiecent
import queue			# keep data safe and in order
import threading 		# run multiple task so that they don't lag another
import servo 			# this is everything needed for the servo
from log import CoordLog	# Stores the data
import model			# model used for drone detection
from flask import Flask, jsonify, request, Response, render_template	# Flask make the web app,
                                                                        # jsonify uses Json to send data,
                                                                        # request reads data from the web server
                                                                        # response gives custom responses
# CONSTANTS
JPEG_QUALITY = 70		# jpeg quality can be turned up if needed
FRAME_WIDTH = 640		# width of frame
FRAME_HEIGHT = 480		# height of frame
THRESHOLD_TRACKING = 100		# this is the +/- threshold increase to make less finiky
PRECISION_RUN = 50      # runs the servo this long in tracking
PRECISION_STOP = 60     # how long the servo will stop in tracking
AMOUNT_SKIPPED = 2       # When it find a drone sometimes doesn't detect it for a frame we want to avoid that

#GLOBAL VARIABLES
servo_state = "Stopped"		# Saves the state of the servo and starts at stopped state
x = -1				# Coord of drone and -1 means none found
y = -1				# Coord of drone and -1 means none found
arriving_jpg = None		# The camera jpeg (image) that just came 
# in start at None since camera must be setup
current_jpg_lock = threading.Lock()	# Locks the image so that it can only change one at a time 
servo_lock = threading.Lock()		# So only one request at a time will be processed
tracking_lock = threading.Lock()	# lock for tracking

current_queue = None			# This is the queue for images to be sent

tracking = False			    # this is for tracking option
precision = 0                   # slows the amount of turn the tracking does

skip_frames  = 0                # this is used to count how many frames we skip in tracking

#LOGGER
def init_log():
    """
    Start up a coordinate logger
    """
    global coord_log

    coord_log = CoordLog(reset_seconds=86400, max_entries=20000) 	# sets it for 24 hours worth of seconds
                                                                    # max amount of data that can be recorded

# WEB SERVER
def init_web_server():
    """
    Create the Web server app. 
    This will be __name__ the python file which is this one.
    The static: CSS, Java Script, and PNG.
    The template folders is for the HTML template files
    """
    global web_server
    web_server = Flask(__name__, static_folder="static", template_folder="templates")

# SERVO
def init_servo():
    """
    This is setting up the servo so we can use it. it's special because try incase we don't have it attached
    """

    try:
        servo.init_servo()
        print("servo connected")
    except Exception as e: 	# normal error and store that error in e
        print(f"servo not initiated, {e}\n")
# CAMERA
def open_camera():
    """
    try to set up the camera for use on cv2
    """

    pipeline = (
    "rtspsrc location=rtsp://192.168.1.173:8554/cam protocols=tcp latency=0 ! "
    "rtph264depay ! h264parse ! nvv4l2decoder ! nvvidconv ! "
    "video/x-raw, format=BGRx ! videoconvert ! "
    "appsink drop=true sync=false max-buffers=1"
    )

    usb_cam = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)                                                    # and make the object called usb_cam

    if (usb_cam.isOpened()): # tries to open to check if it is truely found
        print(" Camera connected")
        return usb_cam
    else:
        print("failed to open camera") # failed to open camera
        return None

def camera_process(current_queue):
    """
    This is a camera thread that will add the images in the correct format into the queue
    """

    # set up the camera object to get the right frames
    cv2.setNumThreads(1)	# Only have one thread for OpenCV
    video = open_camera()	# video holds the camera object
    if video is None:	# the open_camera failed
        print("failed to open_camera" )
        return

    # video.set(cv2.CAP_PROP_BUFFERSIZE, 2) 	# set the buffer field to value 2 so it has very small buffer
    # video.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)	# This is the width of the frame (image)
    # video.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)	# This is the height of the frame (image)

    while True:
        ok, frame = video.read() # grab a frame for the camera, and checks if this frame is okay
        if not ok:
            print("failed frame")
            time.sleep(0.01)	# give time to get a new frame
            continue
        try:
            modeled_frame, cx, cy = model.stream(frame)	# insert frame get modeled frame back
                                    # get the center x from the model
                                    # get the center y from teh model
        except Exception:
            modeled_frame = frame				#By pass the model since no drone seen
            cx, cy = -1, -1

        # We must now compress the frame to send to the web server
        ok, compressed_frame = cv2.imencode(".jpg"				, modeled_frame,
                        [int(cv2.IMWRITE_JPEG_QUALITY)	, JPEG_QUALITY])
        if not ok:
            print(" Compression failed")	# compressing frame failed
            continue

        # now we turen the compressed_frame into raw_bytes
        raw_frame = compressed_frame.tobytes()

        # Time to send the frames to the queue
        try:
            current_queue.put_nowait((raw_frame, cx, cy)) # add to queue

        except Exception:	# failed to add meaning it is full queue
            try:
                current_queue.get_nowait()	#removes the oldest item from the queue
            except Exception:
                pass				#the queue emptied by the time it took to get here

            try:
                current_queue.put_nowait((raw_frame, cx, cy))	# add to queue
            except Exception:
                pass 				# Failed again

def pull_from_queue():
    """
    This function will update the arriving jpg from the queue
    """

    global arriving_jpg, x, y
    while True:
        try:
            jpg, cx, cy = current_queue.get(timeout=0.5) 	# Get image from the queue 
                                    # and timeout looking at 0.5 seconds
        except queue.Empty:
            continue					# queue is empty go back up
        except Exception:
            continue					# queue failed


        with current_jpg_lock:	# get the lock before the block and release the lock when the block ends
            arriving_jpg = jpg	# update the coming in jpeg
            x, y = cx, cy		# update the coming in x and y

        coord_log.update(cx, cy)	# update the current x and y in the logs

def uploading_frames():
    while True:
        with current_jpg_lock:	# get the lock before the block and release the lock when the block ends
            jpg = arriving_jpg	# get the arriving jpg

        if jpg is None:
            time.sleep(0.01)	# wait so maybe a arriving jpg can come
            continue		# go back up to the start of the while

        yield ( b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n")	# you give the frame
        # sending bytes header called frame
        # sending bytes of the content type for the server to know what it is
        # the + jpg + is the raw_frame bytes
        # finally just ending the chunk to be sent
        # This is all HTTP style formating

        time.sleep(0.01)	# give time to add a new arrival frame

# TRACKING OPTION
def do_tracking():
    """
    This is a tracking function that you get to change the threshold if it is to much finiky.
    """
    global servo_state, precision, skip_frames

    with current_jpg_lock:				# load the x and y
        current_x = x
        current_y = y

    if ((current_x == -1 or current_y == -1) and skip_frames == 0):	#their is no drone found and drone hasn't been found within AMOUNT_SKIPPED
        if precision <= PRECISION_RUN:
            with tracking_lock:
                servo_state_different = (servo_state != "Right")	# are the servo state different?
                servo_state = "Right"
                precision += 1
            if servo_state_different:					# move it the correct direction if it is
                with servo_lock:
                    servo.cw()
        else:
            with tracking_lock:
                servo_state_different = (servo_state != "Stopped")	# are the servo state different?
                if precision <= PRECISION_STOP:
                    precision += 1
                else:
                    precision = 0
                servo_state = "Stopped"
            if servo_state_different:					# move it the correct direction if it is
                with servo_lock:
                    servo.stop()
        return

    # drone was found going to track it now
    elif (current_x == -1 or current_y == -1):    # this is used for a skip frame moment
        pass
    else:
        error_x = current_x - (FRAME_WIDTH/2)		# This is the error from the center of the camera
        if ( (THRESHOLD_TRACKING) >= abs(error_x)):	# the error is less or equal to the threshold so stop
            with tracking_lock:
                servo_state_different = (servo_state != "Stopped")	# are the servo state different?
                servo_state = "Stopped"
            if servo_state_different:					# move it the correct direction if 										# it is
                with servo_lock:
                    servo.stop()
        elif ( error_x < 0 ):				# error less than x turn left or ccw
            with tracking_lock:
                servo_state_different = (servo_state != "Left")	# are the servo state different?
                servo_state = "Left"
            if servo_state_different:					# move it the correct direction if 										# it is
                with servo_lock:
                    servo.ccw()
        else:						# the error is more so turn right or cw
            with tracking_lock:
                servo_state_different = (servo_state != "Right")	# are the servo state different?
                servo_state = "Right"
            if servo_state_different:					# move it the correct direction if 										# it is
                with servo_lock:
                    servo.cw()
                
        print(f"drone center:{error_x}, servo state:{servo_state}, servo state different:{servo_state_different}")
    with tracking_lock:
        skip_frames += 1
        if skip_frames > AMOUNT_SKIPPED:
            skip_frames = 0
    return

def tracking_threading():
    """
    This is will be a thread that loops the tracking funciton
    """
    while True:
        with tracking_lock:
            current_tracking = tracking

        if current_tracking:		# asking is tracking true?
            do_tracking()
        time.sleep(0.01)		# give time between each track


# FLASK ROUTES

init_web_server()	# make the web server before the routes

# the next part is web routes for the url
# the following @ are if someone does this on the url it will do the following functions below

@web_server.get("/") # root or main site
def home():
    return render_template("web_html.html") # this is the root or main site and loads the html

@web_server.get("/video_feed") # video feed of the web_server
def video_feed():	# gives the live video
    return Response(uploading_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")

@web_server.get("/value")
def value():
    with tracking_lock:
        return jsonify(servo_state=servo_state, tracking=tracking)	# gives the current servo state 
                                        # and if it is tracking as JSON

@web_server.get("/coords")
def coords():
    with current_jpg_lock:
        return jsonify(x=x, y=y) # give the latest coordinates as JSON

@web_server.get("/angle")
def angle_route():
    try:
        return jsonify(angle=servo.angle())	# send angle as JSON	
    except Exception:
        return jsonify(angle=None)		# failed to get angle send None	as JSON	

@web_server.get("/log.json")
def log_json():
    # give the coordinates history as JSON
    return jsonify( window_start=coord_log.get_window_start(),
            entries=coord_log.get_entries() )


@web_server.post("/log/reset")
def log_reset():			# reset the log
    coord_log.clear()		# clear the log history
    return jsonify(ok=True)		# confirm that it was reseted
                            
@web_server.post("/change")
def change_route():
    global servo_state, tracking

    data = request.get_json(silent=True) or {}	# request for the data
    direction = (data.get("direction") or "Stopped").strip() 	# remove spaces and check 
                                    # direction if no direction stop
    with tracking_lock:
        tracking = False		

        if direction == servo_state:
            return jsonify(servo_state=servo_state, changed=False)  # state is the same as direction 
                                    # keep doing same thing
        # if they are direction and servo_state are different
        servo_state = direction
    
    with servo_lock:	# stops from more than one request at a time
        if direction == "Left":
            servo.ccw()
        elif direction == "Right" :
            servo.cw()
        else:
            servo.stop()
    
    return jsonify(servo_state=servo_state, changed=True)	# returning that it has changed

@web_server.post("/tracking")
def tracking_route():
    global tracking, servo_state
    
    data = request.get_json(silent=True) or {}	# get data
    enabled = data.get("enabled", False)		# read the data to set enabled

    if not isinstance(enabled, bool):		# is it true or false
        enabled = False
        
    with tracking_lock:		
        tracking = enabled			# set tracking to enabled
        if not enabled:
            servo_state = "Stopped"	
        current_state = servo_state
        current_tracking = tracking
        
    if not enabled:
        with servo_lock:
            servo.stop() 

    return jsonify(tracking=current_tracking, servo_state=current_state)
    
@web_server.get("/debug_static")
def search_static():	# searches the static folder for the files
    if os.path.isdir("static"):	# if their is a static directory
        return jsonify(files=os.listdir("static"))	#lists the files
    # else
    return jsonify(files=[], note="No static folder found")	# returns no files and makes a note of it.


# MAIN CODE
if __name__ == "__main__":	# only run this if main program is the __name__
    init_servo()	# activate servo

    init_log()	# activate log

    mp.set_start_method("spawn", force=True)	# setting up the multprocessing

    current_queue = mp.Queue(maxsize=1)	# set the queue size

    queueing_process = mp.Process( target=camera_process, args=(current_queue,), daemon=True) 
                                          # gave the thread to run the function
                                          # camera_process and pass the args in
                                          # daemon is to run in background 
                                          # no waiting for threads
    queueing_process.start()	# start the processes

    pulling_thread = threading.Thread(target=pull_from_queue, daemon=True)
    pulling_thread.start()		# start the thread

    tracking_thread = threading.Thread(target=tracking_threading, daemon=True)
    tracking_thread.start()

    # MAIN CODE STARTING THE SERVER

    print("Starting server...")
    print("Open from your pc: http://<jetson-ip>:80/")  
    web_server.run(host="0.0.0.0", port=80, debug=False, use_reloader=False,threaded=True) # start the server





































    
    
