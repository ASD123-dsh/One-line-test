/*
*********************************************************************************************************
*											        ePDK
*						            the Easy Portable/Player Develop Kits
*									           hello world sample
*
*						        (c) Copyright 2006-2007, Steven.ZGJ China
*											All	Rights Reserved
*
* File    : magic.c
* By      : Steven.ZGJ
* Version : V1.00
*********************************************************************************************************
*/
#include "drv_sif_i.h"

const __module_mgsec_t modinfo __attribute__ ((section (".magic"))) =
{
	{'e','P','D','K','.','m','o','d'},		//.magic
	0x01000000,                				//.version
	EMOD_TYPE_DRV_SIF,                       //.type
	0xF0000,                                //.heapaddr
	0x400,                      			//.heapsize
	{                                       //.mif
		&DRV_SIF_MInit,
		&DRV_SIF_MExit,
		&DRV_SIF_MOpen,
		&DRV_SIF_MClose,
		&DRV_SIF_MRead,
		&DRV_SIF_MWrite,
		&DRV_SIF_MIoctrl
	}
};
