# Super 70

A digital Polaroid SX-70 rebuilt using a Raspberry Pi Zero W and 2.8" LCD display.

**Current boot time:** ~5 seconds

### Requirements
* buildroot

### Python Libraries
* OpenCV 3
* Pillow
* Pygame
* Numpy
* RPi GPIO

### Notes
* `buildroot` directory contains configuration files for buildroot, including the `defconfig`, `post-build`, and `post-image` scripts used to generate the image.
* `package/kmod/kmod.mk` is a modified `kmod` makefile that fixes an issue with Python 3 in the current buildroot version. Lines `43-45` (`KMOD_CONF_ENV`) are added to fix the compilation issue with Python 3.
* `remap.pkl` is the pickled output from the fisheye de-distortion calibration; a new calibration file can be generated using the `fisheye` scripts.

### Loading with buildroot
```sh
make BR2_EXTERNAL=/path/to/super70/buildroot BR2_DEFCONFIG=/path/to/super70/buildroot/configs/raspberrypi0w_defconfig defconfig
```
