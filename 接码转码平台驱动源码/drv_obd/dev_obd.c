/*
****************************************************************************************************
*                                               MELIS
*                               the Easy Portable/Player Develop Kits
*                                           SDMMC Module
*
*                           (c) Copyright 2011-2014, All winners Co,Ld.
*                                       All Rights Reserved
*
* File    :
* By      : james.deng
* Version : 1.0.0
* Date    : 2011-12-25
* Descript:
* Update  : <date>          <author>            <version>           <notes>
*           2011-12-25      james.deng          1.0.0               build the file.
****************************************************************************************************
*/

#include "drv_obd_i.h"

static __hdle DEV_OBD_Open(void *open_arg, __u32 mode)
{
	__s32        cpu_sr;
	s_dev_obd *pDev = (s_dev_obd *) & (drv_obd.dev_obd);

	ENTER_CRITICAL(cpu_sr);
	if (1 == pDev->used)
	{
		EXIT_CRITICAL(cpu_sr);
		return (__hdle)0;
	}
	pDev->used = 1;
	EXIT_CRITICAL(cpu_sr);

	return (__hdle)pDev;
}

static __s32 DEV_OBD_Close(__hdle hDev)
{
	__s32        cpu_sr;
	s_dev_obd *pDev = (s_dev_obd *) & (drv_obd.dev_obd);;

	ENTER_CRITICAL(cpu_sr);
	if (0 == pDev->used)
	{
	EXIT_CRITICAL(cpu_sr);
	return EPDK_FAIL;
	}
	pDev->used = 0;
	EXIT_CRITICAL(cpu_sr);

	return EPDK_OK;
}

static __u32 DEV_OBD_Read(void *pBuffer, __u32 nSize, __u32 nCount, __hdle hDev)
{
	__here__;
	return EPDK_OK;
}

static __u32 DEV_OBD_Write(const void *pBuffer, __u32 nSize, __u32 nCount, __hdle hDev)
{
	__here__;
	return EPDK_OK;
}

static __s32 DEV_OBD_Ioctl(__hdle hDev, __u32 Cmd, __s32 Aux, void *pBuffer)
{
	s_dev_obd *pDev = (s_dev_obd *)hDev;
	__s32 ret = EPDK_OK;
	__msg("%s()\n", __func__);

	switch (Cmd)
	{
		case DRV_OBD_CMD_INIT:
		{
			__msg("DRV_OBD_CMD_INIT\n");
			return ret;
		}

		case DRV_OBD_CMD_EXIT:
		{
			__msg("DRV_OBD_CMD_EXIT\n");
			return ret;
		}
		case DRV_OBD_CMD_GET_OBD_INFO_PTR:
		{
			__msg("DRV_OBD_CMD_GET_OBD_INFO_PTR\n");
			ret = (__s32)&drv_obd.obd_info;
			__msg("ret=%d\n", ret);
			return ret;
		}
		case DRV_OBD_CMD_CAN_DATA_RECV:
		{
			data_recv_from_can((__u8 *)pBuffer, Aux);
			return ret;
		}
		default:
			break;
	}

	return EPDK_FAIL;
}

__dev_devop_t obd_dev_ops =
{
	DEV_OBD_Open,
	DEV_OBD_Close,
	DEV_OBD_Read,
	DEV_OBD_Write,
	DEV_OBD_Ioctl
};
