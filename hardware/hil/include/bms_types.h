#ifndef BMS_TYPES_H
#define BMS_TYPES_H

#include <stdint.h>
#include <stdbool.h>

/* ── Cell / pack limits ─────────────────────────────────────────────── */
#define BMS_MAX_CELLS             16U
#define BMS_MAX_TEMP_SENSORS       8U
#define BMS_CELL_OV_THRESHOLD_MV   4200U
#define BMS_CELL_UV_THRESHOLD_MV   2800U
#define BMS_OC_THRESHOLD_MA       50000U   /* 50 A */
#define BMS_MAX_TEMP_DEG_C_X10     600     /* 60.0 °C */
#define BMS_MIN_TEMP_DEG_C_X10   (-200)   /* -20.0 °C */
#define BMS_BAL_THRESHOLD_MV       20U
#define BMS_ADC_TIMEOUT_MS         10U

typedef enum {
    BMS_STATE_INIT        = 0x00U,
    BMS_STATE_IDLE        = 0x01U,
    BMS_STATE_CHARGING    = 0x02U,
    BMS_STATE_DISCHARGING = 0x03U,
    BMS_STATE_FAULT       = 0x04U,
    BMS_STATE_SHUTDOWN    = 0x05U
} bms_state_t;

typedef enum {
    BMS_FAULT_NONE         = 0x00000000U,
    BMS_FAULT_OVERVOLTAGE  = 0x00000001U,
    BMS_FAULT_UNDERVOLTAGE = 0x00000002U,
    BMS_FAULT_OVERCURRENT  = 0x00000004U,
    BMS_FAULT_OVERTEMP     = 0x00000008U,
    BMS_FAULT_UNDERTEMP    = 0x00000010U,
    BMS_FAULT_COMM         = 0x00000020U,
    BMS_FAULT_ADC          = 0x00000040U,
    BMS_FAULT_INTERNAL     = 0x00000080U,
    BMS_FAULT_BALANCER     = 0x00000100U,
    BMS_FAULT_PRECHARGE    = 0x00000200U
} bms_fault_t;

typedef struct {
    uint16_t cell_voltage_mv[BMS_MAX_CELLS];
    int16_t  temperature_degc_x10[BMS_MAX_TEMP_SENSORS];
    int32_t  pack_current_ma;      /* positive = discharge */
    uint16_t pack_voltage_mv;
    uint8_t  soc_percent;          /* 0-100 */
    uint8_t  soh_percent;          /* 0-100 */
    bms_state_t  state;
    uint32_t     fault_flags;
    uint32_t     timestamp_ms;
} bms_data_t;

typedef struct {
    uint8_t  num_cells;
    uint8_t  num_temp_sensors;
    uint16_t cell_capacity_mah;
    uint16_t ov_threshold_mv;
    uint16_t uv_threshold_mv;
    uint32_t oc_threshold_ma;
    int16_t  max_temp_degc_x10;
    int16_t  min_temp_degc_x10;
    uint32_t balancing_threshold_mv;
} bms_config_t;

typedef enum {
    BMS_OK      = 0x00U,
    BMS_ERROR   = 0x01U,
    BMS_BUSY    = 0x02U,
    BMS_TIMEOUT = 0x03U
} bms_status_t;

#endif /* BMS_TYPES_H */
