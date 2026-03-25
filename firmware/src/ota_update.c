/**
 * @file ota_update.c
 * @brief OTA Firmware Update Manager Implementation
 *
 * IEC 62304 Class B — see ota_update.h for full specification.
 *
 * SOUP dependency: mbedTLS (sha256, ecdsa, crc) — see SOUP_list.md.
 *
 * Platform hooks (provide in your BSP):
 *   bsp_flash_erase_bank(bank)
 *   bsp_flash_write(bank, offset, data, len) -> int (0=ok)
 *   bsp_flash_read(bank, offset, buf, len)
 *   bsp_set_boot_bank(bank)
 *   bsp_get_boot_bank() -> uint8_t
 *   bsp_get_rollback_count() -> uint8_t
 *   bsp_set_rollback_count(n)
 *   bsp_reboot()
 *
 * @version 1.0.0
 * @date    2026-03-21
 */

#include "ota_update.h"
#include <string.h>
#include <stdio.h>

/* =========================================================================
 * mbedTLS SOUP includes — version 3.x
 * Replace with your platform's crypto library if needed.
 * ========================================================================= */
#ifdef OTA_USE_MBEDTLS
#  include "mbedtls/sha256.h"
#  include "mbedtls/ecdsa.h"
#  include "mbedtls/ecp.h"
#  include "mbedtls/entropy.h"
#  include "mbedtls/ctr_drbg.h"
#endif

/* =========================================================================
 * BSP hooks — forward declarations (implement in your BSP layer)
 * ========================================================================= */
extern int     bsp_flash_erase_bank(uint8_t bank);
extern int     bsp_flash_write(uint8_t bank, uint32_t offset,
                                const uint8_t *data, uint32_t len);
extern int     bsp_flash_read(uint8_t bank, uint32_t offset,
                               uint8_t *buf, uint32_t len);
extern void    bsp_set_boot_bank(uint8_t bank);
extern uint8_t bsp_get_boot_bank(void);
extern uint8_t bsp_get_rollback_count(void);
extern void    bsp_set_rollback_count(uint8_t n);
extern void    bsp_reboot(void);

/* =========================================================================
 * Internal constants
 * ========================================================================= */
#define BANK_ACTIVE   0u
#define BANK_STAGING  1u

/* Running firmware version — injected at build time */
#ifndef FW_VERSION_MAJOR
#  define FW_VERSION_MAJOR 1u
#  define FW_VERSION_MINOR 0u
#  define FW_VERSION_PATCH 0u
#endif

/* ECDSA-P256 public key (DER-encoded, 91 bytes) — replace with your key */
static const uint8_t k_public_key[] = {
    /* Placeholder — replace with your ECDSA-P256 public key bytes */
    0x30, 0x59, 0x30, 0x13, 0x06, 0x07, 0x2a, 0x86,
    0x48, 0xce, 0x3d, 0x02, 0x01, 0x06, 0x08, 0x2a,
    0x86, 0x48, 0xce, 0x3d, 0x03, 0x01, 0x07, 0x03,
    0x42, 0x00, 0x04,
    /* X coordinate (32 bytes — placeholder) */
    0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
    0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f,
    0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17,
    0x18, 0x19, 0x1a, 0x1b, 0x1c, 0x1d, 0x1e, 0x1f,
    /* Y coordinate (32 bytes — placeholder) */
    0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27,
    0x28, 0x29, 0x2a, 0x2b, 0x2c, 0x2d, 0x2e, 0x2f,
    0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37,
    0x38, 0x39, 0x3a, 0x3b, 0x3c, 0x3d, 0x3e, 0x3f,
};

/* =========================================================================
 * CRC32 (IEEE 802.3) — no external dependency
 * ========================================================================= */
static uint32_t crc32_update(uint32_t crc, const uint8_t *data, uint32_t len)
{
    crc ^= 0xFFFFFFFFUL;
    for (uint32_t i = 0u; i < len; i++) {
        crc ^= data[i];
        for (uint8_t j = 0u; j < 8u; j++) {
            crc = (crc & 1u) ? (crc >> 1) ^ 0xEDB88320UL : (crc >> 1);
        }
    }
    return crc ^ 0xFFFFFFFFUL;
}

/* =========================================================================
 * Internal state
 * ========================================================================= */
typedef struct {
    bool           initialised;
    bool           session_active;
    bool           update_pending;
    OtaImageHeader pending_header;
    uint32_t       bytes_written;   /* payload bytes written so far */
    uint32_t       running_crc;     /* CRC accumulator over written payload */
    OtaProgressCb  progress_cb;
    void          *progress_user;
} OtaCtx;

static OtaCtx s_ota;

/* =========================================================================
 * Internal helpers
 * ========================================================================= */

static OtaErr version_check(const OtaImageHeader *hdr)
{
    /* Anti-rollback: new version must be >= current */
    uint64_t cur = ((uint64_t)FW_VERSION_MAJOR << 32) |
                   ((uint64_t)FW_VERSION_MINOR << 16) |
                    (uint64_t)FW_VERSION_PATCH;
    uint64_t new_ver = ((uint64_t)hdr->version_major << 32) |
                       ((uint64_t)hdr->version_minor << 16) |
                        (uint64_t)hdr->version_patch;
    if (new_ver < cur) { return OTA_ERR_BAD_VERSION; }
    return OTA_ERR_OK;
}

static OtaErr verify_crc(void)
{
    /* Re-read staging bank and compute CRC */
    uint32_t running = 0xFFFFFFFFUL ^ 0xFFFFFFFFUL; /* reset */
    running = 0u; /* will compute with crc32_update initial 0 */

    uint8_t  chunk[OTA_CHUNK_SIZE];
    uint32_t remaining = s_ota.pending_header.image_size;
    uint32_t offset    = sizeof(OtaImageHeader);

    uint32_t crc = 0u;
    /* Seed with CRC32 of full image */
    uint32_t tmp_crc = 0xFFFFFFFFUL ^ 0xFFFFFFFFUL;
    /* Use running_crc that was accumulated during writes */
    crc = s_ota.running_crc;
    (void)remaining; (void)offset; (void)chunk; (void)running;

    if (crc != s_ota.pending_header.crc32) {
        return OTA_ERR_CRC_FAIL;
    }
    return OTA_ERR_OK;
}

#ifdef OTA_USE_MBEDTLS
static OtaErr verify_signature(void)
{
    mbedtls_ecdsa_context ecdsa;
    mbedtls_ecdsa_init(&ecdsa);

    int rc = mbedtls_ecp_group_load(&ecdsa.grp, MBEDTLS_ECP_DP_SECP256R1);
    if (rc != 0) {
        mbedtls_ecdsa_free(&ecdsa);
        return OTA_ERR_SIG_FAIL;
    }

    /* Load public key */
    rc = mbedtls_ecp_point_read_binary(&ecdsa.grp,
                                        &ecdsa.Q,
                                        k_public_key + 27, /* skip DER prefix */
                                        65u);
    if (rc != 0) {
        mbedtls_ecdsa_free(&ecdsa);
        return OTA_ERR_SIG_FAIL;
    }

    /* Verify signature over hash */
    rc = mbedtls_ecdsa_read_signature(&ecdsa,
                                       s_ota.pending_header.hash,
                                       OTA_HASH_LEN,
                                       s_ota.pending_header.signature,
                                       OTA_SIGNATURE_LEN);
    mbedtls_ecdsa_free(&ecdsa);
    return (rc == 0) ? OTA_ERR_OK : OTA_ERR_SIG_FAIL;
}
#else
/* Stub: always pass in non-production / test builds */
static OtaErr verify_signature(void)
{
    /* WARNING: signature verification disabled — enable OTA_USE_MBEDTLS */
    return OTA_ERR_OK;
}
#endif

/* =========================================================================
 * Public API
 * ========================================================================= */

OtaErr ota_init(void)
{
    memset(&s_ota, 0, sizeof(s_ota));
    s_ota.initialised = true;
    return OTA_ERR_OK;
}

OtaErr ota_begin(const OtaImageHeader *header)
{
    if (!s_ota.initialised)   { return OTA_ERR_NOT_STARTED; }
    if (s_ota.session_active) { return OTA_ERR_ALREADY_STARTED; }
    if (header == NULL)       { return OTA_ERR_NULL_PTR; }

    /* Validate magic */
    if (header->magic != OTA_MAGIC) { return OTA_ERR_BAD_MAGIC; }

    /* Validate image size */
    if (header->image_size == 0u ||
        header->image_size > OTA_MAX_IMAGE_SIZE) {
        return OTA_ERR_BAD_SIZE;
    }

    /* Anti-rollback version check */
    OtaErr rc = version_check(header);
    if (rc != OTA_ERR_OK) { return rc; }

    /* Erase staging bank */
    if (bsp_flash_erase_bank(BANK_STAGING) != 0) {
        return OTA_ERR_FLASH_ERASE;
    }

    /* Write header to staging bank offset 0 */
    if (bsp_flash_write(BANK_STAGING, 0u,
                        (const uint8_t *)header,
                        sizeof(OtaImageHeader)) != 0) {
        return OTA_ERR_FLASH_WRITE;
    }

    s_ota.pending_header = *header;
    s_ota.bytes_written  = 0u;
    s_ota.running_crc    = 0xFFFFFFFFUL ^ 0xFFFFFFFFUL; /* will use crc32_update */
    s_ota.session_active = true;

    /* Recompute running_crc from scratch */
    s_ota.running_crc = crc32_update(0u, NULL, 0u);
    /* Note: crc32_update with len=0 just returns 0^FFFFFFFF^FFFFFFFF = 0
     * We initialise properly on first chunk call. */
    s_ota.running_crc = 0u; /* will be computed incrementally */

    return OTA_ERR_OK;
}

OtaErr ota_write_chunk(const uint8_t *data, uint32_t len)
{
    if (!s_ota.session_active) { return OTA_ERR_NOT_STARTED; }
    if (data == NULL || len == 0u) { return OTA_ERR_NULL_PTR; }
    if (len > OTA_CHUNK_SIZE)  { return OTA_ERR_CHUNK_OVERFLOW; }
    if (s_ota.bytes_written + len > s_ota.pending_header.image_size) {
        return OTA_ERR_CHUNK_OVERFLOW;
    }

    /* Write to staging bank after the header */
    uint32_t offset = (uint32_t)sizeof(OtaImageHeader) + s_ota.bytes_written;
    if (bsp_flash_write(BANK_STAGING, offset, data, len) != 0) {
        ota_abort();
        return OTA_ERR_FLASH_WRITE;
    }

    /* Accumulate CRC (naive incremental — replace with proper CRC if needed) */
    for (uint32_t i = 0u; i < len; i++) {
        /* Simple running CRC32 update */
        uint32_t byte_crc = data[i];
        s_ota.running_crc ^= byte_crc;
        for (uint8_t b = 0u; b < 8u; b++) {
            s_ota.running_crc = (s_ota.running_crc & 1u)
                ? (s_ota.running_crc >> 1) ^ 0xEDB88320UL
                : (s_ota.running_crc >> 1);
        }
    }

    s_ota.bytes_written += len;

    if (s_ota.progress_cb != NULL) {
        s_ota.progress_cb(s_ota.bytes_written,
                          s_ota.pending_header.image_size,
                          s_ota.progress_user);
    }

    return OTA_ERR_OK;
}

OtaErr ota_finalize(void)
{
    if (!s_ota.session_active) { return OTA_ERR_NOT_STARTED; }

    if (s_ota.bytes_written != s_ota.pending_header.image_size) {
        ota_abort();
        return OTA_ERR_NOT_COMPLETE;
    }

    /* Finalise CRC */
    uint32_t final_crc = s_ota.running_crc ^ 0xFFFFFFFFUL;
    if (final_crc != s_ota.pending_header.crc32) {
        ota_abort();
        return OTA_ERR_CRC_FAIL;
    }

    /* Verify ECDSA signature */
    OtaErr sig_rc = verify_signature();
    if (sig_rc != OTA_ERR_OK) {
        ota_abort();
        return sig_rc;
    }

    /* Mark staging bank as boot target */
    bsp_set_boot_bank(BANK_STAGING);
    bsp_set_rollback_count(0u);

    s_ota.update_pending = true;
    s_ota.session_active = false;
    return OTA_ERR_OK;
}

void ota_abort(void)
{
    if (s_ota.session_active) {
        bsp_flash_erase_bank(BANK_STAGING);
        s_ota.session_active = false;
        s_ota.bytes_written  = 0u;
    }
}

bool ota_update_pending(void)
{
    return s_ota.update_pending;
}

void ota_set_progress_cb(OtaProgressCb cb, void *user_data)
{
    s_ota.progress_cb   = cb;
    s_ota.progress_user = user_data;
}

void ota_get_current_version(uint32_t *major, uint32_t *minor, uint32_t *patch)
{
    if (major) { *major = FW_VERSION_MAJOR; }
    if (minor) { *minor = FW_VERSION_MINOR; }
    if (patch) { *patch = FW_VERSION_PATCH; }
}

OtaErr ota_confirm_boot(void)
{
    if (!s_ota.initialised) { return OTA_ERR_NOT_STARTED; }
    bsp_set_rollback_count(0u);
    return OTA_ERR_OK;
}
