/*
****************************************************************************************************
*                                               MELIS
*                               the Easy Portable/Player Develop Kits
*                                           BT Driver
*
*                           (c) Copyright 2011-2014, All winners Co,Ld.
*                                       All Rights Reserved
*
* File    : drv_obd_i.h
* By      : james.deng
* Version : 1.0.0
* Date    : 2011-12-24
* Descript:
* Update  : <date>          <author>            <version>           <notes>
*           2011-12-24      james.deng          1.0.0               build the file.
****************************************************************************************************
*/

#ifndef __DRV_OBD_I_H__
#define __DRV_OBD_I_H__

#include <libc.h>
#include <kapi.h>
#include <mod_defs.h> 
#include <log.h>
#include <hal_uart.h>
#include <rtthread.h>
#include "dfs_posix.h"
#include <emodules/mod_obd.h>

#define UART_RW_BLOCKED				//如果uart读写接口是阻塞的，请打开着宏

// obd soft buffer size for reading
#define OBD_BUFFER_SIZE        	4096
#define MAX_FIFO_LENGTH			1024
#define MAX_CMD_DATA_LEN		MAX_FIFO_LENGTH

typedef struct BYTES_FIFO
{
 	__u16 head;
	__u16 tail;
	__u8 buf[MAX_FIFO_LENGTH];
}s_bytes_fifo;

typedef struct STRUCT_OBD_DEV
{
    __u32  status;
    __u32  used;
} s_dev_obd;

typedef struct STRUCT_OBD_DRV
{
	__u32           mid;
	__u32           used;
	__hdle			hReg;
	s_dev_obd      	dev_obd;
	__u8 			tid;
	__s32 			uart_file;
	s_obd_info 		obd_info;
	s_bytes_fifo 	uart_buf;
	__u8 			obd_uart_task;
	__u8 			obd_data[MAX_FIFO_LENGTH];
	__u16 			obd_data_len;
	__u32 			bdrate;
#if 1//def UART_RW_BLOCKED
	__u8 			t_uart_read_task;
#endif
} s_drv_obd;

extern  __dev_devop_t  obd_dev_ops;

// define at drv_obd.c
extern s_drv_obd drv_obd;

extern __s32 DRV_OBD_MInit(void);
extern __s32 DRV_OBD_MExit(void);
extern __mp  *DRV_OBD_MOpen(__u32 mid, __u32 mod);
extern __s32 DRV_OBD_MClose(__mp *mp);
extern __u32 DRV_OBD_MRead(void *pdata, __u32 size, __u32 n, __mp *mp);
extern __u32 DRV_OBD_MWrite(const void *pdata, __u32 size, __u32 n, __mp *mp);
extern __s32 DRV_OBD_MIoctrl(__mp *mp, __u32 cmd, __s32 aux, void *pbuffer);

void * obd_api_get_sys_state_ptr(void);
extern void data_recv_from_can(__u8 *data, __s32 len);

#endif // __DRV_BT_I_H__

