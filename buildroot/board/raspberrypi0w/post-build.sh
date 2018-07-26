#!/bin/sh

set -u
set -e

BOARD_DIR="$(dirname $0)"

# Update inittab
cp ${BOARD_DIR}/inittab ${TARGET_DIR}/etc/inittab

# Add SD card automount
cp ${BOARD_DIR}/11-sd-cards-auto-mount.rules ${TARGET_DIR}/etc/udev/rules.d/

# Copy over camera script and data
cp ${BOARD_DIR}/../../../cv_cam.py ${TARGET_DIR}/etc/
cp ${BOARD_DIR}/../../../remap.pkl ${TARGET_DIR}/etc/

# Pre-compile camera script
python3 -m compileall ${TARGET_DIR}/etc/cv_cam.py

# Add boot script for busybox
cp ${BOARD_DIR}/S00camera ${TARGET_DIR}/etc/init.d/
chmod +x ${TARGET_DIR}/etc/init.d/S00camera
