
#include <mod_obd.h>
#include "drv_obd_i.h"

void * obd_api_get_sys_state_ptr(void)
{
	return (void *)&drv_obd.obd_info;
}

const obd_mod_api_entry_t obd_api __attribute__((section("OBD_API_TBL")))=
{
	obd_api_get_sys_state_ptr,
};

