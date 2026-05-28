ccflags-y +=		-I$(srctree)/include/melis/kernel \
				-I$(srctree)/include/melis/libs/libc \
				-I$(srctree)/include/melis/board   \
				-I$(srctree)/include/melis/module  \
				-I$(srctree)/include/melis/kernel/drivers \
				-I$(srctree)/ekernel/drivers/include/hal \
				-I$(srctree)/ekernel/core/rt-thread/include		\
				-I$(srctree)/emodules/drv_obd	\
				-I$(srctree)/emodules/drv_obd/obd_sk	\
				-DUSED_BY_OBD_MOD
		
usrlibs-y +=			--start-group \
				-lsyscall  -lminic  -lpub0 \
				-llzma       -lcharset     \
				--end-group

MOD_NAME := obd
SUF_NAME := drv
PRJ_PATH := $(srctree)/projects/${TARGET_BOARD}/data/UDISK/drv/
TEMP_PATH := $(srctree)/emodules/bin

$(MOD_NAME)-objs += dev_obd.o
$(MOD_NAME)-objs += drv_obd.o
$(MOD_NAME)-objs += obd_sk/obd_pro.o
$(MOD_NAME)-objs += obd_api.o
$(MOD_NAME)-objs += magic.o

include $(MELIS_BASE)/scripts/Makefile.mods



