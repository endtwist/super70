#!/bin/bash

set -e

BOARD_DIR="$(dirname $0)"
BOARD_NAME="$(basename ${BOARD_DIR})"
GENIMAGE_CFG="${BOARD_DIR}/genimage-${BOARD_NAME}.cfg"
GENIMAGE_TMP="${BUILD_DIR}/genimage.tmp"

for arg in "$@"
do
	case "${arg}" in
		--add-pi3-miniuart-bt-overlay)
		if ! grep -qE '^dtoverlay=' "${BINARIES_DIR}/rpi-firmware/config.txt"; then
			echo "Adding 'dtoverlay=pi3-miniuart-bt' to config.txt (fixes ttyAMA0 serial console)."
			cat << __EOF__ >> "${BINARIES_DIR}/rpi-firmware/config.txt"

# fixes rpi3 ttyAMA0 serial console
dtoverlay=pi3-miniuart-bt
__EOF__
		fi
		;;
		--aarch64)
		# Run a 64bits kernel (armv8)
		sed -e '/^kernel=/s,=.*,=Image,' -i "${BINARIES_DIR}/rpi-firmware/config.txt"
		if ! grep -qE '^arm_control=0x200' "${BINARIES_DIR}/rpi-firmware/config.txt"; then
			cat << __EOF__ >> "${BINARIES_DIR}/rpi-firmware/config.txt"

# enable 64bits support
arm_control=0x200
__EOF__
		fi

		# Enable uart console
		if ! grep -qE '^enable_uart=1' "${BINARIES_DIR}/rpi-firmware/config.txt"; then
			cat << __EOF__ >> "${BINARIES_DIR}/rpi-firmware/config.txt"

# enable rpi3 ttyS0 serial console
enable_uart=1
__EOF__
		fi
		;;
	esac

done

# Set GPU memory
sed -e "/^gpu_mem_256=/s,=.*,=128," -i "${BINARIES_DIR}/rpi-firmware/config.txt"

# Add settings for display
cat  << __EOF__ >> "${BINARIES_DIR}/rpi-firmware/config.txt"
dtparam=spi=on
dtparam=i2c_arm=off
dtoverlay=mzts-28
display_rotate=1
dtoverlay=mzdpi

overscan_left=0
overscan_right=0
overscan_top=0
overscan_bottom=0
framebuffer_width=640
framebuffer_height=480

enable_dpi_lcd=1
display_default_lcd=1

dpi_group=2
dpi_mode=87

dpi_output_format=0x07f003

hdmi_timings=481 0 228 88 228 640 0 2 2 4 0 0 0 60 0 32000000 3
__EOF__

# Copy other firmware files for display
cp ${BOARD_DIR}/cmdline.txt ${BINARIES_DIR}/rpi-firmware/
cp ${BOARD_DIR}/*.dtb ${BINARIES_DIR}/rpi-firmware/
cp ${BOARD_DIR}/*.dtbo ${BINARIES_DIR}/rpi-firmware/overlays/

rm -rf "${GENIMAGE_TMP}"

genimage                           \
	--rootpath "${TARGET_DIR}"     \
	--tmppath "${GENIMAGE_TMP}"    \
	--inputpath "${BINARIES_DIR}"  \
	--outputpath "${BINARIES_DIR}" \
	--config "${GENIMAGE_CFG}"

exit $?
