
#include "sif.h"
#ifdef CONFIG_SIF_BMS_EN
#include "sif_bms.h"
#endif

#ifdef CONFIG_FORZA_SIF_TOOL_EN
#define SIF_SEND_DATA_TEST				//利用IO口输出模式模拟输出SIF数据波形用于调试,实际应用中将此宏关闭
//#define SUPPORT_PULSE_OUTPUT			//支持脉冲输出
#define SIF_TOOL_LUYUAN_DATA_NUM		(15)	//绿源BMS一线通协议数据长度
#define SIF_TOOL_BATTERY_DATA_NUM		(6)		//电池单线通讯协议数据长度
#define SIF_TOOL_LUYUAN_SYNC_TIME_NUM	(40000/HW_TIMER_TIME)	//绿源BMS同步低电平计数
#define SIF_TOOL_BATTERY_SYNC_TIME_NUM	(62000/HW_TIMER_TIME)	//电池单线同步低电平计数
#define SIF_TOOL_2MS_TIME_NUM			(2000/HW_TIMER_TIME)		//2ms电平计数
#define SIF_TOOL_4MS_TIME_NUM			(4000/HW_TIMER_TIME)		//4ms电平计数
#ifdef SUPPORT_PULSE_OUTPUT
#define PULSE_FREQ_OUTPUT		(166)	//输出的脉冲频率,单位Hz
#define PULSE_L_LEVEL_NUM		(((1000000/HW_TIMER_TIME)/PULSE_FREQ_OUTPUT)/2)	//脉冲低电平计数
#define PULSE_H_LEVEL_NUM		PULSE_L_LEVEL_NUM	//脉冲高电平计数
#endif
#endif

#define setbit(x,y) 			(x|=(1<<y)) 	//将x的第y位置1
#define clrbit(x,y)				(x&=~(1<<y)) 	//将x的第y位清0

#define	SIF_DATA_CNT_MAX		(10*20000)	// 10s
#ifndef CONFIG_SIF_BMS_EN
#define	BMS_SIF_DATA_CNT_MAX	(15*20000)	// 15s
#endif

extern __sif_drv_t	sif_drv;
#ifndef CONFIG_SIF_BMS_EN
static __u32 last_bms_elec = 0;
#endif

static void __call_app(__u32 info, void *p_value)
{
	__u8 err;
	void *para[3];
	
	esKRNL_SemPend(sif_drv.sem2, 0, &err);
	if(sif_drv.app_cb)
	{
		para[0] = sif_drv.app_ctx;
		para[1] = &info;
		para[2] = p_value;
		esKRNL_CallBack(sif_drv.app_cb, para);
	}
	esKRNL_SemPost(sif_drv.sem2);
}

void sif_set_drv_cb(__pCBK_t cb, void *ctx)
{
	__u8 err;

	__msg("%s()\n",__func__);
	__msg("cb==%p\n", cb);
	esKRNL_SemPend(sif_drv.sem2, 0, &err);
	sif_drv.app_cb = esKRNL_GetCallBack(cb);
	sif_drv.app_ctx = ctx;
	esKRNL_SemPost(sif_drv.sem2);
}

static void __check_timer_proc(void)
{
#ifndef CONFIG_SIF_BMS_EN
	__u32 temp_elec = 0;
#endif

	if(sif_drv.start_flag)
	{
		sif_drv.cur_timer_cnt++;
#ifndef CONFIG_SIF_BMS_EN
		sif_drv.bms_cur_timer_cnt++;
#endif
	}
	if(sif_drv.cur_timer_cnt > 0xFFFFFF0)
	{
		sif_drv.cur_timer_cnt = 0;
	}
#ifndef CONFIG_SIF_BMS_EN
	if(sif_drv.bms_cur_timer_cnt > 0xFFFFFF0)
	{
		sif_drv.bms_cur_timer_cnt = 0;
	}
#endif

	if(sif_drv.start_flag)
	{
#if 0
		//当sif_data_cnt/bms_sif_data_cnt达到一定值时判定为一线通通讯失败,数据恢复默认
		sif_drv.sif_data_cnt++;
		if(sif_drv.sif_data_cnt == SIF_DATA_CNT_MAX)
		{
			
		}
#endif
#ifndef CONFIG_SIF_BMS_EN
#if !defined(CONFIG_FORZA_SKZJTZQX003_USER)
		//当bms_sif_data_cnt达到一定值时判定为BMS一线通通讯失败,数据恢复默认
		sif_drv.bms_sif_data_cnt++;
		if(sif_drv.bms_sif_data_cnt == BMS_SIF_DATA_CNT_MAX)
		{
			__call_app(SIF_CB_INFO_ELEC, &temp_elec);
			last_bms_elec = 0;
		}
#endif
#endif
	}
#ifdef CONFIG_SIF_BMS_EN
	bms_check_timer_proc();
#endif
}

static __s32 __hw_timer_init(void)
{
	__csp_timer_req_type_t tmrType = {1*HW_TIMER_TIME, 1};		// HW_TIMER_TIME us定时器

	if(!sif_drv.hw_timer)
	{
		sif_drv.hw_timer = esTIME_RequestTimer(&tmrType, (__pCBK_t)__check_timer_proc, NULL, "sif_check");
		if(!sif_drv.hw_timer)
		{
			__wrn("create timer for sif failed\n");
			return EPDK_FAIL;
		}
		esTIME_StartTimer(sif_drv.hw_timer);
	}

	__msg("__hw_timer_init ok!\n");
	return EPDK_OK;
}

static __s32 __hw_timer_exit(void)
{
    if(sif_drv.hw_timer)
	{
		esTIME_StopTimer(sif_drv.hw_timer);
		esTIME_ReleaseTimer(sif_drv.hw_timer);
		sif_drv.hw_timer = 0;
	}

	sif_drv.cur_timer_cnt = 0;
	sif_drv.last_timer_cnt = 0;
	sif_drv.bms_cur_timer_cnt = 0;
	sif_drv.bms_last_timer_cnt = 0;
	return EPDK_OK;
}

#ifdef SIF_SEND_DATA_TEST
#define SDA_1   	esPINS_WritePinData(sif_drv.send_hio,1,NULL)
#define SDA_0   	esPINS_WritePinData(sif_drv.send_hio,0,NULL)

static __u8 send_data[12] = {DEVICE_CODE,SEQ_CODE,0x00,0x7F,0xA0,0xB8,0x9C,0x05,0xDC,0x62,0x10,0x39};
//static __u8 send_data[12] = {DEVICE_CODE,0x01,0x00,0xAE,0x6E,0x6E,0x00,0x6E,0x6E,0x6E,0x6E,0xA7};
//static __u8 send_data[12] = {DEVICE_CODE,0x02,0x00,0x6D,0x5D,0x5D,0x00,0x5D,0x5D,0x5D,0x5D,0x67};

#ifdef CONFIG_FORZA_SIF_TOOL_EN
/*
*********************************************************************************************************
*                                       获取工具模式同步低电平计数
*
* @brief      : 根据上位机下发的数据长度匹配不同一线通协议的同步低电平时长
* @param[in]  : 无
* @param[out] : 无
* @return     : 同步低电平计数
* @note       : 修复：绿源BMS和电池单线协议同步头与FZ默认协议不同导致转发后设备无法识别
*********************************************************************************************************
*/
static __u32 __sif_tool_get_sync_time_num(void)
{
	if(sif_drv.sif_data_from_uart_num == SIF_TOOL_LUYUAN_DATA_NUM)
	{
		return SIF_TOOL_LUYUAN_SYNC_TIME_NUM;
	}
	else if(sif_drv.sif_data_from_uart_num == SIF_TOOL_BATTERY_DATA_NUM)
	{
		return SIF_TOOL_BATTERY_SYNC_TIME_NUM;
	}

	return SYNC_TIME_NUM;
}

/*
*********************************************************************************************************
*                                       获取工具模式短电平计数
*
* @brief      : 根据上位机下发的数据长度匹配不同一线通协议的短电平时长
* @param[in]  : 无
* @param[out] : 无
* @return     : 短电平计数
* @note       : 修复：BMS类协议使用2ms/4ms脉宽，不能沿用FZ协议32Tosc/64Tosc
*********************************************************************************************************
*/
static __u32 __sif_tool_get_short_time_num(void)
{
	if((sif_drv.sif_data_from_uart_num == SIF_TOOL_LUYUAN_DATA_NUM)
		|| (sif_drv.sif_data_from_uart_num == SIF_TOOL_BATTERY_DATA_NUM))
	{
		return SIF_TOOL_2MS_TIME_NUM;
	}

	return SHORT_TIME_NUM;
}

/*
*********************************************************************************************************
*                                       获取工具模式长电平计数
*
* @brief      : 根据上位机下发的数据长度匹配不同一线通协议的长电平时长
* @param[in]  : 无
* @param[out] : 无
* @return     : 长电平计数
* @note       : 修复：BMS类协议使用2ms/4ms脉宽，不能沿用FZ协议32Tosc/64Tosc
*********************************************************************************************************
*/
static __u32 __sif_tool_get_long_time_num(void)
{
	if((sif_drv.sif_data_from_uart_num == SIF_TOOL_LUYUAN_DATA_NUM)
		|| (sif_drv.sif_data_from_uart_num == SIF_TOOL_BATTERY_DATA_NUM))
	{
		return SIF_TOOL_4MS_TIME_NUM;
	}

	return LONG_TIME_NUM;
}

/*
*********************************************************************************************************
*                                       获取工具模式首bit索引
*
* @brief      : 根据协议要求选择高位先发或低位先发
* @param[in]  : 无
* @param[out] : 无
* @return     : 首bit索引
* @note       : 修复：电池单线通讯协议要求低位先发，原实现固定高位先发
*********************************************************************************************************
*/
static __s8 __sif_tool_get_first_bit_index(void)
{
	if(sif_drv.sif_data_from_uart_num == SIF_TOOL_BATTERY_DATA_NUM)
	{
		return 0;
	}

	return (REV_BIT_NUM-1);
}

/*
*********************************************************************************************************
*                                       判断工具模式当前字节是否发送完成
*
* @brief      : 根据bit发送方向判断当前字节是否已经完成
* @param[in]  : bit_index - 当前bit索引
* @param[out] : 无
* @return     : 1表示完成，0表示未完成
* @note       : 修复：兼容电池单线通讯协议低位先发的bit计数方向
*********************************************************************************************************
*/
static __u8 __sif_tool_is_bit_finish(__s8 bit_index)
{
	if(sif_drv.sif_data_from_uart_num == SIF_TOOL_BATTERY_DATA_NUM)
	{
		return (bit_index >= REV_BIT_NUM);
	}

	return (bit_index < 0);
}

/*
*********************************************************************************************************
*                                       获取工具模式下一bit索引
*
* @brief      : 根据bit发送方向计算下一bit索引
* @param[in]  : bit_index - 当前bit索引
* @param[out] : 无
* @return     : 下一bit索引
* @note       : 修复：兼容电池单线通讯协议低位先发的bit计数方向
*********************************************************************************************************
*/
static __s8 __sif_tool_get_next_bit_index(__s8 bit_index)
{
	if(sif_drv.sif_data_from_uart_num == SIF_TOOL_BATTERY_DATA_NUM)
	{
		return (bit_index+1);
	}

	return (bit_index-1);
}
#endif

static void __check_timer2_proc(void)
{
	static __u32 l_lev_cnt = SYNC_TIME_NUM;
	static __u32 h_lev_cnt = SHORT_TIME_NUM;
	static __u8 data_index = 0;
	static __s8 bit_index = (REV_BIT_NUM-1);
#ifdef CONFIG_FORZA_SIF_TOOL_EN
	static __u8 last_recv_data_flag = 0;
#endif

#ifdef SUPPORT_PULSE_OUTPUT
	static __u32 pulse_l_lev_cnt = PULSE_L_LEVEL_NUM;
	static __u32 pulse_h_lev_cnt = PULSE_H_LEVEL_NUM;
	
	if(pulse_l_lev_cnt)
	{
		pulse_l_lev_cnt--;
		if(!pulse_l_lev_cnt)
		{
			SDA_1;
			pulse_h_lev_cnt = PULSE_H_LEVEL_NUM;
		}
	}
	else if(pulse_h_lev_cnt)
	{
		pulse_h_lev_cnt--;
		if(!pulse_h_lev_cnt)
		{
			SDA_0;
			pulse_l_lev_cnt = PULSE_L_LEVEL_NUM;
		}
	}

	return;
#endif

#ifdef CONFIG_FORZA_SIF_TOOL_EN
	if(sif_drv.sif_recv_data_flag && !last_recv_data_flag)
	{
		/* 修复：收到新一帧串口数据时重置发送状态，避免上一帧协议时序残留影响绿源BMS/电池单线转发 */
		l_lev_cnt = __sif_tool_get_sync_time_num();
		h_lev_cnt = __sif_tool_get_short_time_num();
		data_index = 0;
		bit_index = __sif_tool_get_first_bit_index();
		SDA_0;
	}
	last_recv_data_flag = sif_drv.sif_recv_data_flag;

	if(sif_drv.sif_recv_data_flag)
#endif
	{
		if(l_lev_cnt)
		{
			l_lev_cnt--;
			if(!l_lev_cnt)
			{
				SDA_1;
			}
		}
		else if(h_lev_cnt)
		{
			h_lev_cnt--;
			if(!h_lev_cnt)
			{
				SDA_0;
			}
		}

		if((!l_lev_cnt) && (!h_lev_cnt))
		{
#ifdef CONFIG_FORZA_SIF_TOOL_EN
			if(__sif_tool_is_bit_finish(bit_index))
#else
			if(bit_index < 0)
#endif
			{
				bit_index = (REV_BIT_NUM-1);
#ifdef CONFIG_FORZA_SIF_TOOL_EN
				bit_index = __sif_tool_get_first_bit_index();
#endif
				data_index++;
#ifdef CONFIG_FORZA_SIF_TOOL_EN
				if(data_index >= sif_drv.sif_data_from_uart_num)
#else
				if(data_index >= REV_DATA_NUM)
#endif
				{
					l_lev_cnt = __sif_tool_get_sync_time_num();
					h_lev_cnt = __sif_tool_get_short_time_num();
					data_index = 0;
					bit_index = __sif_tool_get_first_bit_index();
					if(sif_drv.sif_data_from_uart_num == SIF_TOOL_LUYUAN_DATA_NUM)
					{
						SDA_1;
					}
					else
					{
						SDA_0;
					}
					sif_drv.sif_recv_data_flag = 0;
					last_recv_data_flag = 0;
					return;
				}
			}

#ifdef CONFIG_FORZA_SIF_TOOL_EN
			if((sif_drv.sif_data_from_uart[data_index]>>bit_index)&0x01)
#else
			if((send_data[data_index]>>bit_index)&0x01)
#endif
			{
#ifdef CONFIG_FORZA_SIF_TOOL_EN
				l_lev_cnt = __sif_tool_get_short_time_num();
				h_lev_cnt = __sif_tool_get_long_time_num();
#else
				l_lev_cnt = SHORT_TIME_NUM;
				h_lev_cnt = LONG_TIME_NUM;
#endif
			}
			else
			{
#ifdef CONFIG_FORZA_SIF_TOOL_EN
				l_lev_cnt = __sif_tool_get_long_time_num();
				h_lev_cnt = __sif_tool_get_short_time_num();
#else
				l_lev_cnt = LONG_TIME_NUM;
				h_lev_cnt = SHORT_TIME_NUM;
#endif
			}
			
#ifdef CONFIG_FORZA_SIF_TOOL_EN
			bit_index = __sif_tool_get_next_bit_index(bit_index);
#else
			bit_index--;
#endif
		}
	}
}

//设置50us定时器模拟SIF数据发送,则一个周期就是992+32+12*8*(32+64) = 10240 * 50us ~= 500ms一个周期
static __s32 __hw_timer2_init(void)
{
	__csp_timer_req_type_t tmrType = {1*50, 1};		// 50us定时器

	if(!sif_drv.hw_timer2)
	{
		sif_drv.hw_timer2 = esTIME_RequestTimer(&tmrType, (__pCBK_t)__check_timer2_proc, NULL, "sif_check2");
		if(!sif_drv.hw_timer2)
		{
			__wrn("create timer for sif failed\n");
			return EPDK_FAIL;
		}
		esTIME_StartTimer(sif_drv.hw_timer2);
	}

	return EPDK_OK;
}

static __s32 __hw_timer2_exit(void)
{
    if(sif_drv.hw_timer2)
	{
		esTIME_StopTimer(sif_drv.hw_timer2);
		esTIME_ReleaseTimer(sif_drv.hw_timer2);
		sif_drv.hw_timer2 = 0;
	}
	return EPDK_OK;
}

static __s32 __io_init(void)
{
	__s32			 ret;
	user_gpio_set_t  gpio_set[1];

	//利用尾线中P挡引脚模拟SIF数据发送
	eLIBs_memset(gpio_set, 0, sizeof(user_gpio_set_t));
	ret = esCFG_GetKeyValue("sif_para", "sif_send_io", (int *)gpio_set, sizeof(user_gpio_set_t)/4);
	if (!ret)
	{
		if(!sif_drv.send_hio)
		{
			sif_drv.send_hio = esPINS_PinGrpReq(gpio_set, 1);		 
			if (!sif_drv.send_hio)
			{
				__wrn("request send_hio pin failed\n");
				return EPDK_FAIL;
			}	
		}
	}
	else
	{
		__wrn("fetch para from sys_config.fex failed\n");
		return EPDK_FAIL;
	}
	ret = esPINS_SetPinIO(sif_drv.send_hio, 1, NULL);	//output
	esPINS_WritePinData(sif_drv.send_hio,0,NULL);

	return EPDK_OK;
}

static __s32 __io_exit(void)
{
	if(sif_drv.send_hio)
	{
		esPINS_PinGrpRel(sif_drv.send_hio, 0);
	}
	sif_drv.send_hio = NULL;

	return EPDK_OK;
}
#endif

/*
	根据协议速度计算公式:
	N : 每小时电机转过的 hall 个数
	P : 当前电机的极对数
	D: 当前电机的直径
	V: 当前时速
	V = (N * D * pai )/ 6P
	单位换算成 KM/H，此协议中控制器提供一个 500ms 内电机转过的 hall 个数 N_Tx，那
	么（N = N_Tx*7200）； P 为电机极对数，D 电机直径，需整车厂提供或填写个大概值，例
	如 23 对极，16英寸。

	N = hall * 7200;
	P = 23;
	D = 16英寸 = 16 * 25.4 mm;	//按照协议和实际情况D采用轮胎直径
	pai = 3.14;
*/

static __s32 __sif_data_proc(void)
{
	static __u32 delay_cnt = 0;
	static __u32 last_speed = 0;
	static __u32 last_gear = 0xff;
	//static __u32 last_curr = 0;
	static __u32 last_elec = 0;
	//static __u32 last_volt = 0;
	//static __u32 last_s_mode = 0;
	static __u32 last_brake = 0;
	static __u32 last_ecu_e = 0;
	static __u32 last_motor_e = 0;
	static __u32 last_handle_e = 0;
	static __u32 last_error = 0;
	static __u32 last_time = 0;
	__u32 cur_time = 0;
	__u16 hall_h = 0 , hall_l = 0 , hall = 0;
	__s32 cur_speed = 0;
	__u32 cur_gear = 0;
	//__u32 cur_curr = 0;
	__u32 cur_elec = 0;
	//__u32 cur_volt = 0;
	//__u32 cur_s_mode = 0;
	__u32 cur_brake = 0;
	__u32 cur_ecu_e = 0;
	__u32 cur_motor_e = 0;
	__u32 cur_handle_e = 0;
	__u32 cur_error = 0;
	__u32 m_inc;
	__u32 speed_mode = 0;
		
#if 0
	{
		__u8 i = 0;
		eLIBs_printf("SIF data : ");
		for(;i<REV_DATA_NUM;i++)
		{
			eLIBs_printf("0x%02x ",sif_drv.sif_data[i]);
		}
		eLIBs_printf("\n\n");
	}
#endif


	//档位
#if defined(CONFIG_FORZA_SKZJTZQX03_USER) || defined(CONFIG_FORZA_SKZJTZQX033_USER) || defined(CONFIG_FORZA_SKZJTZQX036_USER) || defined(CONFIG_FORZA_SKZJTZQX003_USER)|| defined(CONFIG_FORZA_SKZJTDQR003_USER)|| defined(CONFIG_FORZA_SKZJTDQR0013_USER)|| defined(CONFIG_FORZA_SKZJTZQX066_USER) || defined(CONFIG_FORZA_SKZJTDQR04_USER)
	if(((sif_drv.sif_data[2]>>1)&0x01) || ((sif_drv.sif_data[2]>>3)&0x01))
	{
		cur_gear = 0;	//P档
	}
	else if((sif_drv.sif_data[5] >> 2) & 0x01)
	{
		cur_gear = 2;	//R档
	}
	else
	{
		if(((sif_drv.sif_data[4]>>0)&0x01) && ((sif_drv.sif_data[4]>>1)&0x01))
		{				
			cur_gear = 5;	//D3档 high speed mode
			speed_mode = 1;
		}
		else if(!((sif_drv.sif_data[4]>>0)&0x01) && ((sif_drv.sif_data[4]>>1)&0x01))
		{	
			cur_gear = 4;	//D2档 middle speed mode
			speed_mode = 1;
		}
		else if(((sif_drv.sif_data[4]>>0)&0x01) && !((sif_drv.sif_data[4]>>1)&0x01))
		{		
			cur_gear = 3;	//D1档 low speed mode
			speed_mode = 1;
		}
		else
		{
			cur_gear = 0xff;	//不显示
			speed_mode = 0;
		}
	}
#else
	if(((sif_drv.sif_data[2]>>1)&0x01) || ((sif_drv.sif_data[2]>>3)&0x01))
	{
		cur_gear = 0;	//P档
	}
	else
	{
		cur_gear = 1;	//D档
	}
#endif

	if(last_gear != cur_gear)
	{
		__call_app(SIF_CB_INFO_GEAR, &cur_gear);
		last_gear = cur_gear;
	}

	//速度
	hall_h = (__u16)sif_drv.sif_data[7];
	hall_l = (__u16)sif_drv.sif_data[8];
	hall = (hall_h<<8)|hall_l;
#if defined(CONFIG_FORZA_SKZJTZQX03_USER) || defined(CONFIG_FORZA_SKZJTZQX033_USER) || defined(CONFIG_FORZA_SKZJTZQX036_USER) || defined(CONFIG_FORZA_SKZJTZQX003_USER) || defined(CONFIG_FORZA_SKZJTZQX066_USER)
	if(speed_mode)
		cur_speed = (((hall*72*TYRE_DIA_NUM)/(6*HALL_NUM_PER_CIRCLE*MOTOR_POL_NUM))*314)/(1000000);	//Km/h
	else
		cur_speed = (((hall*72*LIMIT_TYRE_DIA_NUM)/(6*HALL_NUM_PER_CIRCLE*MOTOR_POL_NUM))*314)/(1000000);	//Km/h
#else
	cur_speed = (((hall*72*TYRE_DIA_NUM)/(6*HALL_NUM_PER_CIRCLE*MOTOR_POL_NUM))*314)/(1000000);	//Km/h
#endif
	if(cur_speed)
	{
		cur_speed += sif_drv.speed_offset;
	}
	if(cur_speed < 0)
	{
		cur_speed = 0;
	}
	if(last_speed != cur_speed)
	{
		__call_app(SIF_CB_INFO_SPEED, &cur_speed);
		last_speed = cur_speed;
	}

#if 0
	//电流
	cur_curr = sif_drv.sif_data[6];
	if(last_curr != cur_curr)
	{
		__call_app(SIF_CB_INFO_CURR, &cur_curr);
		last_curr = cur_curr;
	}
#endif

#if 0
	//电量
	cur_elec = sif_drv.sif_data[9];
	if(last_elec != cur_elec)
	{
		__call_app(SIF_CB_INFO_ELEC, &cur_elec);
		last_elec = cur_elec;
	}
#endif

	//刹车
	cur_brake = ((sif_drv.sif_data[4] >> 5) & 0x01) | ((sif_drv.sif_data[5] >> 1) & 0x01);
	if(last_brake != cur_brake)
	{
		__call_app(SIF_CB_INFO_BRAKE, &cur_brake);
		last_brake = cur_brake;
	}

	//控制器故障
	cur_ecu_e = (sif_drv.sif_data[3] >> 4) & 0x01;
	if(last_ecu_e != cur_ecu_e)
	{
		__call_app(SIF_CB_INFO_ECU_E, &cur_ecu_e);
		last_ecu_e = cur_ecu_e;
	}

	//电机故障
	cur_motor_e = (sif_drv.sif_data[3] >> 6) & 0x01;
	if(last_motor_e != cur_motor_e)
	{
		__call_app(SIF_CB_INFO_MOTOR_E, &cur_motor_e);
		last_motor_e = cur_motor_e;
	}

	//转把故障
	cur_handle_e = (sif_drv.sif_data[3] >> 5) & 0x01;
	if(last_handle_e != cur_handle_e)
	{
		__call_app(SIF_CB_INFO_HANDLE_E, &cur_handle_e);
		last_handle_e = cur_handle_e;
	}
	
	//里程必须实时累加计算,当前速度*运行时间累积形成
	cur_time = esKRNL_Time();
	if(last_time)
	{
		if((cur_time - last_time) < SPEED_TIME_OUT_CNT)
		{
			sif_drv.mm_inc += (cur_speed*100/36)*(cur_time - last_time);
		}
	}
	last_time = cur_time;
	m_inc = sif_drv.mm_inc / 1000;	//单位由mm转为m
	sif_drv.mm_inc %= 1000;
	if(m_inc)
	{
		__call_app(SIF_CB_INFO_M_INC, &m_inc);
	}

	return EPDK_OK;
}

#ifndef CONFIG_SIF_BMS_EN
static __s32 __bms_sif_data_proc(void)
{
	static __u32 delay_cnt = 0;
	__u32 cur_elec = 0;
	static __u32 last_volt = 0;
	__u32 cur_volt = 0 , volt_l = 0, volt_h = 0;

	if(!delay_cnt || delay_cnt > 2)	//2个电池发送数据周期更新一次数据
	{
	#if 0
		{
			__u32 i = 0;
			eLIBs_printf("BMS SIF data : ");
			for(;i<BMS_REV_DATA_NUM;i++)
			{
				eLIBs_printf("0x%02x ",sif_drv.bms_sif_data[i]);
			}
			eLIBs_printf("\n\n");
		}
	#endif
#if defined(CONFIG_FORZA_SKZJTDQR0013_USER)
		//电量
		cur_elec = sif_drv.bms_sif_data[2];
		if(last_bms_elec != cur_elec)
		{
			//eLIBs_printf("cur_elec = %d\n",cur_elec);
			__call_app(SIF_CB_INFO_ELEC, &cur_elec);
			last_bms_elec = cur_elec;
		}
		//电压
		volt_l = sif_drv.bms_sif_data[6];
		volt_h = sif_drv.bms_sif_data[7];
		cur_volt = (volt_h<<8)|volt_l;
		if(last_volt != cur_volt)
		{
			//eLIBs_printf("cur_volt = %d\n",cur_volt);
			__call_app(SIF_CB_INFO_VOLT, &cur_volt);
			last_volt = cur_volt;
		}
#else
#if defined(CONFIG_FORZA_SKZJTJQX_USER) || defined(CONFIG_FORZA_SKZJTDQR04_USER)
		//电量
		cur_elec = sif_drv.bms_sif_data[2];
#else
		//电量
		cur_elec = sif_drv.bms_sif_data[1];
#endif
		if(last_bms_elec != cur_elec)
		{
			__call_app(SIF_CB_INFO_ELEC, &cur_elec);
			last_bms_elec = cur_elec;
		}
#endif
		delay_cnt = 0;
	}
	delay_cnt++;

	return EPDK_OK;
}
#endif

static void __data_get_task(void *p_arg)
{
	__u8 i = 0;
	__u8 j = 0;
	__u8 k = 0;
	__u32 proc_data[REV_DATA_NUM][REV_BIT_NUM*2];
	__u8 temp_data[REV_DATA_NUM];
	__u8 check_sum = 0;
#ifndef CONFIG_SIF_BMS_EN
	__u32 bms_proc_data[BMS_REV_DATA_NUM][REV_BIT_NUM*2];
	__u8 bms_temp_data[BMS_REV_DATA_NUM];
	__u8 bms_check_sum = 0;
#endif
	
	while (1)
	{
		if (esKRNL_TDelReq(EXEC_prioself) == OS_TASK_DEL_REQ)
		{
			goto EXIT_TASK;
		}

		if(sif_drv.if_data_proc_flag)
		{
			//处理收到的数据
			eLIBs_memset(proc_data,0,sizeof(proc_data));
			eLIBs_memset(temp_data,0,sizeof(temp_data));

			//eLIBs_printf("------------------------FZ-sif----------------------------\n");
			for(i=0;i<REV_DATA_NUM;i++)
			{
				for(j=0;j<REV_BIT_NUM*2;j++)
				{
					proc_data[i][j] = sif_drv.recv_data[i*REV_BIT_NUM*2+j];
			//		eLIBs_printf("%d ",proc_data[i][j]);
				}
			//	eLIBs_printf("\n");

				for(j=0;j<REV_BIT_NUM*2;j+=2)
				{
					if(proc_data[i][j] && proc_data[i][j+1])
					{
						if(proc_data[i][j] <= proc_data[i][j+1])
						{
							setbit(temp_data[i],(7-j/2));
						}
						else
						{
							clrbit(temp_data[i],(7-j/2));
						}
					}
				}
				
			//	eLIBs_printf("temp_data[%d] = 0x%02x\n",i,temp_data[i]);
			}
			//eLIBs_printf("----------------------------------------------------\n\n");
			
			//数据校验
			check_sum = 0;
			for(k=0;k<(REV_DATA_NUM-2);k++)
			{
				if(!k)
				{
					check_sum = temp_data[k] ^ temp_data[k+1];
				}
				else
				{
					check_sum ^= temp_data[k+1];
				}
			}
			
			//eLIBs_printf("check_sum = 0x%02x\n",check_sum);
			if((check_sum == temp_data[REV_DATA_NUM-1]) && (temp_data[0] == DEVICE_CODE) && (temp_data[1] == SEQ_CODE))
			{
			//	eLIBs_printf("check data correct!\n");
				eLIBs_memset(sif_drv.sif_data,0,sizeof(sif_drv.sif_data));
				//eLIBs_printf("SIF data : ");
				for(k=0;k<REV_DATA_NUM;k++)
				{
					sif_drv.sif_data[k] = temp_data[k];
					//eLIBs_printf("0x%02x ",sif_drv.sif_data[k]);
				
				}
				//eLIBs_printf("\n\n");
				__sif_data_proc();
			}
			else
			{
				eLIBs_printf("fz check data error!\n");
			}
			
			sif_drv.if_data_proc_flag = 0;
		}

#ifndef CONFIG_SIF_BMS_EN
		if(sif_drv.if_bms_data_proc_flag)
		{
			//处理收到BMS的数据
			eLIBs_memset(bms_proc_data,0,sizeof(bms_proc_data));
			eLIBs_memset(bms_temp_data,0,sizeof(bms_temp_data));

		//	eLIBs_printf("---------------------------SIFfz-bms-------------------------\n");
			for(i=0;i<BMS_REV_DATA_NUM;i++)
			{
				for(j=0;j<REV_BIT_NUM*2;j++)
				{
					bms_proc_data[i][j] = sif_drv.bms_recv_data[i*REV_BIT_NUM*2+j];
					//eLIBs_printf("%d ",bms_proc_data[i][j]);
				}
				//eLIBs_printf("\n");

				for(j=0;j<REV_BIT_NUM*2;j+=2)
				{
					if(bms_proc_data[i][j] && bms_proc_data[i][j+1])
					{
						if(bms_proc_data[i][j] <= bms_proc_data[i][j+1])
						{
							setbit(bms_temp_data[i],(7-j/2));
						}
						else
						{
							clrbit(bms_temp_data[i],(7-j/2));
						}
					}
				}
				
				//eLIBs_printf("bms_temp_data[%d] = 0x%02x\n",i,bms_temp_data[i]);
			}
			//eLIBs_printf("----------------------------------------------------\n\n");
			
			//数据校验
			bms_check_sum = 0;
			for(k=0;k<BMS_REV_DATA_NUM-1;k++)
			{
				bms_check_sum += bms_temp_data[k];
			}
			
			//eLIBs_printf("bms_check_sum = 0x%02x\n",bms_check_sum);
			if((bms_check_sum == bms_temp_data[BMS_REV_DATA_NUM-1])
#if defined(CONFIG_FORZA_SKZJTDQR0013_USER)
				&& (bms_temp_data[0] == DEVICE_CODE)
#endif
				)
			{
				//eLIBs_printf("bms_check data correct!\n");
				eLIBs_memset(sif_drv.bms_sif_data,0,sizeof(sif_drv.bms_sif_data));
				//eLIBs_printf("1111BMS SIF data : \n");
				for(k=0;k<BMS_REV_DATA_NUM;k++)
				{
					sif_drv.bms_sif_data[k] = bms_temp_data[k];
				//	eLIBs_printf("0x%02x ",sif_drv.bms_sif_data[k]);
				}
				//eLIBs_printf("\n\n");
				__bms_sif_data_proc();
			}
			else
			{
				eLIBs_printf("fz bms check data error!\n");
			}
			
			sif_drv.if_bms_data_proc_flag = 0;
		}
#endif
		
		esKRNL_TimeDly(5);
	}
	
EXIT_TASK:
	__msg("data proc task delete");
	esKRNL_TDel(EXEC_prioself);
}

static void __data_get_task_init(void)
{
	if(!sif_drv.data_proc_th)
	{
		sif_drv.data_proc_th = esKRNL_TCreate(__data_get_task, NULL, 0x1000, KRNL_priolevel4);
		if(sif_drv.data_proc_th)
		{
			__msg("__data_get_task_init ok!\n");
		}
	}
}

static void __data_get_task_exit(void)
{
	if(sif_drv.data_proc_th > 0)
	{
		int i = 0;
		do
		{
			esKRNL_TimeDlyResume(sif_drv.data_proc_th);
			esKRNL_TimeDly(1);
			++i;
			if (i == 100)
			{
				__err("wait data get task exit failed, kill it!!");
				esKRNL_TDel(sif_drv.data_proc_th);
				break;
			}
		} while (OS_TASK_NOT_EXIST != esKRNL_TDelReq(sif_drv.data_proc_th));
		sif_drv.data_proc_th = 0;
	}
}

static __s32 __isr_task_pio(void *arg)
{
	__u32 temp_data = 0;
	static __u8 data_cnt = 0;

    if(NULL == sif_drv.hirq)
    {
        return EPDK_FAIL;
    }

	if(sif_drv.start_flag)
	{
		temp_data = sif_drv.cur_timer_cnt-sif_drv.last_timer_cnt;
		//eLIBs_printf("%d\n",temp_data);

		if(sif_drv.if_data_proc_flag == 0)
		{
			if(sif_drv.recv_state == INITIAL_STATE)
			{
				if(temp_data >= (SYNC_TIME_NUM*7)/10)		//"*7"和"/10"根据实际数据而定
				{
					sif_drv.recv_state = SYNC_L_STATE;
					data_cnt = 0;
					//eLIBs_printf("sync l:%d\n",temp_data);
				}
			}
			else if(sif_drv.recv_state == SYNC_L_STATE)
			{
				sif_drv.recv_state = SYNC_H_STATE;
				//eLIBs_printf("sync h:%d\n",temp_data);
			}
			else if(sif_drv.recv_state == SYNC_H_STATE)
			{
				data_cnt = 0;
				eLIBs_memset(sif_drv.recv_data,0,sizeof(sif_drv.recv_data));
				sif_drv.recv_state = DATA_REV_STATE;
			}
			
			if(sif_drv.recv_state == DATA_REV_STATE)
			{
				if(data_cnt < (REV_BIT_NUM*REV_DATA_NUM*2))
				{
					//eLIBs_printf("recv_data[%d]:%d\n",data_cnt,temp_data);
					sif_drv.recv_data[data_cnt++] = temp_data;
					if(data_cnt >= (REV_BIT_NUM*REV_DATA_NUM*2))
					{
						//eLIBs_printf("data recv finish,data_cnt=%d\n",data_cnt);
						data_cnt = 0;
						sif_drv.recv_state = INITIAL_STATE;
						sif_drv.cur_timer_cnt = 0;
						sif_drv.if_data_proc_flag = 1;
						sif_drv.sif_data_cnt = 0;
					}
				}
				else
				{
					data_cnt = 0;
					sif_drv.recv_state = INITIAL_STATE;
				}
			}
		}

		sif_drv.last_timer_cnt = sif_drv.cur_timer_cnt;
	}

	return EPDK_OK;
}

static __s32 __irq_init(void)
{
    //中断IO口初始化
    __s32 ret;
    __hdle hdl;
    user_gpio_set_t  gpio_set[1];

    ret = esCFG_GetKeyValue("sif_para", "sif_irq", (int *)gpio_set, sizeof(user_gpio_set_t)/4);
    if (EPDK_FAIL == ret)
    {
        __wrn("read cfg file fail:user_para int...\n");
        return EPDK_FAIL;
    }
    else
    {
		sif_drv.hirq = esPINS_PinGrpReq(gpio_set, 1);
		if (!sif_drv.hirq)
		{
			__wrn("request sif_irq pin failed\n");
			return EPDK_FAIL;
		}
	}

	if(sif_drv.hirq)
	{
		if(esPINS_SetIntMode(sif_drv.hirq, 3) != EPDK_OK) 	//IRQ_TYPE_EDGE_BOTH
		{
			__wrn("set irq mode failed!!!\n");
		}
		
		//register pin int handler
		ret = esPINS_RegIntHdler(sif_drv.hirq, (__pCBK_t)__isr_task_pio, NULL);
		if(ret == EPDK_OK)
		{
			ret = esPINS_EnbaleInt(sif_drv.hirq); 
			if(ret != EPDK_OK)
			{
				__wrn("enable irq failed!!!\n");
			}
			else
			{
				__msg("__irq_init ok!\n");
			}
		}
		else
		{
			__wrn("reg irq hdl failed!!!\n");
		}
	}

	return EPDK_OK;
}

static __s32 __irq_exit(void)
{
    if(sif_drv.hirq)
    {
        esPINS_DisbaleInt(sif_drv.hirq);
        esPINS_UnregIntHdler(sif_drv.hirq, NULL);
        esPINS_PinGrpRel(sif_drv.hirq, 0);
        sif_drv.hirq = NULL;
    }

    return EPDK_OK;
}

//电池BMS中断
/*
根据协议如下:
						
									 -----
1、起始码 : _________________________|   |
					   62ms			  2ms
								  
                       
					  -----
2、数据0 : 	__________|	  |		
				4ms    2ms
	
                     
				  ---------
3、数据1 : 	______|	      |		
			  2ms    4ms

*/
#ifndef CONFIG_SIF_BMS_EN
static __s32 __bms_isr_task_pio(void *arg)
{
	__u32 temp_data = 0;
	static __u8 data_cnt = 0;

    if(NULL == sif_drv.bms_hirq)
    {
        return EPDK_FAIL;
    }

	if(sif_drv.start_flag)
	{
		temp_data = sif_drv.bms_cur_timer_cnt-sif_drv.bms_last_timer_cnt;
		//eLIBs_printf("%d\n",temp_data);

		if(sif_drv.if_bms_data_proc_flag == 0)
		{			
			if(sif_drv.bms_recv_state == INITIAL_STATE)
			{
#if defined(CONFIG_FORZA_SKZJTDQR0013_USER)
				if(temp_data >= (SYNC_TIME_NUM*7)/10)	
#else
				if(temp_data >= 1000 && temp_data <=1600)		//依据协议判断起始状态位
#endif
				{
					sif_drv.bms_recv_state = SYNC_L_STATE;
					data_cnt = 0;
					//eLIBs_printf("bms sync l:%d\n",temp_data);
				}
			}
			else if(sif_drv.bms_recv_state == SYNC_L_STATE)
			{
				sif_drv.bms_recv_state = SYNC_H_STATE;
				//eLIBs_printf("bms sync h:%d\n",temp_data);
			}
			else if(sif_drv.bms_recv_state == SYNC_H_STATE)
			{
				data_cnt = 0;
				eLIBs_memset(sif_drv.bms_recv_data,0,sizeof(sif_drv.bms_recv_data));
				sif_drv.bms_recv_state = DATA_REV_STATE;
			}
			
			if(sif_drv.bms_recv_state == DATA_REV_STATE)
			{
				if(data_cnt < (REV_BIT_NUM*BMS_REV_DATA_NUM*2))
				{
					sif_drv.bms_recv_data[data_cnt++] = temp_data;
					if(data_cnt >= (REV_BIT_NUM*BMS_REV_DATA_NUM*2))
					{
						//eLIBs_printf("bms data recv finish,data_cnt=%d\n",data_cnt);
						data_cnt = 0;
						sif_drv.bms_recv_state = INITIAL_STATE;
						sif_drv.bms_cur_timer_cnt = 0;
						sif_drv.if_bms_data_proc_flag = 1;
						sif_drv.bms_sif_data_cnt = 0;
					}
				}
				else
				{
					data_cnt = 0;
					sif_drv.bms_recv_state = INITIAL_STATE;
				}
			}
		}

		sif_drv.bms_last_timer_cnt = sif_drv.bms_cur_timer_cnt;
	}

	return EPDK_OK;
}

static __s32 __bms_irq_init(void)
{
    //BMS中断IO口初始化
    __s32 ret;
    __hdle hdl;
    user_gpio_set_t  gpio_set[1];

    ret = esCFG_GetKeyValue("sif_para", "bms_sif_irq", (int *)gpio_set, sizeof(user_gpio_set_t)/4);
    if (EPDK_FAIL == ret)
    {
        __wrn("read cfg file fail:user_para int...\n");
        return EPDK_FAIL;
    }
    else
    {
		sif_drv.bms_hirq = esPINS_PinGrpReq(gpio_set, 1);
		if (!sif_drv.bms_hirq)
		{
			__wrn("request bms_sif_irq pin failed\n");
			return EPDK_FAIL;
		}
	}

	if(sif_drv.bms_hirq)
	{
		if(esPINS_SetIntMode(sif_drv.bms_hirq, 3) != EPDK_OK) 	//IRQ_TYPE_EDGE_BOTH
		{
			__wrn("set irq mode failed!!!\n");
		}
		
		//register pin int handler
		ret = esPINS_RegIntHdler(sif_drv.bms_hirq, (__pCBK_t)__bms_isr_task_pio, NULL);
		if(ret == EPDK_OK)
		{
			ret = esPINS_EnbaleInt(sif_drv.bms_hirq); 
			if(ret != EPDK_OK)
			{
				__wrn("enable irq failed!!!\n");
			}
			else
			{
				__wrn("__irq_init ok!\n");
			}
		}
		else
		{
			__wrn("reg irq hdl failed!!!\n");
		}
	}

	return EPDK_OK;
}

static __s32 __bms_irq_exit(void)
{
    if(sif_drv.bms_hirq)
    {
        esPINS_DisbaleInt(sif_drv.bms_hirq);
        esPINS_UnregIntHdler(sif_drv.bms_hirq, NULL);
        esPINS_PinGrpRel(sif_drv.bms_hirq, 0);
        sif_drv.bms_hirq = NULL;
    }

    return EPDK_OK;
}
#endif

__s32 sif_init(void)
{
	if(!sif_drv.sem1)
	{
		sif_drv.sem1 = esKRNL_SemCreate(1);
	}
	if(!sif_drv.sem2)
	{
		sif_drv.sem2 = esKRNL_SemCreate(1);
	}

	sif_drv.recv_state = INITIAL_STATE;
	eLIBs_memset(sif_drv.recv_data,0,sizeof(sif_drv.recv_data));
	eLIBs_memset(sif_drv.sif_data,0,sizeof(sif_drv.sif_data));
#ifndef CONFIG_SIF_BMS_EN
	sif_drv.bms_recv_state = INITIAL_STATE;
	eLIBs_memset(sif_drv.bms_recv_data,0,sizeof(sif_drv.bms_recv_data));
	eLIBs_memset(sif_drv.bms_sif_data,0,sizeof(sif_drv.bms_sif_data));
#endif

	//创建数据获取线程
	__data_get_task_init();

	//创建硬件定时器
	__hw_timer_init();

	//控制器一线通数据中断
	__irq_init();
	
	//电池一线通数据中断
#ifdef CONFIG_SIF_BMS_EN
	sif_bms_init();
#else
	__bms_irq_init();
#endif
	
#ifdef SIF_SEND_DATA_TEST
	__hw_timer2_init();
	__io_init();
#endif
	return EPDK_OK;
}

__s32 sif_exit(void)
{
	__u8 err;
	
	sif_drv.app_cb = NULL;
	sif_drv.app_ctx = NULL;
	
	if(sif_drv.sem1)
	{
		esKRNL_SemDel(sif_drv.sem1, 0, &err);
		sif_drv.sem1 = 0;
	}
	if(sif_drv.sem2)
	{
		esKRNL_SemDel(sif_drv.sem2, 0, &err);
		sif_drv.sem2 = 0;
	}

	//删除数据获取线程
	__data_get_task_exit();

	//删除硬件定时器
	__hw_timer_exit();

	__irq_exit();
#ifdef CONFIG_SIF_BMS_EN
	sif_bms_exit();
#else
	__bms_irq_exit();
#endif
	
#ifdef SIF_SEND_DATA_TEST
	__hw_timer2_exit();
	__io_exit();
#endif
	return EPDK_OK;
}

