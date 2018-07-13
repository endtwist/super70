# Add missing build vars required to properly build kmod with python3
KMOD_CONF_ENV += \
	PYTHON_LIBS="`$(STAGING_DIR)/usr/bin/python3-config --ldflags`" \
	PYTHON_CFLAGS="`$(STAGING_DIR)/usr/bin/python3-config --cflags`"

include $(sort $(wildcard $(BR2_EXTERNAL_SUPER70_PATH)/package/*/*.mk))
