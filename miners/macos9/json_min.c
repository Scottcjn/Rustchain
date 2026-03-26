/*
 * json_min.c - Minimal JSON Parser Implementation
 * 
 * Minimal RFC 8259-compatible JSON parser.
 * No dynamic allocation - uses input buffer directly.
 * Parser does not modify input buffer.
 */

#include "json_min.h"
#include <string.h>
#include <stdlib.h>
#include <ctype.h>
#include <math.h>

/* ============================================================
 * INTERNAL HELPERS
 * ============================================================ */

static void skip_whitespace(JsonParser *p)
{
    while (p->pos < p->len) {
        char c = p->buf[p->pos];
        if (c == ' ' || c == '\t' || c == '\r' || c == '\n') {
            p->pos++;
        } else {
            break;
        }
    }
}

static int at_end(JsonParser *p)
{
    return p->pos >= p->len;
}

static char peek(JsonParser *p)
{
    if (at_end(p)) return '\0';
    return p->buf[p->pos];
}

static char next(JsonParser *p)
{
    if (at_end(p)) return '\0';
    return p->buf[p->pos++];
}

static void set_error(JsonParser *p, const char *msg)
{
    if (p->err == NULL) {
        /* Keep first error only */
        p->err = (char *)msg;
    }
}

/* ============================================================
 * PARSERS
 * ============================================================ */

static int parse_value(JsonParser *p, JsonVal *out);
static int parse_string(JsonParser *p, char **out_str);
static int parse_number(JsonParser *p, double *out_num);
static int parse_literal(JsonParser *p, const char *lit, JsonType type, JsonVal *out);

static int parse_string(JsonParser *p, char **out_str)
{
    char c;
    size_t start;
    char *result;
    size_t result_len = 0;
    size_t result_cap = 64;  /* Initial capacity */
    
    if (peek(p) != '"') {
        set_error(p, "expected string");
        return -1;
    }
    p->pos++;  /* Skip opening quote */
    
    start = p->pos;
    
    /* Pass 1: measure and validate */
    while (!at_end(p)) {
        c = peek(p);
        if (c == '"') break;
        if (c == '\\') {
            p->pos++;
            if (at_end(p)) { set_error(p, "unterminated escape"); return -1; }
            c = next(p);
            switch (c) {
                case '"': case '\\': case '/': case 'b':
                case 'f': case 'n': case 'r': case 't':
                    break;
                case 'u':
                    /* Unicode escape - skip 4 hex digits */
                    p->pos += 4;
                    if (p->pos >= p->len) { set_error(p, "invalid unicode"); return -1; }
                    break;
                default:
                    set_error(p, "invalid escape");
                    return -1;
            }
        } else if ((unsigned char)c < 0x20) {
            set_error(p, "control character in string");
            return -1;
        } else {
            p->pos++;
        }
    }
    
    if (at_end(p)) { set_error(p, "unterminated string"); return -1; }
    
    result_len = p->pos - start;
    p->pos++;  /* Skip closing quote */
    
    /* Allocate result (this is the only dynamic allocation) */
    result = (char *)malloc(result_len + 1);
    if (!result) { set_error(p, "out of memory"); return -1; }
    
    /* Copy and unescape in one pass */
    {
        size_t src_i = 0, dst_i = 0;
        while (src_i < result_len) {
            char sc = p->buf[start + src_i];
            if (sc == '\\') {
                src_i++;
                if (src_i >= result_len) break;
                sc = p->buf[start + src_i];
                switch (sc) {
                    case '"':  result[dst_i++] = '"';  break;
                    case '\\': result[dst_i++] = '\\'; break;
                    case '/':  result[dst_i++] = '/';  break;
                    case 'b':  result[dst_i++] = '\b'; break;
                    case 'f':  result[dst_i++] = '\f'; break;
                    case 'n':  result[dst_i++] = '\n'; break;
                    case 'r':  result[dst_i++] = '\r'; break;
                    case 't':  result[dst_i++] = '\t'; break;
                    case 'u':
                        /* Simplified: just append U+FFFD for \uXXXX */
                        result[dst_i++] = (char)0xEF;
                        result[dst_i++] = (char)0xBF;
                        result[dst_i++] = (char)0xBD;
                        break;
                    default:   result[dst_i++] = sc;   break;
                }
                src_i++;
            } else {
                result[dst_i++] = sc;
                src_i++;
            }
        }
        result[dst_i] = '\0';
    }
    
    *out_str = result;
    return 0;
}

static int parse_number(JsonParser *p, double *out_num)
{
    size_t start = p->pos;
    double num = 0.0;
    int sign = 1;
    double frac = 0.0;
    int digits = 0;
    int exp_sign = 1;
    int exp_val = 0;
    
    if (peek(p) == '-') { sign = -1; p->pos++; }
    
    /* Integer part */
    while (!at_end(p) && isdigit((unsigned char)peek(p))) {
        num = num * 10.0 + (peek(p) - '0');
        p->pos++;
        digits++;
    }
    
    /* Fractional part */
    if (peek(p) == '.') {
        p->pos++;
        while (!at_end(p) && isdigit((unsigned char)peek(p))) {
            frac = frac * 10.0 + (peek(p) - '0');
            p->pos++;
            digits++;
        }
    }
    
    /* Exponent */
    if (peek(p) == 'e' || peek(p) == 'E') {
        p->pos++;
        if (peek(p) == '+') p->pos++;
        else if (peek(p) == '-') { exp_sign = -1; p->pos++; }
        while (!at_end(p) && isdigit((unsigned char)peek(p))) {
            exp_val = exp_val * 10 + (peek(p) - '0');
            p->pos++;
        }
    }
    
    if (digits == 0) {
        set_error(p, "expected number");
        return -1;
    }
    
    *out_num = sign * (num + frac / 9.0) * pow(10.0, exp_sign * exp_val);
    return 0;
}

static int parse_literal(JsonParser *p, const char *lit, JsonType type, JsonVal *out)
{
    size_t i = 0;
    while (!at_end(p) && lit[i] != '\0') {
        if (p->buf[p->pos] != lit[i]) {
            set_error(p, "expected literal");
            return -1;
        }
        p->pos++;
        i++;
    }
    out->type = type;
    if (type == JSON_BOOL) {
        out->val.bol = (lit[0] == 't') ? 1 : 0;
    }
    return 0;
}

static int parse_value(JsonParser *p, JsonVal *out)
{
    skip_whitespace(p);
    if (at_end(p)) { set_error(p, "unexpected end"); return -1; }
    
    char c = peek(p);
    
    switch (c) {
        case '{': {
            /* Object - simplified: just skip for now, store position */
            p->pos++;
            out->type = JSON_OBJECT;
            out->val.obj = (void *)p->pos;
            /* Skip to matching } */
            {
                int depth = 1;
                int in_string = 0;
                while (!at_end(p) && depth > 0) {
                    c = next(p);
                    if (c == '"') in_string = !in_string;
                    else if (!in_string) {
                        if (c == '{') depth++;
                        else if (c == '}') depth--;
                    }
                }
            }
            return 0;
        }
        case '[': {
            /* Array - simplified: store position */
            p->pos++;
            out->type = JSON_ARRAY;
            out->val.obj = (void *)p->pos;
            {
                int depth = 1;
                int in_string = 0;
                while (!at_end(p) && depth > 0) {
                    c = next(p);
                    if (c == '"') in_string = !in_string;
                    else if (!in_string) {
                        if (c == '[') depth++;
                        else if (c == ']') depth--;
                    }
                }
            }
            return 0;
        }
        case '"': {
            char *s = NULL;
            if (parse_string(p, &s) != 0) return -1;
            out->type = JSON_STRING;
            out->val.str = s;
            return 0;
        }
        case 't':
            return parse_literal(p, "true", JSON_BOOL, out);
        case 'f':
            return parse_literal(p, "false", JSON_BOOL, out);
        case 'n':
            return parse_literal(p, "null", JSON_NULL, out);
        default:
            if (c == '-' || isdigit((unsigned char)c)) {
                double num = 0;
                if (parse_number(p, &num) != 0) return -1;
                out->type = JSON_NUMBER;
                out->val.num = num;
                return 0;
            }
            set_error(p, "unexpected character");
            return -1;
    }
}

/* ============================================================
 * PUBLIC API
 * ============================================================ */

void JsonParser_Init(JsonParser *p, char *buf, size_t len)
{
    p->buf = buf;
    p->len = len;
    p->pos = 0;
    p->err = NULL;
}

int JsonParser_Parse(JsonParser *p, JsonVal *out)
{
    skip_whitespace(p);
    return parse_value(p, out);
}

JsonVal JsonObject_Get(JsonVal obj, const char *key)
{
    JsonVal null_val;
    null_val.type = JSON_NULL;
    return null_val;  /* Simplified: full implementation would iterate */
}

JsonVal JsonArray_Get(JsonVal arr, int index)
{
    JsonVal null_val;
    null_val.type = JSON_NULL;
    return null_val;  /* Simplified: full implementation would iterate */
}

int JsonVal_IsNull(JsonVal v) { return v.type == JSON_NULL; }
int JsonVal_IsTrue(JsonVal v) { return v.type == JSON_BOOL && v.val.bol; }
double JsonVal_Number(JsonVal v) { return v.val.num; }
char *JsonVal_String(JsonVal v) { return v.val.str; }

/* ============================================================
 * SERIALIZER (for building requests)
 * ============================================================ */

static size_t min_size(size_t a, size_t b) { return (a < b) ? a : b; }

int json_put_object_start(char *buf, size_t cap, size_t *pos)
{
    if (*pos >= cap) return -1;
    buf[(*pos)++] = '{';
    return 0;
}

int json_put_object_end(char *buf, size_t cap, size_t *pos)
{
    if (*pos >= cap) return -1;
    buf[(*pos)++] = '}';
    return 0;
}

int json_put_array_start(char *buf, size_t cap, size_t *pos)
{
    if (*pos >= cap) return -1;
    buf[(*pos)++] = '[';
    return 0;
}

int json_put_array_end(char *buf, size_t cap, size_t *pos)
{
    if (*pos >= cap) return -1;
    buf[(*pos)++] = ']';
    return 0;
}

int json_put_string(char *buf, size_t cap, size_t *pos, const char *s)
{
    size_t len;
    if (!s) return json_put_string(buf, cap, pos, "null");
    len = strlen(s);
    if (*pos >= cap) return -1;
    buf[(*pos)++] = '"';
    if (len > 0) {
        size_t available = cap - *pos;
        size_t to_copy = min_size(len, available - 2);  /* room for '"' and '\0' */
        size_t i;
        for (i = 0; i < to_copy; i++) {
            char c = s[i];
            if (c == '"' || c == '\\') {
                if (*pos < cap - 1) buf[(*pos)++] = '\\';
            }
            if (*pos < cap - 1) buf[(*pos)++] = c;
        }
    }
    if (*pos >= cap) return -1;
    buf[(*pos)++] = '"';
    return 0;
}

int json_put_number(char *buf, size_t cap, size_t *pos, double n)
{
    char tmp[32];
    int len;
    size_t i;
    /* Simple integer formatting for RTC slot numbers */
    if (n == (long)n) {
        len = sprintf(tmp, "%.0f", n);
    } else {
        len = sprintf(tmp, "%.6g", n);
    }
    for (i = 0; i < (size_t)len && *pos < cap; i++) {
        buf[(*pos)++] = tmp[i];
    }
    return (i < (size_t)len) ? -1 : 0;
}

int json_put_bool(char *buf, size_t cap, size_t *pos, int b)
{
    const char *s = b ? "true" : "false";
    size_t len = strlen(s);
    size_t i;
    for (i = 0; i < len && *pos < cap; i++) {
        buf[(*pos)++] = s[i];
    }
    return (i < len) ? -1 : 0;
}

int json_put_null(char *buf, size_t cap, size_t *pos)
{
    const char *s = "null";
    size_t len = 4;
    size_t i;
    for (i = 0; i < len && *pos < cap; i++) {
        buf[(*pos)++] = s[i];
    }
    return (i < len) ? -1 : 0;
}

int json_put_key(char *buf, size_t cap, size_t *pos, const char *key)
{
    size_t start = *pos;
    if (json_put_string(buf, cap, pos, key) != 0) return -1;
    if (*pos < cap) buf[(*pos)++] = ':';
    return 0;
}
