
#ifndef _SIF_H_
#define _SIF_H_

#include "drv_sif_i.h"

//以下宏由协议而定
#define SYNC_TIME_NUM       (992)     	//992Tosc中的992 	//同步信号的低电平数
#define SHORT_TIME_NUM      (32)      	//一个逻辑周期中短的时间：32Tosc中的32 
#define LONG_TIME_NUM       (64)      	//一个逻辑周期中长的时间：64Tosc中的64 
#if defined(CONFIG_FORZA_SKZJTDQR0013_USER)
#define DEVICE_CODE			(0x3A)		//DATA0 设备编码固定
#else
#define DEVICE_CODE			(0x08)		//DATA0 设备编码固定
#endif
#define SEQ_CODE			(0x61)		//DATA1 流水号固定   Multiple

#define	MOTOR_POL_NUM		(26)		//当前电机的极对数,车厂提供
#define	HALL_NUM_PER_CIRCLE	(1)			//电机1圈的hall个数
#if defined(CONFIG_FORZA_SKZJTJQX_USER) || (CONFIG_FORZA_SKZJTZQXZZ_USER) || (CONFIG_FORZA_SKZJTZQXZZR01_USER)|| (CONFIG_FORZA_SKZJTDQR0013_USER)
#define	TYRE_DIA_NUM		(391)		//轮胎直径16英寸 = (16*25.4)mm
#elif defined(CONFIG_FORZA_SKZJTDQR003_USER) 
#define	TYRE_DIA_NUM		(467)		//轮胎直径16英寸 = (16*25.4)mm
#elif defined(CONFIG_FORZA_SKZJTDQR04_USER)
#define	TYRE_DIA_NUM		(638)
#elif defined(CONFIG_FORZA_SKZJTZQXZZR_USER)
#define	TYRE_DIA_NUM		(452)
#elif defined(CONFIG_FORZA_SKZJTZQX03_USER) || defined(CONFIG_FORZA_SKZJTZQX003_USER) || defined(CONFIG_FORZA_SKZJTZQX066_USER)
#define	TYRE_DIA_NUM		(415)
#define	LIMIT_TYRE_DIA_NUM	(440)
#elif defined(CONFIG_FORZA_SKZJTZQX033_USER)
#define	TYRE_DIA_NUM		(630)
#define	LIMIT_TYRE_DIA_NUM	(440)
#elif defined(CONFIG_FORZA_SKZJTZQX036_USER)
#define	TYRE_DIA_NUM		(368)
#define	LIMIT_TYRE_DIA_NUM	(440)
#else
#define	TYRE_DIA_NUM		(407)		//轮胎直径16英寸 = (16*25.4)mm
#endif

#define SPEED_TIME_OUT_CNT	(200)		//发送速度数据间隔超过此超时时间则认为数据中断不进行里程累积,单位 *10 ms

extern __s32 sif_init(void);
extern __s32 sif_exit(void);

#endif
