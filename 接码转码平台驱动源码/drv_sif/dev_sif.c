/*
*********************************************************************************************************
*											        ePDK
*						            the Easy Portable/Player Develop Kits
*									           ir key driver
*
*						        (c) Copyright 2006-2007, Steven.ZGJ China
*											All	Rights Reserved
*
* File    : dev_sif.c
* By      : Steven.ZGJ
* Version : V1.00
*********************************************************************************************************
*/

#include "sif.h"
#include "drv_sif_i.h"

extern __sif_drv_t sif_drv;
/*
**********************************************************************************************************************
*                                               FUNCTION
*
* Description:
*
* Arguments  :
*
* Returns    :
*
* Notes      :
*
**********************************************************************************************************************
*/
static void SIF_OpLock(void)
{
    __u8  err;

    esKRNL_SemPend(sif_drv.sem1, 0, &err);
}
/*
**********************************************************************************************************************
*                                               FUNCTION
*
* Description:
*
* Arguments  :
*
* Returns    :
*
* Notes      :
*
**********************************************************************************************************************
*/
static void SIF_OpUnlock(void)
{
    esKRNL_SemPost(sif_drv.sem1);
}
/*
****************************************************************************************************
*
*             DEV_SIF_Open
*
*  Description:
*       DEV_SIF_Open
*
*  Parameters:
*
*  Return value:
*       EPDK_OK
*       EPDK_FAIL
****************************************************************************************************
*/
__hdle DEV_SIF_Open(void * open_arg, __u32 mode)
{
	__s32        cpu_sr;
	__sif_dev_t *pDev = (__sif_dev_t *) & (sif_drv.sif_dev);

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
/*
****************************************************************************************************
*
*             DEV_SIF_Close
*
*  Description:
*       DEV_SIF_Close
*
*  Parameters:
*
*  Return value:
*       EPDK_OK
*       EPDK_FAIL
****************************************************************************************************
*/
__s32 DEV_SIF_Close(__hdle hfm)
{
	__s32        cpu_sr;
	__sif_dev_t *pDev = (__sif_dev_t *) & (sif_drv.sif_dev);
	
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
/*
****************************************************************************************************
*
*             DEV_SIF_Read
*
*  Description:
*       DEV_SIF_Read
*
*  Parameters:
*
*  Return value:
*       size*n
*
****************************************************************************************************
*/
__u32 DEV_SIF_Read(void *pdata, __u32 size, __u32 n, __hdle hPower)
{
    return EPDK_OK;
}
/*
****************************************************************************************************
*
*             DEV_SIF_Write
*
*  Description:
*       DEV_SIF_Write
*
*  Parameters:
*
*  Return value:
*       size*n
*
****************************************************************************************************
*/
__u32 DEV_SIF_Write(const void *pdata, __u32 size, __u32 n, __hdle hPower)
{
    return EPDK_OK;
}
/*
****************************************************************************************************
*
*             DEV_SIF_Ioctrl
*
*  Description:
*       DEV_SIF_Ioctrl
*
*  Parameters:
*
*  Return value:
*       EPDK_OK
*       EPDK_FAIL
****************************************************************************************************
*/
__s32 DEV_SIF_Ioctrl(__hdle hDev, __u32 cmd, __s32 aux, void *pbuffer)
{
    __s32	ret;
	__sif_dev_t *pDev = (__sif_dev_t *)hDev;

	ret = EPDK_FAIL;

    SIF_OpLock();

    switch(cmd)
    {
        case DRV_SIF_CMD_INIT:
        {
            ret = EPDK_OK;
            break;
        }
        case DRV_SIF_CMD_EXIT:
        {
            ret = EPDK_OK;
            break;
        }
		case DRV_SIF_CMD_SET_CB:
		{
			sif_set_drv_cb(pbuffer, (void*)aux);
			ret = EPDK_OK;
			break;
		}
		case DRV_SIF_CMD_SET_SPEED_OFFSET:
		{
			sif_drv.speed_offset = aux;
			//eLIBs_printf("------ sif_drv.speed_offset = %d ------\n",sif_drv.speed_offset);
			break;
		}
		case DRV_SIF_CMD_START_STOP:
		{
			if(!aux)
			{
				sif_drv.start_flag = 0;
			}
			else
			{
				sif_drv.start_flag = 1;
			}
			ret = EPDK_OK;
			break;
		}
		case DRV_SIF_CMD_SET_SPEED_LIMIT:
		{
			if(!aux)
			{
				sif_drv.speed_limit_flag = 0;
			}
			else
			{
				sif_drv.speed_limit_flag = 1;
			}
			//eLIBs_printf("------ sif_drv.speed_limit_flag = %d ------\n",sif_drv.speed_limit_flag);
			ret = EPDK_OK;
			break;
		}
		case DRV_SIF_CMD_SEND_DATA:
		{
		#ifdef CONFIG_FORZA_SIF_TOOL_EN
			eLIBs_memset(sif_drv.sif_data_from_uart,0,sizeof(sif_drv.sif_data_from_uart));
			//if(aux == REV_DATA_NUM)
			{
				{
					__u8 i = 0;

					eLIBs_printf("sif recv data from uart(len = %d) : ",aux);
					for(;i<aux;i++)
					{
						sif_drv.sif_data_from_uart[i] = *((__u8 *)pbuffer+i);
						eLIBs_printf("%02x ",sif_drv.sif_data_from_uart[i]);
					}
					eLIBs_printf("\n");
				}
				sif_drv.sif_data_from_uart_num = aux;
				sif_drv.sif_recv_data_flag = 1;
			}
			//else
			{
				//eLIBs_printf("sif data from uart len is not %d , please check again !!!\n",REV_DATA_NUM);
			}
		#endif
			ret = EPDK_OK;
			break;
		}
    	default:
		{
			__wrn("Unkonwn Command...\n");
			break;
		}
	}

	SIF_OpUnlock();

	return ret;
}

__dev_devop_t sif_dev_ops =
{
    DEV_SIF_Open,
    DEV_SIF_Close,
    DEV_SIF_Read,
    DEV_SIF_Write,
    DEV_SIF_Ioctrl
};

