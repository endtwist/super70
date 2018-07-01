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
import logging
import numpy as np
import RPi.GPIO as GPIO
from pygame.locals import KEYDOWN
from PIL import Image, ImageDraw, ImageFont

# For capture
PHOTO_WIDTH = 3264
PHOTO_HEIGHT = 2448
PHOTO_SIZE = (PHOTO_WIDTH, PHOTO_HEIGHT)

# For on-screen preview
SCREEN_WIDTH = 640
SCREEN_HEIGHT = 480
SCREEN_SIZE = (SCREEN_WIDTH, SCREEN_HEIGHT)

# initialize the camera and grab a reference to the raw camera capture
camera = PiCamera()
camera.resolution = SCREEN_SIZE  # change this right before taking a photo
camera.framerate = 24
camera.iso = 150
camera.start_preview()
logging.debug('Preview started!')

# Pre-generated de-fisheye OpenCV remap calibration variables
pkl_file = open('remap.pkl', 'rb')
remap = pickle.load(pkl_file)
pkl_file.close()

PHOTO_PATH = '/media/sd-sda1/photos'
UID = os.getuid()
GID = os.getgid()

# Trigger (button) handler variables
TRIGGER_PIN = 25
trigger_state = 1
trigger_start_time = 0
last_trigger_time = 0

# Photocell read variables
PHOTOCELL_PIN = 18
photocell_read_start = 0
photocell_hist = []
photocell_value = 0
photocell_baseline = 0

LOG_PATH = '%s/cam.log' % PHOTO_PATH
try:
    os.remove(LOG_PATH)
except Exception:
    pass
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
file_log = logging.FileHandler(filename=LOG_PATH, mode='w')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_log.setLevel(logging.DEBUG)
file_log.setFormatter(formatter)
logging.getLogger('').addHandler(file_log)

logging.debug('Camera booting...')

# Fun trick: picamera's preview will actually render *above* pygame meaning
# we can use both at the same time pretty easily. When we want to show the
# pygame window (e.g., for post-capture review), we just stop the picamera
# preview briefly.
pygame.init()

screen = pygame.display.set_mode(SCREEN_SIZE)
pygame.mouse.set_visible(False)

# allow the camera to warm up
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


# from https://gist.github.com/bhawkins/3535131
def medfilt(x, k):
    """Apply a length-k median filter to a 1D array x.
    Boundaries are extended by repeating endpoints.
    """
    assert k % 2 == 1, "Median filter length must be odd."
    assert x.ndim == 1, "Input must be one-dimensional."
    k2 = (k - 1) // 2
    y = np.zeros((len(x), k), dtype=x.dtype)
    y[:, k2] = x
    for i in range(k2):
        j = k2 - i
        y[j:, i] = x[:-j]
        y[:j, i] = x[0]
        y[:-j, -(i+1)] = x[j:]
        y[-j:, -(i+1)] = x[-1]
    return np.median(y, axis=1)


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


def free_space(path):
    statvfs = os.statvfs(path)
    avail_mbytes = (statvfs.f_frsize * statvfs.f_bavail) / (1024 * 1024)
    if avail_mbytes < 1024:
        return '%d MB' % ()
    else:
        return '%.1f GB' % (avail_mbytes / 1024)  # return gigabytes


def capture_photo():
    global camera, PHOTO_PATH, PHOTO_SIZE

    camera.stop_preview()

    time.sleep(0.1)
    # grab last frame from videoport?
    # show 'waiting' state on pygame display

    stream = io.BytesIO()
    camera.resolution = PHOTO_SIZE
    camera.rotation = 180
    camera.capture(stream, 'jpeg')
    logging.debug('Photo captured!')

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
    scaled = cv2.transpose(scaled[..., ::-1])  # BGR to RGB
    scaled = cv2.flip(scaled, -1)  # Rotate 180 degrees
    frame = pygame.surfarray.make_surface(scaled)
    screen.blit(frame, (0, 0))
    pygame.display.update()
    time.sleep(2.5)

    # restart the preview
    camera.rotation = 0
    camera.resolution = SCREEN_SIZE
    camera.start_preview()


def draw_overlay(shutter_speed):
    global SCREEN_SIZE, SCREEN_WIDTH, SCREEN_HEIGHT, \
           DEJA_VU_SANS_MONO, PHOTO_PATH

    overlay = Image.new('RGBA', SCREEN_SIZE, (255, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # shutter_speed is microseconds, we convert to milliseconds for rendering
    shutter_speed = '%d ms' % round(shutter_speed / 1000)
    textwidth, textheight = draw.textsize(shutter_speed, DEJA_VU_SANS_MONO)
    draw.text(
        (10, SCREEN_HEIGHT - textheight - 10),
        shutter_speed,
        font=DEJA_VU_SANS_MONO,
        fill=(255, 255, 255)
    )

    disk_space = free_space(PHOTO_PATH)
    textwidth, textheight = draw.textsize(disk_space, DEJA_VU_SANS_MONO)
    draw.text(
        (SCREEN_WIDTH - textwidth - 10, SCREEN_HEIGHT - textheight - 10),
        disk_space,
        font=DEJA_VU_SANS_MONO,
        fill=(255, 255, 255)
    )

    return overlay.tobytes()


DEJA_VU_SANS_MONO = ImageFont.truetype(
    '/usr/share/fonts/dejavu/DejaVuSansMono-Bold.ttf', 24)

camera_overlay = Image.new('RGBA', SCREEN_SIZE, (255, 0, 0, 0))
draw = ImageDraw.Draw(camera_overlay)
draw.ellipse((
    (SCREEN_WIDTH / 2) - 50,
    (SCREEN_HEIGHT / 2) - 50,
    (SCREEN_WIDTH / 2) + 50,
    (SCREEN_HEIGHT / 2) + 50,
), outline=(255, 255, 255, 50))
draw.rectangle((
    0, SCREEN_HEIGHT - 60,
    SCREEN_WIDTH, SCREEN_HEIGHT
), fill=(0, 0, 0, 100))
camera_overlay = camera_overlay.tobytes()
camera_overlay_item = camera.add_overlay(
    camera_overlay,
    size=SCREEN_SIZE,
    layer=3
)

default_status_overlay = draw_overlay('±0')
status_overlay = camera.add_overlay(
    default_status_overlay,
    size=SCREEN_SIZE,
    layer=3,
    rotation=180
)
last_status_overlay = time.time()

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

# Trigger
GPIO.setup(TRIGGER_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.add_event_detect(TRIGGER_PIN, GPIO.BOTH, bouncetime=100)

# Photocell
GPIO.setup(PHOTOCELL_PIN, GPIO.OUT)
GPIO.output(PHOTOCELL_PIN, GPIO.LOW)
time.sleep(0.1)
photocell_read_start = time.time()
GPIO.setup(PHOTOCELL_PIN, GPIO.IN)
GPIO.add_event_detect(PHOTOCELL_PIN, GPIO.RISING)

try:
    # Wait indefinitely until the user terminates the script
    while True:
        screen.fill([0, 0, 0])

        pygame.display.update()

        for event in pygame.event.get():
            if event.type == KEYDOWN:
                raise KeyboardInterrupt

        if GPIO.event_detected(TRIGGER_PIN):
            now = time.time()
            new_trigger_state = GPIO.input(TRIGGER_PIN)
            if trigger_state == 1 and new_trigger_state == 0:
                # shutter button went from unpressed to pressed
                trigger_start_time = now
            elif trigger_state == 0 and new_trigger_state == 1 and \
                    now - last_trigger_time > 0.2:
                # shutter button went from pressed to unpressed (trigger time
                # detection here is used as a bit of debounce)
                logging.debug('Trigger up detected!')
                capture_photo()
                last_trigger_time = time.time()
            trigger_state = new_trigger_state

        if GPIO.event_detected(PHOTOCELL_PIN) and \
           GPIO.input(PHOTOCELL_PIN) == 1:
            # A side note here: because the pi0 is single-core single-thread,
            # we don't get the benefit of being able to run a photocell counter
            # in another thread. Instead, we just wait for the GPIO library
            # to trigger an event when the pin goes high, and then we check
            # the timing since we last set the pin low.
            GPIO.remove_event_detect(PHOTOCELL_PIN)

            # some light smoothing of the photocell reading
            photocell_reading = (time.time() - photocell_read_start) * 1000
            photocell_hist.append(photocell_reading)
            if len(photocell_hist) > 11:
                photocell_hist = photocell_hist[1:]

            if len(photocell_hist) > 5:
                photocell_hist = medfilt(np.array(photocell_hist), 5).tolist()

                # Second-to-last value in the median-filtered history
                # is the most 'stable' value we can get
                photocell_value = photocell_hist[-2]

                logging.debug('Photocell reading: %d', photocell_value)

                # The dividend here is the total timing range we see on the
                # photoresistor between darkest and lightest environments.
                light_reading = (photocell_value - 20) / (300 - 20)
                # 1/500 second -> 1.25 seconds
                shutter_speed = int(2000 + (light_reading * 1250000))
                camera.shutter_speed = shutter_speed

                # Updating the overlay too often causes memory issues with MMAL
                # —as does using the ".update" method offered by picamera's
                # PiOverlayRenderer class. So, instead, we update every ~3s by
                # removing and creating a new overlay.
                if time.time() - last_status_overlay >= 3:
                    camera.remove_overlay(status_overlay)
                    status_overlay = camera.add_overlay(
                        draw_overlay(shutter_speed),
                        size=SCREEN_SIZE,
                        layer=3,
                        rotation=180
                    )
                    last_status_overlay = time.time()

            GPIO.setup(PHOTOCELL_PIN, GPIO.OUT)
            GPIO.output(PHOTOCELL_PIN, GPIO.LOW)
            time.sleep(0.1)
            photocell_read_start = time.time()
            GPIO.setup(PHOTOCELL_PIN, GPIO.IN)
            GPIO.add_event_detect(PHOTOCELL_PIN, GPIO.RISING)

except (KeyboardInterrupt, SystemExit):
    sys.exit(0)
