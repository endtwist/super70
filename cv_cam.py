from picamera import PiCamera
import io
import time
import cv2
import pickle
import sys
import fnmatch
import os
import errno
import stat
import pygame
import queue
import threading
import logging
import numpy as np
import RPi.GPIO as GPIO
from pygame.locals import KEYDOWN

PHOTO_WIDTH = 3264
PHOTO_HEIGHT = 2448
PHOTO_SIZE = (PHOTO_WIDTH, PHOTO_HEIGHT)

SCREEN_WIDTH = 640
SCREEN_HEIGHT = 480
SCREEN_SIZE = (SCREEN_WIDTH, SCREEN_HEIGHT)

# initialize the camera and grab a reference to the raw camera capture
camera = PiCamera()
camera.resolution = SCREEN_SIZE  # change this right before taking a photo
camera.framerate = 24
camera.start_preview()
logging.debug('Preview started!')

pkl_file = open('remap.pkl', 'rb')
remap = pickle.load(pkl_file)
pkl_file.close()

PHOTO_PATH = '/media/sd-sda1/photos'
UID = os.getuid()
GID = os.getgid()

# Trigger (button) handler variables
TRIGGER_PIN = 25
trigger_state = 1
last_trigger_time = 0

# Photocell read variables
PHOTOCELL_PIN = 18
photocell_reading = 0
photocell_last_read = 0

LOG_PATH = '%s/cam.log' % PHOTO_PATH
try:
    os.remove(LOG_PATH)
except:
    pass
logging.basicConfig(filename=LOG_PATH, level=logging.DEBUG)

logging.debug('Camera booting...')

pygame.init()

screen = pygame.display.set_mode(SCREEN_SIZE)
pygame.mouse.set_visible(False)

# allow the camera to warmup
time.sleep(0.1)

if not os.path.isdir(PHOTO_PATH):
    try:
        os.makedirs(PHOTO_PATH)
        # Set new directory ownership to current user, mode to 755
        os.chown(PHOTO_PATH, UID, GID)
        os.chmod(PHOTO_PATH,
                 stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR |
                 stat.S_IRGRP | stat.S_IXGRP |
                 stat.S_IROTH | stat.S_IXOTH)
    except OSError as e:
        # errno = 2 if can't create folder
        print(errno.errorcode[e.errno])
        # show an error on screen


def img_range(path):
    min = 9999
    max = 0
    try:
        for file in os.listdir(path):
            if fnmatch.fnmatch(file, 'IMG_[0-9][0-9][0-9][0-9].JPG'):
                i = int(file[4:8])
                if(i < min):
                    min = i
                if(i > max):
                    max = i
    finally:
        return None if min > max else (min, max)


def capture_photo():
    global camera, PHOTO_PATH, PHOTO_SIZE

    camera.stop_preview()

    stream = io.BytesIO()
    camera.resolution = PHOTO_SIZE
    camera.rotation = 180
    camera.capture(stream, 'jpeg')
    logging.debug('Photo captured!')

    # grab last frame from videoport?
    # show 'waiting' state on pygame display

    data = np.fromstring(stream.getvalue(), dtype=np.uint8)
    image = cv2.imdecode(data, 1)
    image = cv2.remap(
       image,
       remap[PHOTO_SIZE]['map1'],
       remap[PHOTO_SIZE]['map2'],
       interpolation=cv2.INTER_LINEAR,
       borderMode=cv2.BORDER_CONSTANT
    )
    logging.debug('De-fisheyed photo')

    photo_range = img_range(PHOTO_PATH)
    if photo_range is None:
        photo_index = 1
    else:
        photo_index = photo_range[1] + 1
        if photo_index > 9999:
            photo_index = 0

    while True:
        filename = '%s/IMG_%04d.JPG' % (PHOTO_PATH, photo_index)
        if not os.path.isfile(filename):
            break
        photo_index += 1
        if photo_index > 9999:
            photo_index = 0

    cv2.imwrite(filename, image, [cv2.IMWRITE_JPEG_QUALITY, 90])
    logging.debug('Saved photo as %s' % filename)

    # show final image before restarting the preview (converts BGR to RGB)
    scaled = cv2.resize(image, SCREEN_SIZE)
    scaled = cv2.transpose(scaled[..., ::-1])
    frame = pygame.surfarray.make_surface(scaled)
    screen.blit(frame, (0, 0))
    pygame.display.update()
    time.sleep(2.5)

    # restart the preview
    camera.rotation = 0
    camera.resolution = SCREEN_SIZE
    camera.start_preview()


GPIO.setwarnings(False)  # Ignore warning for now
GPIO.setmode(GPIO.BCM)  # Use physical pin numbering

# Trigger
GPIO.setup(TRIGGER_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.add_event_detect(TRIGGER_PIN, GPIO.BOTH, bouncetime=100)

# Photocell
photocell_q = queue.Queue()


def photocell_worker():
    GPIO.setup(PHOTOCELL_PIN, GPIO.OUT)
    GPIO.output(PHOTOCELL_PIN, GPIO.LOW)
    time.sleep(0.1)
    GPIO.setup(PHOTOCELL_PIN, GPIO.IN)
    while GPIO.input(PHOTOCELL_PIN) == GPIO.LOW:
        photocell_q.put(True)
    photocell_q.put(-1)


photocell = threading.Thread(target=photocell_worker)
photocell.start()

try:
    # Wait indefinitely until the user terminates the script
    while True:
        screen.fill([0, 0, 0])

        pygame.display.update()

        for event in pygame.event.get():
            if event.type == KEYDOWN:
                raise KeyboardInterrupt

        if GPIO.event_detected(TRIGGER_PIN):
            new_trigger_state = GPIO.input(TRIGGER_PIN)
            now = time.time()
            if trigger_state == 0 and \
               new_trigger_state == 1 and \
               now - last_trigger_time > 0.2:
                logging.debug('Trigger up detected!')
                capture_photo()
                last_trigger_time = time.time()
            trigger_state = new_trigger_state

        try:
            pcv = photocell_q.get_nowait()
            if pcv:
                photocell_reading += 1
            elif pcv == -1:
                photocell_last_read = photocell_reading
                photocell_reading = 0
                logging.debug('Photocell reading: %d', photocell_last_read)
                exposure_adjust = (
                    max(200, min(1000, photocell_last_read)) - 200
                ) / 800
                camera.exposure_compensation = (exposure_adjust * 50) - 25
        except queue.Empty:
            continue
except (KeyboardInterrupt, SystemExit):
    sys.exit(0)
