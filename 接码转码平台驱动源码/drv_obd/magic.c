/*
****************************************************************************************************
*                                               MELIS
*                               the Easy Portable/Player Develop Kits
*                                           UART Driver
*
*                           (c) Copyright 2011-2014, All winners Co,Ld.
*                                       All Rights Reserved
*
* File    : magic.c
* By      : james.deng
* Version : 1.0.0
* Date    : 2011-12-24
* Descript:
* Update  : <date>          <author>            <version>           <notes>
*           2011-12-24      james.deng          1.0.0               build the file.
****************************************************************************************************
*/

#include "drv_obd_i.h"

const __module_mgsec_t modinfo __attribute__ ((section (".magic"))) =
{
    {'e', 'P', 'D', 'K', '.', 'm', 'o', 'd'}, //.magic
    0x01000000,                         //.version
    EMOD_TYPE_DRV_OBD,                 //.type
    0xF0000,                            //.heapaddr
    0x400,                              //.heapsize
    {
        //.mif
        &DRV_OBD_MInit,
        &DRV_OBD_MExit,
        &DRV_OBD_MOpen,
        &DRV_OBD_MClose,
        &DRV_OBD_MRead,
        &DRV_OBD_MWrite,
        &DRV_OBD_MIoctrl
    }
};
