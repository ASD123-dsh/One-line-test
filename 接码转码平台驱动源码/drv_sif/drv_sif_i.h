/*
*********************************************************************************************************
*											        ePDK
*						            the Easy Portable/Player Develop Kits
*									          ir keyboard driver
*
*						        (c) Copyright 2006-2007, Steven.ZGJ China
*											All	Rights Reserved
*
* File    : drv_sif_i.h
* By      : jerry
* Version : V1.00
*********************************************************************************************************
*/
#ifndef  _DRV_SIF_I_H_
#define  _DRV_SIF_I_H_

#include "libc.h"
#include "mod_twi.h"
#include <sunxi_hal_twi.h>

#include <log.h>
#include <init.h>
#include "dfs_posix.h"
#include <kconfig.h>

#include <typedef.h>
#include <mod_defs.h>
#include "kapi.h"
#include "misc/pub0.h"
#include "mod_sif.h"

#define HW_TIMER_TIME		(50)		//硬件定时器时长,单位us
#define REV_BIT_NUM         (8)      	//接收的bit位个数，看是按字节接收还是按字接收，1字节=8bit，1字=2字节=16bit
#if defined(CONFIG_HUAWEI_SIF_EN)
#define REV_DATA_NUM        (14)      	//接收的数据个数
#elif defined(CONFIG_AIMA_SIF_EN) || defined(CONFIG_TAILING_SIF_EN)
#define REV_DATA_NUM        (15)      	//接收的数据个数
#elif defined(CONFIG_ANXIAN_SKWXHLW_USER) || defined(CONFIG_ANXIAN_SKWXHLW2_USER)
#define REV_DATA_NUM        (13)      	//接收的数据个数
#else
#define REV_DATA_NUM        (12)      	//接收的数据个数
#endif

#ifdef CONFIG_SIF_BMS_EN
#if defined(CONFIG_YADI_SKSDQDJZ001_USER) || defined(CONFIG_ANXIAN_SKSDQDJZ001_USER)
#define BMS_REV_DATA_NUM	(6)			//BMS接收的数据个数
#elif defined(CONFIG_ANXIAN_SKWXZZ20260101_USER)
#define BMS_REV_DATA_NUM	(12)		//BMS接收的数据个数
#elif defined(CONFIG_FORZA_SKZJTDQR04_USER)
#define BMS_REV_DATA_NUM	(10)		//BMS接收的数据个数
#elif defined(CONFIG_YADI_SKZJTZLT01_USER)
#define BMS_REV_DATA_NUM	(15)		//BMS接收的数据个数
#else
#define BMS_REV_DATA_NUM	(12)		//BMS接收的数据个数
#endif
#else
#if defined(CONFIG_FORZA_SKZJTDQR0013_USER)|| (CONFIG_FORZA_SKZJTJQX_USER) 
#define BMS_REV_DATA_NUM	(10)			//BMS接收的数据个数
#else
#define BMS_REV_DATA_NUM	(6)			//BMS接收的数据个数
#endif
#endif

typedef enum 
{ 
	INITIAL_STATE=0,            	//初始状态，等待接收同步信号 
	SYNC_L_STATE=1,             	//接收同步低电平信号状态 
	SYNC_H_STATE=2,             	//接收同步高电平信号状态 
	DATA_REV_STATE=3,           	//读取数据码电平状态 
}REV_STATE_e;                   	//接收数据状态枚举

typedef struct STRUCT_SIF_DEV
{
	__u32  status;
	__u32  used;
}__sif_dev_t;

typedef struct STRUCT_SIF_DRV
{
	__u32           mid;
	__u32           used;
	__hdle			hReg;
	__sif_dev_t     sif_dev;
	__krnl_event_t 	*sem1;
	__krnl_event_t 	*sem2;
	__pCBK_t 		app_cb;
	void 			*app_ctx;
	__s32 			speed_offset;
	__u8			speed_limit_flag;	// 1:启动限速 0:解除限速
	__u8			start_flag;			// 1:启动sif数据获取处理 0:停止
	__s32 			hw_timer;
	__s32 			hw_timer2;
	__u32 			cur_timer_cnt;
	__u32 			last_timer_cnt;
	__u32 			bms_cur_timer_cnt;
	__u32 			bms_last_timer_cnt;
	__u32 			data_proc_th;
	__u32 			bms_data_proc_th;
	__u8 			if_data_proc_flag;		//是否需要进行数据处理的flag 0:不需要 1:需要
	__u8 			if_bms_data_proc_flag;	//是否需要进行BMS数据处理的flag 0:不需要 1:需要
	__u32 			mm_inc;		//累计行驶的mm数
	__hdle 			hirq;		//一线通数据中断IO
	__hdle 			bms_hirq;	//电池BMS一线通数据中断IO
	__hdle 			send_hio;
	__u8			recv_state;		//接收数据状态
	__u32 			recv_data[REV_BIT_NUM*REV_DATA_NUM*2];	//存放SIF收到的数据
	__u8			sif_data[REV_DATA_NUM];		//最终存放收到并解析出来的正确数据
	
	__u8			bms_recv_state;		//BMS接收数据状态
	__u32 			bms_recv_data[REV_BIT_NUM*BMS_REV_DATA_NUM*2];	//BMS存放SIF收到的数据
	__u8			bms_sif_data[BMS_REV_DATA_NUM];		//BMS最终存放收到并解析出来的正确数据
	
	__u32			sif_data_cnt;			//一线通数据计数,用于判断是否有一线通数据,若无一线通数据则将显示恢复默认
	__u32			bms_sif_data_cnt;		//BMS一线通数据计数,用于判断是否有一线通数据,若无一线通数据则将显示恢复默认

	__u8			sif_data_from_uart[32];		//从串口接收到的sif数据用于测试SIF
	__u8			sif_data_from_uart_num;		//从串口接收到的sif数据个数
	__u8			sif_recv_data_flag;			////从串口接收到的sif数据标志
}__sif_drv_t;

extern  __dev_devop_t  sif_dev_ops;

__s32 DRV_SIF_MInit(void);
__s32 DRV_SIF_MExit(void);
__mp* DRV_SIF_MOpen(__u32 mid, __u32 mode);
__s32 DRV_SIF_MClose(__mp *mp);
__u32 DRV_SIF_MRead(void *pdata, __u32 size, __u32 n, __mp *mp);
__u32 DRV_SIF_MWrite(const void *pdata, __u32 size, __u32 n, __mp *mp);
__s32 DRV_SIF_MIoctrl(__mp *mp, __u32 cmd, __s32 aux, void *pbuffer);

extern void sif_set_drv_cb(__pCBK_t cb, void *ctx);

#endif /*_DRV_SIF_I_H_*/

