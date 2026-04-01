#ifndef BMS_FAULT_INJECTION_H
#define BMS_FAULT_INJECTION_H

/**
 * Fault injection interface — HIL / unit-test use only.
 * Compiled-in only when BMS_FAULT_INJECTION_ENABLED is defined.
 * Production builds get no-op stubs.
 */

#include "bms_types.h"

#ifdef BMS_FAULT_INJECTION_ENABLED

typedef enum {
    FI_NONE           = 0x00,
    FI_CELL_OV        = 0x01,  /* clamp cell N to 4300 mV          */
    FI_CELL_UV        = 0x02,  /* clamp cell N to 2700 mV          */
    FI_OVERCURRENT    = 0x03,  /* override pack current to 55000 mA */
    FI_OVERTEMP       = 0x04,  /* override sensor N to 650 (65.0°C) */
    FI_UNDERTEMP      = 0x05,  /* override sensor N to -250         */
    FI_ADC_STUCK      = 0x06,  /* ADC returns BMS_TIMEOUT           */
    FI_COMM_LOSS      = 0x07,  /* CAN send returns BMS_ERROR        */
    FI_CONTACTOR_WELD = 0x08,  /* open command ignored              */
    FI_PRECHARGE_FAIL = 0x09   /* precharge voltage never rises     */
} fi_type_t;

typedef struct {
    fi_type_t type;
    uint8_t   target_index;    /* cell / sensor index (if applicable) */
    int32_t   override_value;  /* injected value in native units      */
    uint32_t  duration_ms;     /* 0 = persistent                      */
    uint32_t  activate_at_ms;  /* abs tick, 0 = immediate             */
} fi_descriptor_t;

void    fi_inject(const fi_descriptor_t *desc);
void    fi_clear(fi_type_t type);
void    fi_clear_all(void);
bool    fi_is_active(fi_type_t type);
int32_t fi_get_override(fi_type_t type, uint8_t index);
void    fi_tick(uint32_t now_ms);

#else /* production stubs */

#define fi_inject(d)         do {} while (0)
#define fi_clear(t)          do {} while (0)
#define fi_clear_all()       do {} while (0)
#define fi_is_active(t)      (false)
#define fi_get_override(t,i) (0)
#define fi_tick(n)           do {} while (0)

#endif /* BMS_FAULT_INJECTION_ENABLED */

#endif /* BMS_FAULT_INJECTION_H */
