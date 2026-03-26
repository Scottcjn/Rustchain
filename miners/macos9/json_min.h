/*
 * json_min.h - Minimal JSON Parser
 * 
 * Minimal RFC 8259-compatible JSON parser for RustChain attestation
 * payloads. Handles: objects {}, arrays [], strings "", numbers,
 * booleans, null. No allocations beyond initial buffer.
 * 
 * Compatible with: CodeWarrior, MPW, GCC, MSVC.
 * No external dependencies.
 */

#ifndef JSON_MIN_H
#define JSON_MIN_H

#include <stddef.h>

/* JSON value types */
typedef enum {
    JSON_NULL    = 0,
    JSON_BOOL    = 1,
    JSON_NUMBER  = 2,
    JSON_STRING  = 3,
    JSON_ARRAY   = 4,
    JSON_OBJECT  = 5
} JsonType;

/* JSON value - stores parsed result */
typedef struct {
    JsonType   type;
    union {
        double      num;      /* JSON_NUMBER */
        int         bol;      /* JSON_BOOL   */
        char       *str;      /* JSON_STRING (points into buffer) */
        void       *obj;      /* JSON_OBJECT / JSON_ARRAY (opaque) */
    } val;
} JsonVal;

/* JSON object key-value pair iterator */
typedef struct {
    char       *key;
    JsonVal     value;
} JsonPair;

/* JSON parser context */
typedef struct {
    char       *buf;          /* Input buffer (not owned) */
    size_t      len;          /* Buffer length */
    size_t      pos;          /* Current parse position */
    char       *err;          /* Error message (not owned) */
} JsonParser;

/* Parser lifecycle */
void  JsonParser_Init(JsonParser *p, char *buf, size_t len);
int   JsonParser_Parse(JsonParser *p, JsonVal *out);
void  JsonParser_Free(JsonVal *v);  /* No-op for our use */

/* Navigate parsed JSON */
JsonVal JsonObject_Get(JsonVal obj, const char *key);
JsonVal JsonArray_Get(JsonVal arr, int index);
int     JsonVal_IsNull(JsonVal v);
int     JsonVal_IsTrue(JsonVal v);
double  JsonVal_Number(JsonVal v);
char   *JsonVal_String(JsonVal v);

/* Serialize (for building requests) */
int  json_put_object_start(char *buf, size_t cap, size_t *pos);
int  json_put_object_end(char *buf, size_t cap, size_t *pos);
int  json_put_array_start(char *buf, size_t cap, size_t *pos);
int  json_put_array_end(char *buf, size_t cap, size_t *pos);
int  json_put_string(char *buf, size_t cap, size_t *pos, const char *s);
int  json_put_number(char *buf, size_t cap, size_t *pos, double n);
int  json_put_bool(char *buf, size_t cap, size_t *pos, int b);
int  json_put_null(char *buf, size_t cap, size_t *pos);
int  json_put_key(char *buf, size_t cap, size_t *pos, const char *key);

#endif /* JSON_MIN_H */
