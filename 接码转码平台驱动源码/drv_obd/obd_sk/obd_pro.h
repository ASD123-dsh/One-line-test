/*
****************************************************************************************************
*                                               MELIS
*                               the Easy Portable/Player Develop Kits
*                                           BT Driver
*
*                           (c) Copyright 2011-2014, All winners Co,Ld.
*                                       All Rights Reserved
*
* File    : obd_pro.h
* By      : james.deng
* Version : 1.0.0
* Date    : 2011-12-24
* Descript:
* Update  : <date>          <author>            <version>           <notes>
*           2011-12-24      james.deng          1.0.0               build the file.
****************************************************************************************************
*/

#ifndef __OBD_PRO_H__
#define __OBD_PRO_H__

#include "drv_obd_i.h"

extern __s32 obd_uart_data_proc(void);
extern void data_msg_recv_from_can(__u8 *data, __s32 len);

#endif // __OBD_PRO_H__

