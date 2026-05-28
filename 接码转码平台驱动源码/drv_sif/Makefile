
ifeq ($(CONFIG_FORZA_SIF_EN),y)
	SIF_PATH=$(srctree)/emodules/drv_sif/sif_fz
else ifeq ($(CONFIG_YADI_SIF_EN),y)
	SIF_PATH=$(srctree)/emodules/drv_sif/sif_yd
else ifeq ($(CONFIG_YADI_V01_SIF_EN),y)
	SIF_PATH=$(srctree)/emodules/drv_sif/sif_yd_v01
else ifeq ($(CONFIG_TAILING_SIF_EN),y)
	SIF_PATH=$(srctree)/emodules/drv_sif/sif_tl
else ifeq ($(CONFIG_LIMA_SIF_EN),y)
	SIF_PATH=$(srctree)/emodules/drv_sif/sif_lm
else ifeq ($(CONFIG_ANXIAN_SIF_EN),y)
	SIF_PATH=$(srctree)/emodules/drv_sif/sif_ax
else ifeq ($(CONFIG_JINGHUI_SIF_EN),y)
	SIF_PATH=$(srctree)/emodules/drv_sif/sif_jh
else ifeq ($(CONFIG_HUAWEI_SIF_EN),y)
	SIF_PATH=$(srctree)/emodules/drv_sif/sif_hw
else ifeq ($(CONFIG_XINSIWEI_SIF_EN),y)
	SIF_PATH=$(srctree)/emodules/drv_sif/sif_xsw
else ifeq ($(CONFIG_AIMA_SIF_EN),y)
	SIF_PATH=$(srctree)/emodules/drv_sif/sif_am
else ifeq ($(CONFIG_JINGXIAN_SIF_EN),y)
	SIF_PATH=$(srctree)/emodules/drv_sif/sif_jx
else ifeq ($(CONFIG_RUILUN_SIF_EN),y)
	SIF_PATH=$(srctree)/emodules/drv_sif/sif_rl
else ifeq ($(CONFIG_TAIBANG_SIF_EN),y)
	SIF_PATH=$(srctree)/emodules/drv_sif/sif_tb
else ifeq ($(CONFIG_YOUYIBAO_SIF_EN),y)
	SIF_PATH=$(srctree)/emodules/drv_sif/sif_yyb
else ifeq ($(CONFIG_TAIXIANG_SIF_EN),y)
	SIF_PATH=$(srctree)/emodules/drv_sif/sif_tx
else ifeq ($(CONFIG_FZY21_SIF_EN),y)
	SIF_PATH=$(srctree)/emodules/drv_sif/sif_y21
else ifeq ($(CONFIG_XINRI_SIF_EN),y)
	SIF_PATH=$(srctree)/emodules/drv_sif/sif_xr	
else ifeq ($(CONFIG_WUXIYIGE_SIF_EN),y)
	SIF_PATH=$(srctree)/emodules/drv_sif/sif_tjyg
else
	SIF_PATH=$(srctree)/emodules/drv_sif/sif_fz
endif

subdir-ccflags-y +=			-I$(srctree)/include/melis/kernel \
				-I$(srctree)/include/melis/libs/libc \
				-I$(srctree)/include/melis/board   \
				-I$(srctree)/include/melis/module  \
				-I$(srctree)/include/melis/kernel/drivers \
				-I${SIF_PATH}  \
				-I$(srctree)/emodules/drv_sif/sif_bms \
				-I$(srctree)/emodules/drv_sif \
				-I$(srctree)/ekernel/drivers/include/hal \
				-I$(srctree)/ekernel/drivers/include/drv \
				-I$(srctree)/ekernel/core/rt-thread/include						
					
usrlibs-y +=			--start-group \
				-lsyscall  -lminic  -lpub0  -ldrv\
				--end-group

MOD_NAME := sif
SUF_NAME := drv
PRJ_PATH := $(srctree)/projects/${TARGET_BOARD}/data/UDISK/drv/
TEMP_PATH := $(srctree)/emodules/bin

ifeq ($(CONFIG_FORZA_SIF_EN),y)
	$(MOD_NAME)-objs += sif_fz/sif.o
else ifeq ($(CONFIG_YADI_SIF_EN),y)
	$(MOD_NAME)-objs += sif_yd/sif.o
else ifeq ($(CONFIG_YADI_V01_SIF_EN),y)
	$(MOD_NAME)-objs += sif_yd_v01/sif.o
else ifeq ($(CONFIG_TAILING_SIF_EN),y)
	$(MOD_NAME)-objs += sif_tl/sif.o
else ifeq ($(CONFIG_LIMA_SIF_EN),y)
	$(MOD_NAME)-objs += sif_lm/sif.o
else ifeq ($(CONFIG_ANXIAN_SIF_EN),y)
	$(MOD_NAME)-objs += sif_ax/sif.o
else ifeq ($(CONFIG_JINGHUI_SIF_EN),y)
	$(MOD_NAME)-objs += sif_jh/sif.o
else ifeq ($(CONFIG_HUAWEI_SIF_EN),y)
	$(MOD_NAME)-objs += sif_hw/sif.o
else ifeq ($(CONFIG_XINSIWEI_SIF_EN),y)
	$(MOD_NAME)-objs += sif_xsw/sif.o
else ifeq ($(CONFIG_AIMA_SIF_EN),y)
	$(MOD_NAME)-objs += sif_am/sif.o
else ifeq ($(CONFIG_JINGXIAN_SIF_EN),y)
	$(MOD_NAME)-objs += sif_jx/sif.o
else ifeq ($(CONFIG_RUILUN_SIF_EN),y)
	$(MOD_NAME)-objs += sif_rl/sif.o
else ifeq ($(CONFIG_TAIBANG_SIF_EN),y)
	$(MOD_NAME)-objs += sif_tb/sif.o
else ifeq ($(CONFIG_YOUYIBAO_SIF_EN),y)
	$(MOD_NAME)-objs += sif_yyb/sif.o
else ifeq ($(CONFIG_TAIXIANG_SIF_EN),y)
	$(MOD_NAME)-objs += sif_tx/sif.o
else ifeq ($(CONFIG_FZY21_SIF_EN),y)
	$(MOD_NAME)-objs += sif_y21/sif.o
else ifeq ($(CONFIG_XINRI_SIF_EN),y)
	$(MOD_NAME)-objs += sif_xr/sif.o
else ifeq ($(CONFIG_WUXIYIGE_SIF_EN),y)
	$(MOD_NAME)-objs += sif_tjyg/sif.o
else
	$(MOD_NAME)-objs += sif_fz/sif.o
endif

ifeq ($(CONFIG_SIF_BMS_EN),y)
	$(MOD_NAME)-objs += sif_bms/sif_bms.o
endif
	
$(MOD_NAME)-objs += dev_sif.o
$(MOD_NAME)-objs += drv_sif.o
$(MOD_NAME)-objs += magic.o

include $(MELIS_BASE)/scripts/Makefile.mods


