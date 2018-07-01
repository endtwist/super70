#!/bin/sh

set -u
set -e

BOARD_DIR="$(dirname $0)"

# Add a console on tty1
if [ -e ${TARGET_DIR}/etc/inittab ]; then
	sed -i 's/^.*Put a getty.*$/tty1::respawn:\/usr\/bin\/python3 \/etc\/cv_cam.py/' ${TARGET_DIR}/etc/inittab
	sed -i 's/^.*GENERIC_SERIAL$/tty1::respawn:\/sbin\/getty -L  tty1 0 vt100 # HDMI console/' ${TARGET_DIR}/etc/inittab
fi

# Add SD card automount
cp ${BOARD_DIR}/11-sd-cards-auto-mount.rules ${TARGET_DIR}/etc/udev/rules.d/
cp ${BOARD_DIR}/../../../cv_cam.py ${TARGET_DIR}/etc/
cp ${BOARD_DIR}/../../../remap.pkl ${TARGET_DIR}/etc/
