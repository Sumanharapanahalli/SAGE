/**
 * @file ble_gatt.h
 * @brief BLE GATT custom service for caregiver app pairing.
 *
 * Custom service UUID: 12345678-1234-5678-1234-56789ABCDEF0
 * Characteristics:
 *   - Device Status  (notify, 20 B)  — SOC, fall state, GPS fix
 *   - Alert Config   (write, 8 B)    — alert thresholds, caregiver phone
 *   - OTA Control    (write, 4 B)    — initiate/abort OTA session
 *   - Audit Replay   (read/notify)   — stream recent audit entries
 *
 * SRS-007  BLE discoverable, pairs within 30 s.
 * Security: BLE Secure Connections (LE Secure Connections, Numeric Comparison).
 *
 * @version 1.0.0
 */

#ifndef BLE_GATT_H
#define BLE_GATT_H

#include <stdint.h>
#include <stdbool.h>
#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/gatt.h>

#ifdef __cplusplus
extern "C" {
#endif

/* -------------------------------------------------------------------------
 * Custom service and characteristic UUIDs
 * ------------------------------------------------------------------------- */
/* Service: 12345678-1234-5678-1234-56789ABCDEF0 */
#define BLE_SVC_UUID_CAREGIVER \
    BT_UUID_DECLARE_128(BT_UUID_128_ENCODE(0x12345678U, 0x1234U, 0x5678U, \
                                           0x1234U, 0x56789ABCDEF0ULL))

/* Device Status characteristic: UUID ...DEF1 */
#define BLE_CHAR_UUID_STATUS \
    BT_UUID_DECLARE_128(BT_UUID_128_ENCODE(0x12345678U, 0x1234U, 0x5678U, \
                                           0x1234U, 0x56789ABCDEF1ULL))

/* Alert Config characteristic: UUID ...DEF2 */
#define BLE_CHAR_UUID_ALERT_CFG \
    BT_UUID_DECLARE_128(BT_UUID_128_ENCODE(0x12345678U, 0x1234U, 0x5678U, \
                                           0x1234U, 0x56789ABCDEF2ULL))

/* OTA Control characteristic: UUID ...DEF3 */
#define BLE_CHAR_UUID_OTA_CTRL \
    BT_UUID_DECLARE_128(BT_UUID_128_ENCODE(0x12345678U, 0x1234U, 0x5678U, \
                                           0x1234U, 0x56789ABCDEF3ULL))

/* Audit Replay characteristic: UUID ...DEF4 */
#define BLE_CHAR_UUID_AUDIT \
    BT_UUID_DECLARE_128(BT_UUID_128_ENCODE(0x12345678U, 0x1234U, 0x5678U, \
                                           0x1234U, 0x56789ABCDEF4ULL))

/* -------------------------------------------------------------------------
 * Status notification payload (packed, 20 bytes)
 * ------------------------------------------------------------------------- */
typedef struct __attribute__((packed)) ble_status_notif {
    uint8_t  soc_pct;           /**< Battery SOC 0–100 %               */
    uint8_t  fall_state;        /**< fall_state_t cast to uint8_t       */
    uint8_t  gps_valid;         /**< 1 if GPS fix cached and valid      */
    int32_t  latitude_mdeg;     /**< Last GPS latitude millidegrees     */
    int32_t  longitude_mdeg;    /**< Last GPS longitude millidegrees    */
    uint8_t  lte_state;         /**< lte_state_t cast to uint8_t        */
    uint8_t  fw_major;          /**< Firmware version major             */
    uint8_t  fw_minor;          /**< Firmware version minor             */
    uint8_t  fw_patch;          /**< Firmware version patch             */
    uint8_t  reserved[2];       /**< Pad to 20 bytes                    */
} ble_status_notif_t;

BUILD_ASSERT(sizeof(ble_status_notif_t) == 20U, "BLE status notif must be 20B");

/* -------------------------------------------------------------------------
 * Public API
 * ------------------------------------------------------------------------- */

/**
 * @brief Initialise BLE stack and register custom GATT service.
 *
 * Starts advertising with device name "SAGE-Wearable-XXXX" (last 2B of MAC).
 * Secure connections required; no legacy pairing accepted.
 *
 * @return 0 on success, negative errno on BT stack init failure.
 */
int ble_gatt_init(void);

/**
 * @brief Send device status notification to connected caregiver client.
 *
 * No-op if no client connected or notifications not subscribed.
 * Thread-safe: marshalled through g_ble_notify_q.
 *
 * @return 0 on success, -ENOTCONN if no subscriber.
 */
int ble_gatt_notify_status(void);

/**
 * @brief Send fall alert notification to connected caregiver client.
 *
 * @param p_fix  GPS fix at time of fall (may be NULL if no fix available).
 * @return 0 on success, -ENOTCONN if no subscriber.
 */
int ble_gatt_notify_fall(const gps_fix_t *p_fix);

/**
 * @brief Return true if a caregiver client is currently connected.
 */
bool ble_gatt_is_connected(void);

/**
 * @brief Stop advertising and disconnect any active connection.
 *
 * Called during shutdown sequence.
 */
void ble_gatt_stop(void);

#ifdef __cplusplus
}
#endif

#endif /* BLE_GATT_H */
