/**
 * @file ble_gatt.h
 * @brief BLE GATT server attribute handling for elder fall detection wearable.
 *
 * Provides characteristic read/write/notify operations with CCCD management.
 *
 * IEC 62304 Classification: Class B software unit
 * Software Unit ID: SU-BLE-001
 */

#ifndef BLE_GATT_H
#define BLE_GATT_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* -------------------------------------------------------------------------
 * Limits
 * ---------------------------------------------------------------------- */
#define BLE_ATTR_MAX_LEN        512
#define BLE_MAX_ATTRIBUTES       16

/* -------------------------------------------------------------------------
 * Attribute properties (ORable flags)
 * ---------------------------------------------------------------------- */
#define BLE_PROP_READ           0x02U
#define BLE_PROP_WRITE          0x08U
#define BLE_PROP_WRITE_NR       0x04U  /**< Write without response */
#define BLE_PROP_NOTIFY         0x10U
#define BLE_PROP_INDICATE       0x20U

/* -------------------------------------------------------------------------
 * CCCD values
 * ---------------------------------------------------------------------- */
#define BLE_CCCD_DISABLED       0x00U
#define BLE_CCCD_NOTIFY         0x01U
#define BLE_CCCD_INDICATE       0x02U

/* -------------------------------------------------------------------------
 * Well-known characteristic handles
 * ---------------------------------------------------------------------- */
#define HANDLE_FALL_ALERT_CHAR      0x0010U  /**< Fall alert notification */
#define HANDLE_FALL_ALERT_CCCD      0x0011U  /**< CCCD for fall alert     */
#define HANDLE_LOCATION_CHAR        0x0020U  /**< GPS location data       */
#define HANDLE_LOCATION_CCCD        0x0021U  /**< CCCD for location       */
#define HANDLE_BATTERY_CHAR         0x0030U  /**< Battery level (0-100)   */
#define HANDLE_SOS_CHAR             0x0040U  /**< SOS trigger / status    */
#define HANDLE_DEVICE_STATUS_CHAR   0x0050U  /**< Device status bitmap    */
#define HANDLE_CONFIG_CHAR          0x0060U  /**< Writeable configuration */

/* -------------------------------------------------------------------------
 * Error codes
 * ---------------------------------------------------------------------- */
typedef enum {
    BLE_OK                  = 0,
    BLE_ERR_INVALID_HANDLE  = 1,
    BLE_ERR_READ_NOT_PERM   = 2,
    BLE_ERR_WRITE_NOT_PERM  = 3,
    BLE_ERR_INVALID_LENGTH  = 4,
    BLE_ERR_NOTIFY_DISABLED = 5,
    BLE_ERR_OUT_OF_MEMORY   = 6,
    BLE_ERR_NULL_PARAM      = 7,
    BLE_ERR_STACK_BUSY      = 8,
} BLEError;

/* -------------------------------------------------------------------------
 * Types
 * ---------------------------------------------------------------------- */

/** Single GATT attribute descriptor */
typedef struct {
    uint16_t handle;
    uint8_t  properties;
    uint8_t  data[BLE_ATTR_MAX_LEN];
    uint16_t data_len;
    bool     notify_enabled;
    uint8_t  cccd;
} GATTAttribute;

/** Notification callback type */
typedef void (*BLENotifyCallback)(uint16_t handle,
                                  const uint8_t *data,
                                  uint16_t len);

/* -------------------------------------------------------------------------
 * API
 * ---------------------------------------------------------------------- */

/** @brief Initialise GATT server with default attributes. */
void ble_gatt_init(void);

/**
 * @brief Read a characteristic value.
 * @param handle  Attribute handle.
 * @param buf     Output buffer.
 * @param len     In: buffer capacity; Out: bytes written.
 */
BLEError ble_gatt_read(uint16_t handle, uint8_t *buf, uint16_t *len);

/**
 * @brief Write a characteristic value.
 * @param handle  Attribute handle.
 * @param data    Data to write.
 * @param len     Length of data.
 */
BLEError ble_gatt_write(uint16_t handle, const uint8_t *data, uint16_t len);

/**
 * @brief Send a notification to a connected central.
 * @param handle  Attribute handle (must have NOTIFY property and CCCD enabled).
 * @param data    Notification payload.
 * @param len     Payload length.
 */
BLEError ble_gatt_notify(uint16_t handle, const uint8_t *data, uint16_t len);

/**
 * @brief Set CCCD value for a characteristic.
 * @param handle      Characteristic handle.
 * @param cccd_value  BLE_CCCD_DISABLED / BLE_CCCD_NOTIFY / BLE_CCCD_INDICATE.
 */
BLEError ble_gatt_set_cccd(uint16_t handle, uint8_t cccd_value);

/** @brief Returns true if notifications are enabled for this handle. */
bool ble_gatt_is_notify_enabled(uint16_t handle);

/** @brief Register notification sent callback (for test verification). */
void ble_gatt_set_notify_callback(BLENotifyCallback cb);

/** @brief Returns number of notifications sent since last reset. */
uint32_t ble_gatt_get_notify_count(void);

/** @brief Reset GATT state (clears data and counters). */
void ble_gatt_reset(void);

#ifdef __cplusplus
}
#endif
#endif /* BLE_GATT_H */
