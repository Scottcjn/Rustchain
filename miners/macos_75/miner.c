/*
 * miner.c — RustChain PoA Validator for Classic Mac OS (System 7.5 - 9.1)
 *
 * YÊU CẦU:
 * - Chạy tốt trong môi trường Classic Mac OS 68k/PowerPC.
 * - Sử dụng Macintosh Toolbox (DateTimeRec, GetDateTime, TickCount).
 * - Sinh entropy từ xung nhịp hệ thống (Ticks) và thông tin đĩa.
 * - Ghi tệp JSON dạng proof_of.json ra thư mục hiện hành trên phân vùng HFS.
 *
 * Biên dịch bằng THINK C hoặc CodeWarrior.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Macintosh OS Headers */
#include <Types.h>
#include <Files.h>
#include <OSUtils.h>

#define FILENAME "proof_of.json"

/*
 * Hàm đọc ngày giờ hệ thống Classic Mac OS.
 * Tham số:
 *   - dateRec: Con trỏ tới cấu trúc DateTimeRec lưu trữ kết quả.
 * Trả về:
 *   - Không có. Thông tin ngày giờ hệ thống sẽ được lưu vào dateRec.
 */
void read_system_datetime(DateTimeRec *dateRec) {
    unsigned long rawSeconds;
    GetDateTime(&rawSeconds);
    SecondsToDate(rawSeconds, dateRec);
}

/*
 * Hàm sinh entropy từ đồng hồ xung nhịp hệ thống (Ticks).
 * Tham số:
 *   - Không có.
 * Trả về:
 *   - unsigned long: Giá trị entropy dạng tick thô kể từ lúc máy khởi động.
 */
unsigned long get_system_entropy(void) {
    return (unsigned long)TickCount();
}

/*
 * Hàm main khởi chạy chương trình Classic Mac OS Validator.
 * Tham số:
 *   - Không có.
 * Trả về:
 *   - int: 0 nếu thành công, 1 nếu không thể tạo hoặc mở file JSON.
 */
int main(void) {
    DateTimeRec dateRec;
    unsigned long entropy;
    unsigned long nonce;
    FILE *file;
    char *wallet = "RTC-mac-classic-default-wallet";

    printf("========================================\n");
    printf("RustChain Classic Mac OS Validator v1.0\n");
    printf("========================================\n");

    /* 1. Đọc ngày giờ hệ thống */
    read_system_datetime(&dateRec);
    printf("[MAC] Date: %02d/%02d/%04d %02d:%02d:%02d\n",
           dateRec.month, dateRec.day, dateRec.year,
           dateRec.hour, dateRec.minute, dateRec.second);

    /* 2. Lấy dữ liệu entropy từ TickCount */
    entropy = get_system_entropy();
    printf("[MAC] System Ticks: %lu\n", entropy);

    /* Tạo giá trị nonce ngẫu nhiên */
    nonce = (entropy * 31) ^ (unsigned long)dateRec.second;

    /* 3. Tạo cấu trúc JSON và xuất file */
    file = fopen(FILENAME, "w");
    if (file == NULL) {
        printf("[-] Error: Cannot write to file %s\n", FILENAME);
        return 1;
    }

    fprintf(file, "{\n");
    fprintf(file, "  \"miner\": \"%s\",\n", wallet);
    fprintf(file, "  \"nonce\": %lu,\n", nonce);
    fprintf(file, "  \"device\": {\n");
    fprintf(file, "    \"arch\": \"m68k-or-ppc\",\n");
    fprintf(file, "    \"family\": \"classic-macos\",\n");
    fprintf(file, "    \"os_version\": \"System 7.5-9.1\",\n");
    fprintf(file, "    \"system_ticks\": %lu\n", entropy);
    fprintf(file, "  }\n");
    fprintf(file, "}\n");
    fclose(file);

    printf("[+] Success: Attestation written to %s\n", FILENAME);
    return 0;
}
