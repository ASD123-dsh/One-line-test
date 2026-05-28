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

#include "drv_obd_i.h"
#include "obd_pro.h"

s_drv_obd drv_obd;

static __u32 obd_get_buffer_size(void)	//20191017
{
    __u32 size;

    if(drv_obd.uart_buf.head > drv_obd.uart_buf.tail)
        size = drv_obd.uart_buf.head - drv_obd.uart_buf.tail;
    else if(drv_obd.uart_buf.head < drv_obd.uart_buf.tail)
        size = MAX_FIFO_LENGTH - (drv_obd.uart_buf.tail - drv_obd.uart_buf.head);
    else
        size = MAX_FIFO_LENGTH;

    return size;
}

__s32 obd_uart_rcv_check(void)
{
	__u8    *buffer;
	__u32   i;
	__u32   ret;
	__s32 cpu_sr;
	uart_msg_t msg;

	__u32 size = obd_get_buffer_size();	//20191017
	if(size == 0)
	{
		eLIBs_printf("uart com buf is full!!!\n");
		return EPDK_FAIL;
	}
	buffer = esMEMS_Balloc(size);
	if (NULL == buffer)
	{
		__wrn("allocate memory for test_task failed\n");
		return EPDK_FAIL;
	}
	eLIBs_memset(buffer, 0, size);
	ENTER_CRITICAL(cpu_sr);
	msg.buf = buffer;
	msg.len = 1;
	ret = ioctl(drv_obd.uart_file, UART_RECIEVE, &msg);
	EXIT_CRITICAL(cpu_sr);
	if(ret != 0)
	{
		if(ret <= size)
		{
			//__msg("uart rceived %d bytes\n", ret);
			for(i = 0; i < ret; i++)
			{
				//eLIBs_printf(" 0x%02x \n", buffer[i]);
				//__msg("drv_obd.uart_buf.head=%d\n", drv_obd.uart_buf.head);
				//__msg("drv_obd.uart_buf.tail=%d\n", drv_obd.uart_buf.tail);
				if(((drv_obd.uart_buf.tail + 1) % MAX_FIFO_LENGTH) != drv_obd.uart_buf.head)
				{
					drv_obd.uart_buf.buf[drv_obd.uart_buf.tail++] = buffer[i];
					drv_obd.uart_buf.tail %= MAX_FIFO_LENGTH ;
				}
				else
				{
					__msg("uart data overflow!!!!!!!!!!!\n");
					drv_obd.uart_buf.buf[drv_obd.uart_buf.tail++] = buffer[i];
					drv_obd.uart_buf.tail %= MAX_FIFO_LENGTH ;
				}
				if(i  == (ret-1))
				{
					__inf("\n");
				}
			}
		}
		else
		{
			eLIBs_printf("ERR: uart data is larger than buffer size!!!!\n");
		}
	}
	esMEMS_Bfree(buffer, size);
	buffer = 0;
	return ret;
}

static __krnl_event_t *uart_send_sem = 0;
static __s32 uart_send_sem_init(void)
{
	if (0 == uart_send_sem)
	{
		uart_send_sem = esKRNL_SemCreate(1);
	}

	if(uart_send_sem)
	{
		return EPDK_OK;
	}
	else
	{
		return EPDK_FAIL;
	}
}

static __s32 uart_send_sem_deinit(void)
{
	if (uart_send_sem)
	{
		__u8 err;

		esKRNL_SemDel(uart_send_sem, OS_DEL_ALWAYS, &err);
		uart_send_sem = NULL;
	}

	return EPDK_OK;
}

static __s32 uart_send_sem_pend(void)
{
	__u8 err;
	if (uart_send_sem)
	{
		esKRNL_SemPend(uart_send_sem, 0, &err);
	}

	return 0;
}

static __s32 uart_send_sem_accept(void)
{
	__u16 sem_nr;

	sem_nr = esKRNL_SemAccept(uart_send_sem);
	return sem_nr;
}

static __s32 uart_send_sem_post(void)
{
	esKRNL_SemPost(uart_send_sem);
	return 0;
}

#ifdef UART_RW_BLOCKED
static __krnl_event_t *uart_read_sem = 0;
static __s32 uart_read_sem_init(void)
{
	if (0 == uart_read_sem)
	{
		uart_read_sem = esKRNL_SemCreate(1);
	}

	if(uart_read_sem)
	{
		return EPDK_OK;
	}
	else
	{
		return EPDK_FAIL;
	}
}

static __s32 uart_read_sem_deinit(void)
{
	if (uart_read_sem)
	{
		__u8 err;

		esKRNL_SemDel(uart_read_sem, OS_DEL_ALWAYS, &err);
		uart_read_sem = NULL;
	}
	return EPDK_OK;
}

static __s32 uart_read_sem_pend(void)
{
	__u8 err;
	if (uart_read_sem)
	{
		esKRNL_SemPend(uart_read_sem, 0, &err);
	}
	return 0;
}

static __s32 uart_read_sem_accept(void)
{
	__u16 sem_nr;

	sem_nr = esKRNL_SemAccept(uart_read_sem);
	return sem_nr;
}

static __s32 uart_read_sem_post(void)
{
	esKRNL_SemPost(uart_read_sem);
	return 0;
}
#endif

__s32 obd_uart_send(__u8 *buffer, __u32 size)
{
	__u32 i = 0;
	__u32   ret;
	uart_msg_t msg;
	
	__msg("%s()\n", __func__);
	uart_send_sem_pend();	//20191008
#if 0
	eLIBs_printf("obd uart send buffer(%d):",size);
	for(;i<size;i++)
	{
		eLIBs_printf("%02x ", buffer[i]);
	}
	eLIBs_printf("\n");
#endif
	msg.buf = buffer;
	msg.len = size;
	ret = ioctl(drv_obd.uart_file, UART_SEND, &msg);
	__msg("ret=%d\n", ret);
	uart_send_sem_post();	//20191008
	return EPDK_OK;
}

#ifdef UART_RW_BLOCKED
static void uart_com_rcv_task(void *p_arg)
{
    while(1)
    {
        obd_uart_rcv_check();
        uart_read_sem_post();
    }
}
#endif

void obd_uart_task(void *p_arg)
{
	while(1)
	{
		if(esKRNL_TDelReq(EXEC_prioself) == OS_TASK_DEL_REQ)
		{
			goto EXIT_TASK;
		}
		esKRNL_TimeDly(1);
		//__here__;
		//esMEMS_Info();
#ifdef UART_RW_BLOCKED
		uart_read_sem_pend();
#else
		obd_uart_rcv_check();
#endif
		//esMEMS_Info();
		obd_uart_data_proc();
	}
	EXIT_TASK:
	esKRNL_TDel(EXEC_prioself);
}

__s32 obd_reset_bdrate(void)
{
	_uart_config_t uart_config;
	__s32 ret;

	uart_config.word_length = UART_WORD_LENGTH_8;
	uart_config.stop_bit = UART_STOP_BIT_1;
	uart_config.parity = UART_PARITY_NONE;
	
	if(drv_obd.uart_file)
	{
		__msg("drv_obd.bdrate=%d\n", drv_obd.bdrate);
		__msg("uart_com_reset_bdrate\n");
		if(!drv_obd.bdrate)
		{
			drv_obd.bdrate =  9600;
			uart_config.baudrate = UART_BAUDRATE_9600;
		}
		else
		{
			switch (drv_obd.bdrate)
			{
				case 9600:
					uart_config.baudrate = UART_BAUDRATE_9600;
					break;
				case 19200:
					uart_config.baudrate = UART_BAUDRATE_19200;
					break;
				case 38400:
					uart_config.baudrate = UART_BAUDRATE_38400;
					break;
				case 57600:
					uart_config.baudrate = UART_BAUDRATE_57600;
					break;
				case 115200:
					uart_config.baudrate = UART_BAUDRATE_115200;
					break;
				case 230400:
					uart_config.baudrate = UART_BAUDRATE_230400;
					break;
				case 460800:
					uart_config.baudrate = UART_BAUDRATE_460800;
					break;
				case 576000:
					uart_config.baudrate = UART_BAUDRATE_576000;
					break;
				case 921600:
					uart_config.baudrate = UART_BAUDRATE_921600;
					break;
				default:
					__msg("unsupport uart baudrate %d\n", drv_obd.bdrate);
					return EPDK_FAIL;
			}
		}
		ret = ioctl(drv_obd.uart_file, UART_CONFIG, &uart_config);
		return ret;
	}
    __msg("uart_file is null\n");
}

__s32 obd_uart_init(void)
{
	uart_send_sem_init();
#ifdef UART_RW_BLOCKED
	uart_read_sem_init();
#endif
	eLIBs_memset(&(drv_obd.uart_buf), 0, sizeof(s_bytes_fifo));
	obd_reset_bdrate();
	drv_obd.obd_uart_task= esKRNL_TCreate(obd_uart_task, NULL, 0x8000, KRNL_priolevel2);

	if(drv_obd.obd_uart_task == 0)
	{
		__wrn("create obd_uart_task failed!\n");
	}
#ifdef UART_RW_BLOCKED
	drv_obd.t_uart_read_task= esKRNL_TCreate(uart_com_rcv_task, NULL, 0x8000, KRNL_priolevel2);
	if(drv_obd.t_uart_read_task == 0)
	{
		__wrn("create t_uart_read_task failed!\n");
	}
#endif

	return EPDK_OK;
}

static __s32 uart_com_exit(void)
{
	if(drv_obd.obd_uart_task)
	{
		while(1)
		{
			if(esKRNL_TDelReq(drv_obd.obd_uart_task ) == OS_TASK_NOT_EXIST)
			{
				break;
			}
			esKRNL_TimeDly(1);
		}
		drv_obd.obd_uart_task = 0;
	}
	uart_send_sem_deinit();	
#ifdef UART_RW_BLOCKED
	if(drv_obd.t_uart_read_task)
	{
		while(1)
		{
			if(esKRNL_TDelReq(drv_obd.t_uart_read_task ) == OS_TASK_NOT_EXIST)
			{
				break;
			}
			esKRNL_TimeDly(1);
		}
		drv_obd.t_uart_read_task = 0;
	}
	uart_read_sem_deinit();
#endif
	return EPDK_OK;
}

void data_recv_from_can(__u8 *data, __s32 len)
{
	data_msg_recv_from_can(data,len);
}

__s32 DRV_OBD_MInit(void)
{
	__msg("%s()\n", __func__);
	memset(&drv_obd, 0, sizeof(s_drv_obd));
	return 0;
}

__s32 DRV_OBD_MExit(void)
{
	__msg("%s()\n", __func__);
	memset(&drv_obd, 0, sizeof(s_drv_obd));
	return 0;
}

__mp *DRV_OBD_MOpen(__u32 mid, __u32 mod)
{
	__s32 cpu_sr;

	ENTER_CRITICAL(cpu_sr);
	if (1 == drv_obd.used)
	{
		__msg("obd used by someone else\n");
		EXIT_CRITICAL(cpu_sr);
		return (__mp *)0;
	}
	// drv_obd.used = 1;
	EXIT_CRITICAL(cpu_sr);

	drv_obd.mid = mid;

	return (__mp *)&drv_obd;
}

__s32 DRV_OBD_MClose(__mp *mp)
{
	__s32 cpu_sr;

	ENTER_CRITICAL(cpu_sr);
	if (0 == drv_obd.used)
	{
		EXIT_CRITICAL(cpu_sr);
		return EPDK_FAIL;
	}
	drv_obd.used = 0;
	EXIT_CRITICAL(cpu_sr);

	return EPDK_OK;
}

__u32 DRV_OBD_MRead(void *pdata, __u32 size, __u32 n, __mp *mp)
{
		return 0;
}

__u32 DRV_OBD_MWrite(const void *pdata, __u32 size, __u32 n, __mp *mp)
{
		return 0;
}

__s32 DRV_OBD_MIoctrl(__mp *mp, __u32 cmd, __s32 aux, void *pbuffer)
{
	__msg("%s()\n", __func__);
	__msg("aux==%d\n", aux);
	switch(cmd)
	{
		case DRV_CMD_PLUGIN:
		{
			__msg("DRV_CMD_PLUGIN\n");
			if(drv_obd.used)
			{
				__msg("obd already used\n");
				return EPDK_FAIL;
			}
			esKRNL_TimeDly(10);

			if(aux == 0)
			{
				__msg("obd use uart0\n");
				drv_obd.uart_file = open("/dev/uart0/",O_RDWR);
			}
			else if(aux == 1)
			{
				__msg("obd use uart1\n");
				drv_obd.uart_file = open("/dev/uart1/",O_RDWR);
			}
			else if(aux == 2)
			{
				__msg("obd use uart2\n");
				drv_obd.uart_file = open("/dev/uart2/",O_RDWR);
			}
			else if(aux == 3)
			{
				__msg("obd use uart3\n");
				drv_obd.uart_file = open("/dev/uart3/",O_RDWR);
			}
			else if(aux == 4)
			{
				__msg("obd use uart4\n");
				drv_obd.uart_file = open("/dev/uart4/",O_RDWR);
			}
			else
			{
				__msg("unknown uart port!!!\n");
			}

			__msg("uart_file==0x%x\n", drv_obd.uart_file);
			if(!drv_obd.uart_file )
			{
				__msg("Open UART Dev File Failed\n");
				return EPDK_FAIL;
			}
			__msg("open uart succeed...\n");
			drv_obd.hReg = esDEV_DevReg("USER4", "OBD", &obd_dev_ops, 0);
			if(NULL == drv_obd.hReg)
			{
				__msg("user OBD registered Error!\n");
				close( drv_obd.uart_file);
				return EPDK_FAIL;
			}
			
			if(pbuffer)
			{
				drv_obd.bdrate = (__u32)pbuffer;
			}
			else
			{
				drv_obd.bdrate = 9600;
			}
			obd_uart_init();
			drv_obd.used = 1;
			//eLIBs_printf("OBD DRV VER = %s , uart%d(0x%x) , bdrate = %d\n", DRV_OBD_VER_STR,aux,drv_obd.uart_file,drv_obd.bdrate);
			return EPDK_OK;
		}
		case DRV_CMD_PLUGOUT:
		{
			__msg("DRV_CMD_PLUGOUT\n");
			if(drv_obd.used == 1)
			{
				//DRV_FM_SelectAuxAudioChannel();
				if(drv_obd.uart_file)
				{
					close(drv_obd.uart_file);
				}

				if(!drv_obd.hReg)
				{
					__wrn("Dev not plugin!\n");
					return EPDK_FAIL;
				}
				esDEV_DevUnreg(drv_obd.hReg);
			}

			drv_obd.used = 0;
			return EPDK_OK;
		}

		case DRV_CMD_GET_STATUS:
		{
			__msg("DRV_CMD_GET_STATUS\n");
			if(drv_obd.used)
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

