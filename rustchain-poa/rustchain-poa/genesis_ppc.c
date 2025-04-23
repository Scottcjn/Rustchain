// RustChain PoA Genesis Builder for PowerMac G4 (C)
// Generates genesis.json with SHA1 and Base64 fingerprint

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

// Minimal SHA1 implementation
void sha1(const unsigned char *data, size_t len, unsigned char *out) {
    unsigned int h0 = 0x67452301;
    unsigned int h1 = 0xEFCDAB89;
    unsigned int h2 = 0x98BADCFE;
    unsigned int h3 = 0x10325476;
    unsigned int h4 = 0xC3D2E1F0;
    unsigned int i, j;

    unsigned char msg[64];
    unsigned int w[80], a, b, c, d, e, f, k, temp;
    size_t new_len = len + 1;
    while (new_len % 64 != 56) new_len++;
    unsigned char *msg_full = calloc(new_len + 8, 1);
    memcpy(msg_full, data, len);
    msg_full[len] = 0x80;
    unsigned int bits_len = len * 8;
    for (i = 0; i < 4; i++) {
        msg_full[new_len + 7 - i] = bits_len >> (i * 8);
    }

    for (i = 0; i < new_len + 8; i += 64) {
        memcpy(msg, msg_full + i, 64);
        for (j = 0; j < 16; j++) {
            w[j] = (msg[j*4] << 24) | (msg[j*4+1] << 16) | (msg[j*4+2] << 8) | msg[j*4+3];
        }
        for (j = 16; j < 80; j++) {
            w[j] = (w[j-3] ^ w[j-8] ^ w[j-14] ^ w[j-16]);
            w[j] = (w[j] << 1) | (w[j] >> 31);
        }
        a = h0; b = h1; c = h2; d = h3; e = h4;
        for (j = 0; j < 80; j++) {
            if (j < 20) { f = (b & c) | ((~b) & d); k = 0x5A827999; }
            else if (j < 40) { f = b ^ c ^ d; k = 0x6ED9EBA1; }
            else if (j < 60) { f = (b & c) | (b & d) | (c & d); k = 0x8F1BBCDC; }
            else { f = b ^ c ^ d; k = 0xCA62C1D6; }
            temp = ((a << 5) | (a >> 27)) + f + e + k + w[j];
            e = d; d = c; c = (b << 30) | (b >> 2); b = a; a = temp;
        }
        h0 += a; h1 += b; h2 += c; h3 += d; h4 += e;
    }
    free(msg_full);
    out[0] = h0 >> 24; out[1] = h0 >> 16; out[2] = h0 >> 8; out[3] = h0;
    out[4] = h1 >> 24; out[5] = h1 >> 16; out[6] = h1 >> 8; out[7] = h1;
    out[8] = h2 >> 24; out[9] = h2 >> 16; out[10] = h2 >> 8; out[11] = h2;
    out[12] = h3 >> 24; out[13] = h3 >> 16; out[14] = h3 >> 8; out[15] = h3;
    out[16] = h4 >> 24; out[17] = h4 >> 16; out[18] = h4 >> 8; out[19] = h4;
}

// Simple Base64 encoding
const char b64_table[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
void base64_encode(const unsigned char *src, int len, char *out) {
    int i, j;
    for (i = 0, j = 0; i < len;) {
        unsigned octet_a = i < len ? src[i++] : 0;
        unsigned octet_b = i < len ? src[i++] : 0;
        unsigned octet_c = i < len ? src[i++] : 0;
        unsigned triple = (octet_a << 16) + (octet_b << 8) + octet_c;
        out[j++] = b64_table[(triple >> 18) & 0x3F];
        out[j++] = b64_table[(triple >> 12) & 0x3F];
        out[j++] = b64_table[(triple >> 6) & 0x3F];
        out[j++] = b64_table[triple & 0x3F];
    }
    int mod = len % 3;
    if (mod > 0) {
        out[j - 1] = '=';
        if (mod == 1) out[j - 2] = '=';
    }
    out[j] = '\0';
}

int main() {
    char input[256];
    char hostname[64] = "PowerMac-G4";
    time_t now = time(NULL);
    struct tm *local = localtime(&now);

    printf("\n🔥 RustChain PowerGenesis Builder (SHA1 + Base64) 🔥\n\n");
    printf("Genesis Timestamp: %s", asctime(local));
    printf("Enter your Genesis Message:\n> ");
    fgets(input, sizeof(input), stdin);
    input[strcspn(input, "\n")] = 0;

    char raw[512];
    snprintf(raw, sizeof(raw), "%s|%s|%s", hostname, asctime(local), input);

    unsigned char sha1_result[20];
    sha1((unsigned char*)raw, strlen(raw), sha1_result);

    char encoded[128];
    base64_encode(sha1_result, 20, encoded);

    FILE *fp = fopen("genesis.json", "w");
    if (fp) {
        fprintf(fp, "{\n");
        fprintf(fp, "  \"device\": \"%s\",\n", hostname);
        fprintf(fp, "  \"timestamp\": \"%s\",\n", asctime(local));
        fprintf(fp, "  \"message\": \"%s\",\n", input);
        fprintf(fp, "  \"fingerprint\": \"%s\"\n", encoded);
        fprintf(fp, "}\n");
        fclose(fp);
        printf("\n✅ Genesis written to genesis.json\n");
    } else {
        printf("❌ Could not write genesis.json\n");
    }
    return 0;
}
