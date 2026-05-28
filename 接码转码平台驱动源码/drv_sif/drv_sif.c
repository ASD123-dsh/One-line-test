/*
*********************************************************************************************************
*											        ePDK
*						            the Easy Portable/Player Develop Kits
*									           hello world sample
*
*						        (c) Copyright 2006-2007, Steven.ZGJ China
*											All	Rights Reserved
*
* File    : drv_sif.c
* By      : 
* Version : V1.00
*********************************************************************************************************
*/
#include "sif.h"
#include "drv_sif_i.h"

__sif_drv_t	sif_drv;

/*
****************************************************************************************************
*
*             DRV_SIF_MInit
*
*  Description:
*       DRV_SIF_MInit
*
*  Parameters:
*
*  Return value:
*       EPDK_OK
*       EPDK_FAIL
****************************************************************************************************
*/

__s32 DRV_SIF_MInit(void)
{	
	eLIBs_memset((void*)&sif_drv, 0, sizeof(sif_drv));
	sif_drv.used = 0;
	sif_init();
	return EPDK_OK;
}
/*
****************************************************************************************************
*
*             DRV_SIF_MExit
*
*  Description:
*       DRV_SIF_MExit
*
*  Parameters:
*
*  Return value:
*       EPDK_OK
*       EPDK_FAIL
****************************************************************************************************
*/
__s32 DRV_SIF_MExit(void)
{
	sif_drv.used = 0;
	sif_exit();
	return EPDK_OK;
}
/*
****************************************************************************************************
*
*             DRV_SIF_MOpen
*
*  Description:
*       DRV_SIF_MOpen
*
*  Parameters:
*
*  Return value:
*       EPDK_OK
*       EPDK_FAIL
****************************************************************************************************
*/
__mp *DRV_SIF_MOpen(__u32 mid, __u32 mod)
{
	__s32 cpu_sr;

	ENTER_CRITICAL(cpu_sr);
	if (1 == sif_drv.used)
	{
		__msg("sif used by someone else\n");
		EXIT_CRITICAL(cpu_sr);
		return (__mp *)0;
	}
	EXIT_CRITICAL(cpu_sr);

	sif_drv.mid = mid;

	return (__mp *)&sif_drv;
}
/*
****************************************************************************************************
*
*             DRV_SIF_MClose
*
*  Description:
*       DRV_SIF_MClose
*
*  Parameters:
*
*  Return value:
*       EPDK_OK
*       EPDK_FAIL
****************************************************************************************************
*/
__s32 DRV_SIF_MClose(__mp *mp)
{
	__s32 cpu_sr;

	ENTER_CRITICAL(cpu_sr);
	if (0 == sif_drv.used)
	{
		EXIT_CRITICAL(cpu_sr);
		return EPDK_FAIL;
	}
	sif_drv.used = 0;
	EXIT_CRITICAL(cpu_sr);

	return EPDK_OK;
}
/*
****************************************************************************************************
*
*             DRV_SIF_MRead
*
*  Description:
*       DRV_SIF_MRead
*
*  Parameters:
*
*  Return value:
*       size*n
*
****************************************************************************************************
*/
__u32 DRV_SIF_MRead(void *pdata, __u32 size, __u32 n, __mp *mp)
{
	return 0;
}
/*
****************************************************************************************************
*
*             DRV_SIF_MWrite
*
*  Description:
*       DRV_SIF_MWrite
*
*  Parameters:
*
*  Return value:
*       size*n
*
****************************************************************************************************
*/
__u32 DRV_SIF_MWrite(const void *pdata, __u32 size, __u32 n, __mp *mp)
{
	return 0;
}
/*
****************************************************************************************************
*
*             DRV_SIF_MIoctrl
*
*  Description:
*       DRV_SIF_MIoctrl
*
*  Parameters:
*
*  Return value:
*       EPDK_OK
*       EPDK_FAIL
****************************************************************************************************
*/
__s32 DRV_SIF_MIoctrl(__mp *mp, __u32 cmd, __s32 aux, void *pbuffer)
{
	switch(cmd)
	{
		case DRV_CMD_PLUGIN:
		{
			if(sif_drv.used)
			{
				__wrn("sif already used\n");
				return EPDK_FAIL;
			}
						
			sif_drv.hReg = esDEV_DevReg("USER", "SIF", &sif_dev_ops, 0);
			if(!sif_drv.hReg)
			{
				__wrn("user sif registered Error!\n");
				return EPDK_FAIL;
			}
			sif_drv.used = 1;
			//eLIBs_printf("SIF plugin successed , DRV VER=%s\n", DRV_SIF_VER_STR);
			return EPDK_OK;
		}
		case DRV_CMD_PLUGOUT:
		{
			if(sif_drv.used == 1)
			{
				if(!sif_drv.hReg)
				{
					__wrn("Dev not plugin!\n");
					return EPDK_FAIL;
				}
				esDEV_DevUnreg(sif_drv.hReg);
			}
			sif_drv.used = 0;
			return EPDK_OK;
		}
		case DRV_CMD_GET_STATUS:
		{
			if(sif_drv.used)
			{
				return DRV_STA_BUSY;
			}
			else
			{
				return DRV_STA_FREE;
			}
		}
		default:
		    return EPDK_FAIL;
	}
}

