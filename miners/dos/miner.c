/*
 * miner.c — RustChain PoA Validator for MS-DOS (16-bit Real Mode)
 *
 * YÊU CẦU:
 * - Tương thích với MS-DOS 6.x trở lên.
 * - Đọc ngày BIOS trực tiếp tại địa chỉ vật lý 0xF000:0xFFF5.
 * - Sử dụng ngắt INT 1Ah để sinh entropy ngẫu nhiên từ tick hệ thống.
 * - Ghi tệp proof_of.json ra ổ đĩa FAT.
 *
 * Biên dịch bằng Open Watcom: wcl -0 -y -d0 miner.c
 * Hoặc Borland C++ 3.1: bcc -mt -lt miner.c
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dos.h>

#define FILENAME "proof_of.json"

/*
 * Hàm đọc ngày BIOS từ bộ nhớ 0xFFFF5 (F000:FFF5).
 * Tham số:
 *   - buffer: Con trỏ tới vùng nhớ lưu chuỗi ngày BIOS (độ dài tối thiểu 9 bytes).
 * Trả về:
 *   - Không có. Ngày BIOS dạng "MM/DD/YY" sẽ được lưu vào buffer.
 */
void read_bios_date(char *buffer) {
    char far *bios_ptr = (char far *)0xF000FFF5L;
    int i;
    for (i = 0; i < 8; i++) {
        buffer[i] = bios_ptr[i];
    }
    buffer[8] = '\0';
}

/*
 * Hàm lấy số tick của đồng hồ hệ thống thông qua ngắt BIOS INT 1Ah.
 * Tham số:
 *   - Không có.
 * Trả về:
 *   - unsigned long: Giá trị tick hiện tại của hệ thống.
 */
unsigned long get_bios_ticks(void) {
    union REGS regs;
    regs.h.ah = 0x00;
    int86(0x1A, &regs, &regs);
    return ((unsigned long)regs.x.cx << 16) | regs.x.dx;
}

/*
 * Hàm mô phỏng tạo entropy qua vòng lặp trễ (loop delay).
 * Tham số:
 *   - iterations: Số lần lặp để tạo độ trễ.
 * Trả về:
 *   - unsigned int: Giá trị băm đơn giản (hash/checksum) được tính từ vòng lặp trễ.
 */
unsigned int simulate_entropy(unsigned long iterations) {
    unsigned long i;
    unsigned int hash = 5381;
    for (i = 0; i < iterations; i++) {
        hash = ((hash << 5) + hash) + (unsigned int)(i ^ get_bios_ticks());
    }
    return hash;
}

/*
 * Hàm main khởi chạy chương trình DOS Validator.
 * Tham số:
 *   - argc: Số lượng tham số dòng lệnh.
 *   - argv: Mảng các chuỗi tham số dòng lệnh.
 * Trả về:
 *   - int: 0 nếu thành công, 1 nếu gặp lỗi ghi file.
 */
int main(int argc, char *argv[]) {
    char bios_date[16];
    unsigned long ticks;
    unsigned int entropy;
    FILE *file;
    char *wallet = "RTC-dos-default-wallet";

    if (argc > 1) {
        wallet = argv[1];
    }

    printf("========================================\n");
    printf("RustChain MS-DOS PoA Validator v1.0\n");
    printf("========================================\n");

    /* 1. Đọc ngày BIOS */
    read_bios_date(bios_date);
    printf("[BIOS] Detected Date: %s\n", bios_date);

    /* 2. Sinh entropy bằng vòng lặp trễ */
    printf("[POA] Generating entropy via CPU loop delay...\n");
    ticks = get_bios_ticks();
    entropy = simulate_entropy(15000L);
    printf("[POA] System Ticks: %lu, Entropy Hash: 0x%04X\n", ticks, entropy);

    /* 3. Tạo cấu trúc JSON và ghi file */
    file = fopen(FILENAME, "w");
    if (file == NULL) {
        printf("[-] Error: Cannot write to file %s\n", FILENAME);
        return 1;
    }

    fprintf(file, "{\n");
    fprintf(file, "  \"miner\": \"%s\",\n", wallet);
    fprintf(file, "  \"nonce\": %lu,\n", ticks ^ entropy);
    fprintf(file, "  \"device\": {\n");
    fprintf(file, "    \"arch\": \"i86-realmode\",\n");
    fprintf(file, "    \"family\": \"ms-dos\",\n");
    fprintf(file, "    \"bios_date\": \"%s\",\n", bios_date);
    fprintf(file, "    \"entropy_seed\": %u\n", entropy);
    fprintf(file, "  }\n");
    fprintf(file, "}\n");
    fclose(file);

    printf("[+] Success: Attestation written to %s\n", FILENAME);
    return 0;
}
