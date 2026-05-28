/*
****************************************************************************************************
*                                               MELIS
*                               the Easy Portable/Player Develop Kits
*                                           SDMMC Module
*
*                           (c) Copyright 2011-2014, All winners Co,Ld.
*                                       All Rights Reserved
*
* File    : drv_obd.c
* By      : james.deng
* Version : 1.0.0
* Date    : 2011-12-24
* Descript:
* Update  : <date>          <author>            <version>           <notes>
*           2011-12-24      james.deng          1.0.0               build the file.
****************************************************************************************************
*/

#include "obd_pro.h"
#include <emodules/mod_can.h>
#include <emodules/mod_sif.h>

__s32 obd_uart_send(__u8 *buffer, __u32 size);

#ifdef CONFIG_FORZA_SIF_TOOL_EN
#define SIF_TOOL_LUYUAN_DATA_NUM		(15)	//绿源BMS一线通协议数据长度
#define SIF_TOOL_BATTERY_DATA_NUM		(6)		//电池单线通讯协议数据长度
#endif

static __u8 uart_data_get(void)
{
	__u8 val;

	val = drv_obd.uart_buf.buf[drv_obd.uart_buf.head];
	drv_obd.uart_buf.head = ((drv_obd.uart_buf.head + 1) % MAX_FIFO_LENGTH);
	__msg("drv_obd.uart_buf.head=%d\n", drv_obd.uart_buf.head);
	return val;
}

static __u16 check_uart_data_len(void)
{
	return ((drv_obd.uart_buf.tail + MAX_FIFO_LENGTH - drv_obd.uart_buf.head) % MAX_FIFO_LENGTH);
}

static void sif_msg_send_proc(__u8 *data, __s32 len)
{
	__u8 i = 0;
	__u8 sif_data[64] = {0};
	__u8 check_sum = 0;
	__s32 send_len = 0;
	static ES_FILE* h_sif_dev = NULL;

	if(h_sif_dev == NULL)
	{
		h_sif_dev = eLIBs_fopen("b:\\USER\\SIF", "r+");
		if(!h_sif_dev)
		{
			eLIBs_printf("obd open SIF driver failed!\n");
			return;
		}
	}

	eLIBs_memset(sif_data,0,sizeof(sif_data));

	for(i=0;i<len;i++)
	{
		sif_data[i] = *(data+i);
		check_sum ^= sif_data[i];
	}
	send_len = len;

#ifdef CONFIG_FORZA_SIF_TOOL_EN
	if((len != SIF_TOOL_LUYUAN_DATA_NUM) && (len != SIF_TOOL_BATTERY_DATA_NUM))
#endif
	{
		/* 修复：工具模式下绿源BMS/电池单线协议上位机已生成累加和，不能再追加FZ异或校验字节 */
		sif_data[len] = check_sum;
		send_len = len+1;
	}

	eLIBs_fioctrl(h_sif_dev , DRV_SIF_CMD_SEND_DATA, send_len, (void *)sif_data);
}

static void can_msg_send_proc(__u8 *data, __s32 len)
{
	static ES_FILE* h_can_dev = NULL;

	if(h_can_dev == NULL)
	{
		h_can_dev = eLIBs_fopen("b:\\USER\\CAN", "r+");
		if(!h_can_dev)
		{
			eLIBs_printf("obd open CAN driver failed!\n");
			return;
		}
	}

	eLIBs_fioctrl(h_can_dev , DRV_CAN_CMD_SEND_DATA, len, (void *)data);	
}

static __s32 obd_data_proc(__u8 *data, __u32 len)
{
	__u32 i = 1;		//校验 从数据长度(byte1---最后一个数据)
	__u8 j = 0;
	__u8 check_sum = 0;
	__u8 send_data[2] = {0};

#if 0
	{
		__u32 j = 0;
		eLIBs_printf("need pro data(len=%d) : ",len);
		for(;j<len;j++)
		{
			eLIBs_printf("%02x ",*(data+j));
		}
		eLIBs_printf("\n");
	}
#endif

	//数据校验
	for(i=1;i<len-1;i++)
	{
		check_sum += *(data+i);
	}
	//eLIBs_printf("------ check_sum = %02x ------\n",check_sum);
	
	if(*(data+len-1) != check_sum)
	{
		eLIBs_printf("------ obd data check fail! ------\n");
		return EPDK_FAIL;
	}
	else
	{
		//eLIBs_printf("------ obd data check successed! ------\n");
		send_data[0] = *(data+1);
		send_data[1] = *(data+3);
	}

	if(send_data[0] == 0x81 || send_data[0] == 0x82)
	{
		for(j=0;j<5;j++)
		{
			can_msg_send_proc(send_data,2);
			esKRNL_TimeDly(10);
		}
	}
	else
	{
		can_msg_send_proc(send_data,2);
		esKRNL_TimeDly(2);
	}

	return EPDK_OK;
}

__s32 obd_uart_data_proc(void)
{
	__u16 i , j , k;
	__u16 len;
	char *p = 0;
	char *q = 0;
	char *p1 = 0;
	char *q1 = 0;
	char *p2 = 0;
	char *q2 = 0;
	char *str_sch = NULL;
	char *str_sch2 = NULL;
	__u8 proc_data[64];	//处理数据最大个数64,可根据实际作调整
	__u32 proc_data_cnt = 0;
	__u8 exit_flag = 0;
	
	len = check_uart_data_len();

	if(len)
	{
		__u8 temp_buf[MAX_FIFO_LENGTH];
		eLIBs_memset(temp_buf, 0, MAX_FIFO_LENGTH);
		for(i=0; i<len; i++)
		{
			drv_obd.obd_data[drv_obd.obd_data_len] = uart_data_get();
			drv_obd.obd_data_len++;
			if(drv_obd.obd_data_len >= MAX_FIFO_LENGTH)
			{
				__wrn("obd uart data overflow!!!!!!!!!!\n");
			#if 1 //保险起见
				eLIBs_memset(drv_obd.obd_data,0,sizeof(drv_obd.obd_data));
				drv_obd.obd_data_len = 0;
			#endif
			}
		}

#ifdef CONFIG_FORZA_SIF_TOOL_EN
	#if 0
		{
			__u32 n = 0;
			eLIBs_printf("uart recv sif data(len=%d) : ",drv_obd.obd_data_len);
			for(;n<len;n++)
			{
				eLIBs_printf("%02x ",drv_obd.obd_data[n]);
			}
			eLIBs_printf("\n");
		}
	#endif
		sif_msg_send_proc(drv_obd.obd_data,drv_obd.obd_data_len);
		eLIBs_memset(drv_obd.obd_data,0,sizeof(drv_obd.obd_data));
		drv_obd.obd_data_len = 0;
		return EPDK_OK;
#endif

		while(!exit_flag)
		{
#if 0
			eLIBs_printf("drv_obd.obd_data_len = %d\n",drv_obd.obd_data_len);
			for(i=0; i<drv_obd.obd_data_len; i++)
			{
				eLIBs_printf("%02x ",drv_obd.obd_data[i]);
			}
			eLIBs_printf("\n\n");
#endif
		
			for(i=0; i<drv_obd.obd_data_len; i++)
			{
				//有效数据帧以0x2e开头
				if(drv_obd.obd_data[i] == 0x2e)
				{
					k = i;
					//获取这一帧数据长度
					proc_data_cnt = drv_obd.obd_data[i+2];

					//+4是加上头1个字节,key占1个字节,数据长度1个字节,尾1个字节
					if((proc_data_cnt+4) <= (drv_obd.obd_data_len - i))	
					{
						eLIBs_memset(proc_data,0,sizeof(proc_data));
						for(j=0;j<proc_data_cnt+4;j++)
						{
							proc_data[j] = drv_obd.obd_data[i+j];
						}

						obd_data_proc(proc_data,proc_data_cnt+4);

						//从drv_obd.obd_data中去除处理过的这部分数据,再重新组合新的drv_obd.obd_data
						for(;k<drv_obd.obd_data_len;k++)
						{
							if((k+proc_data_cnt+4)<drv_obd.obd_data_len)
							{
								drv_obd.obd_data[k] = drv_obd.obd_data[k+proc_data_cnt+4];
							}
							else
							{
								drv_obd.obd_data[k] = 0;
							}
						}
						
						drv_obd.obd_data_len = drv_obd.obd_data_len-(proc_data_cnt+4);
						break;
					}
					else
					{
						exit_flag = 1;
					}
				}
			}

			if(i>=drv_obd.obd_data_len)
			{
				exit_flag = 1;
			}

			esKRNL_TimeDly(1);
		}
	}
	return EPDK_FALSE;
}

void data_msg_recv_from_can(__u8 *data, __s32 len)
{
	__u8 i = 1;
	__u8 check_sum = 0;
	__u8 send_data[6] = {0x2E,0x00,0x02,0x00,0x00,0x00};
	//eLIBs_printf("------ recv data from can , data[0] = %02x , data[1] = %02x ------\n",data[0],data[1]);

	send_data[1] = data[0];
	send_data[3] = data[1];

	for(;i<5;i++)
	{
		check_sum += send_data[i];
	}
	send_data[5] = check_sum;
	
	obd_uart_send(send_data,6);
}
