/**
 * @file gps_parser.h
 * @brief NMEA 0183 sentence parser for elder fall detection wearable.
 *
 * Supported sentences: $GPRMC, $GPGGA
 * Validates XOR checksum. Gracefully handles malformed input.
 *
 * IEC 62304 Classification: Class B software unit
 * Software Unit ID: SU-GPS-001
 */

#ifndef GPS_PARSER_H
#define GPS_PARSER_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* -------------------------------------------------------------------------
 * Limits
 * ---------------------------------------------------------------------- */
#define GPS_SENTENCE_MAX_LEN  128
#define GPS_MAX_FIELDS         20

/* -------------------------------------------------------------------------
 * Error codes
 * ---------------------------------------------------------------------- */
typedef enum {
    GPS_OK                    = 0,
    GPS_ERR_NULL_INPUT        = 1,
    GPS_ERR_EMPTY             = 2,
    GPS_ERR_NO_DOLLAR         = 3,
    GPS_ERR_SENTENCE_TOO_LONG = 4,
    GPS_ERR_BAD_CHECKSUM      = 5,
    GPS_ERR_MISSING_CHECKSUM  = 6,
    GPS_ERR_UNKNOWN_SENTENCE  = 7,
    GPS_ERR_INSUFFICIENT_FIELDS = 8,
    GPS_ERR_INVALID_DATA      = 9,
    GPS_ERR_INVALID_LATLON    = 10,
    GPS_ERR_INVALID_TIME      = 11,
} GPSParseError;

/* -------------------------------------------------------------------------
 * Data types
 * ---------------------------------------------------------------------- */

/** Parsed GPS fix */
typedef struct {
    double   latitude;      /**< Decimal degrees, N positive      */
    double   longitude;     /**< Decimal degrees, E positive      */
    float    altitude_m;    /**< MSL altitude in metres           */
    float    speed_knots;   /**< Speed over ground in knots       */
    float    course_deg;    /**< True course in degrees           */
    float    hdop;          /**< Horizontal dilution of precision */
    uint8_t  satellites;    /**< Number of satellites in use      */
    bool     fix_valid;     /**< True if fix status is 'A'/'1'   */
    uint8_t  fix_quality;   /**< GPGGA fix quality indicator      */
    uint8_t  hour;
    uint8_t  minute;
    uint8_t  second;
    uint8_t  day;
    uint8_t  month;
    uint16_t year;
} GPSFix;

/* -------------------------------------------------------------------------
 * API
 * ---------------------------------------------------------------------- */

/**
 * @brief Parse any supported NMEA sentence into a GPSFix.
 * @param sentence  Null-terminated NMEA sentence string.
 * @param out       Output GPSFix (untouched on error).
 * @return GPS_OK on success, error code otherwise.
 */
GPSParseError gps_parse_sentence(const char *sentence, GPSFix *out);

/**
 * @brief Validate the XOR checksum of an NMEA sentence.
 * @param sentence  Null-terminated NMEA sentence (must contain '*').
 * @return true if checksum matches, false otherwise.
 */
bool gps_validate_checksum(const char *sentence);

/**
 * @brief Parse a $GPRMC sentence directly.
 * @param sentence  Full NMEA sentence string.
 * @param out       Output GPSFix.
 * @return GPS_OK on success, error code otherwise.
 */
GPSParseError gps_parse_gprmc(const char *sentence, GPSFix *out);

/**
 * @brief Parse a $GPGGA sentence directly.
 * @param sentence  Full NMEA sentence string.
 * @param out       Output GPSFix.
 * @return GPS_OK on success, error code otherwise.
 */
GPSParseError gps_parse_gpgga(const char *sentence, GPSFix *out);

/**
 * @brief Convert NMEA lat/lon format (DDDMM.MMMMM) to decimal degrees.
 * @param nmea_val   Value in DDDMM.MMMMM format.
 * @param hemisphere 'N', 'S', 'E', or 'W'.
 * @return Decimal degrees (negative for S/W), or NaN on error.
 */
double gps_nmea_to_decimal(double nmea_val, char hemisphere);

#ifdef __cplusplus
}
#endif
#endif /* GPS_PARSER_H */
