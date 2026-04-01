/**
 * @file ota_update.h
 * @brief OTA firmware update via MCUboot — slot management and verification.
 *
 * Uses MCUboot A/B (ping-pong) flash layout.  New image is written to
 * slot-1 (secondary) via BLE DFU or LTE cloud download.  On reboot,
 * MCUboot verifies ECDSA-P256 signature; if valid, swaps to new image.
 * If new image fails to call boot_write_img_confirmed() within
 * CONFIG_BOOT_REVERT_TIMEOUT, MCUboot reverts to slot-0.
 *
 * SRS-008  OTA update uses MCUboot verified boot; invalid images rejected.
 *
 * @version 1.0.0
 */

#ifndef OTA_UPDATE_H
#define OTA_UPDATE_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* -------------------------------------------------------------------------
 * OTA session state
 * ------------------------------------------------------------------------- */
typedef enum ota_state {
    OTA_STATE_IDLE       = 0,
    OTA_STATE_STARTED    = 1,  /**< Session open, receiving image chunks   */
    OTA_STATE_WRITING    = 2,  /**< Writing chunks to secondary slot        */
    OTA_STATE_VERIFYING  = 3,  /**< MCUboot verifying image hash/signature  */
    OTA_STATE_PENDING    = 4,  /**< Image written; awaiting reboot to swap  */
    OTA_STATE_FAILED     = 5,  /**< Write or verify failed                  */
} ota_state_t;

/* -------------------------------------------------------------------------
 * Image chunk for streaming write (BLE MTU-friendly 240 B)
 * ------------------------------------------------------------------------- */
#define OTA_CHUNK_SIZE_MAX  240U

typedef struct ota_chunk {
    uint32_t offset;                  /**< Byte offset into image          */
    uint16_t len;                     /**< Valid bytes in data[]           */
    uint8_t  data[OTA_CHUNK_SIZE_MAX]; /**< Image payload chunk            */
} ota_chunk_t;

/* -------------------------------------------------------------------------
 * Public API
 * ------------------------------------------------------------------------- */

/**
 * @brief Initialise OTA subsystem.
 *
 * Checks MCUboot status; if running in test mode (unconfirmed image),
 * calls boot_write_img_confirmed() to accept the current image.
 *
 * @return 0 on success, negative errno on flash driver init failure.
 */
int ota_update_init(void);

/**
 * @brief Open a new OTA update session.
 *
 * Erases secondary flash slot.  Must be called before first chunk.
 *
 * @param image_size_bytes  Total image size (sanity check against slot size).
 * @return 0 on success, -EBUSY if session already open, -E2BIG if too large.
 */
int ota_update_begin(uint32_t image_size_bytes);

/**
 * @brief Write an image chunk to secondary slot.
 *
 * Must be called in order (ascending offset).  Validates chunk bounds.
 *
 * @param p_chunk  Chunk data; must not be NULL.
 * @return 0 on success, negative errno on flash write failure.
 */
int ota_update_write_chunk(const ota_chunk_t *p_chunk);

/**
 * @brief Finalise OTA session and request MCUboot swap on next reboot.
 *
 * Calls boot_request_upgrade(BOOT_UPGRADE_TEST) which sets the upgrade
 * pending flag in MCUboot's trailer.  Device MUST be rebooted to activate.
 * Posts EVT_OTA_COMPLETE to orchestrator.
 *
 * @return 0 on success, negative errno on flash verify failure.
 */
int ota_update_finalise(void);

/**
 * @brief Abort current OTA session and erase secondary slot.
 *
 * Posts EVT_OTA_FAILED to orchestrator.
 */
void ota_update_abort(void);

/**
 * @brief Trigger a system reboot to activate pending OTA image.
 *
 * Flushes audit log before reboot.  Does NOT return.
 */
void ota_update_reboot(void);

/**
 * @brief Return current OTA session state.
 */
ota_state_t ota_update_get_state(void);

/**
 * @brief Return bytes written so far in current session.
 */
uint32_t ota_update_bytes_written(void);

#ifdef __cplusplus
}
#endif

#endif /* OTA_UPDATE_H */
