#ifndef OPENSMASH_CB_CAPTURE_LIMITS_H
#define OPENSMASH_CB_CAPTURE_LIMITS_H
/* Measured startup exceeded the inherited 512 records. This remains a bounded
 * inventory, not a full-roster guarantee; overflow must refuse capture. */
#define CB_CAPTURE_MAX 1024
#endif
