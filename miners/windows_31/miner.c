/*
 * miner.c — RustChain PoA Validator for Windows 3.1 (16-bit Win16 API)
 *
 * YÊU CẦU:
 * - Chạy đồ họa (GUI) tương thích với Windows 3.1 Program Manager.
 * - Hiển thị cửa sổ GUI với điểm số xác thực PoA.
 * - Sử dụng GetTickCount và WM_TIMER để sinh entropy.
 * - Ghi tệp JSON proof_of.json ra thư mục hiện hành.
 *
 * Biên dịch bằng Open Watcom: wcl -l=windows -d0 -y miner.c
 * Hoặc Microsoft Visual C++ 1.52.
 */

#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define FILENAME "proof_of.json"
#define TIMER_ID 1

char szAppName[] = "RustChainWin16";
char szTitle[] = "RustChain Win3.1 Validator";
char szWallet[] = "RTC-win31-default-wallet";
unsigned long dwTicks = 0;
unsigned int wEntropy = 0;

/* Prototype */
long FAR PASCAL _export WndProc(HWND, UINT, WPARAM, LPARAM);

/*
 * Hàm ghi cấu trúc dữ liệu JSON ra tệp proof_of.json.
 * Tham số:
 *   - szWallet: Địa chỉ ví nhận thưởng.
 *   - dwNonce: Giá trị nonce ngẫu nhiên sinh ra từ hệ thống.
 * Trả về:
 *   - Không có.
 */
void WriteJsonFile(const char *szWallet, unsigned long dwNonce) {
    FILE *file = fopen(FILENAME, "w");
    if (file != NULL) {
        fprintf(file, "{\n");
        fprintf(file, "  \"miner\": \"%s\",\n", szWallet);
        fprintf(file, "  \"nonce\": %lu,\n", dwNonce);
        fprintf(file, "  \"device\": {\n");
        fprintf(file, "    \"arch\": \"i386-win16\",\n");
        fprintf(file, "    \"family\": \"windows-3.1\",\n");
        fprintf(file, "    \"graphics\": \"gdi-gui\"\n");
        fprintf(file, "  }\n");
        fprintf(file, "}\n");
        fclose(file);
    }
}

/*
 * Điểm khởi đầu chính (Entry point) của ứng dụng đồ họa Win16.
 */
int PASCAL WinMain(HANDLE hInstance, HANDLE hPrevInstance, LPSTR lpszCmdLine, int nCmdShow) {
    HWND hwnd;
    MSG msg;
    WNDCLASS wndclass;

    if (lpszCmdLine && lpszCmdLine[0] != '\0') {
        int i;
        for (i = 0; i < 63 && lpszCmdLine[i] != '\0'; i++) {
            szWallet[i] = lpszCmdLine[i];
        }
        szWallet[i] = '\0';
    }

    if (!hPrevInstance) {
        wndclass.style         = CS_HREDRAW | CS_VREDRAW;
        wndclass.lpfnWndProc   = WndProc;
        wndclass.cbClsExtra    = 0;
        wndclass.cbWndExtra    = 0;
        wndclass.hInstance     = hInstance;
        wndclass.hIcon         = LoadIcon(NULL, IDI_APPLICATION);
        wndclass.hCursor       = LoadCursor(NULL, IDC_ARROW);
        wndclass.hbrBackground = (HBRUSH)GetStockObject(WHITE_BRUSH);
        wndclass.lpszMenuName  = NULL;
        wndclass.lpszClassName = szAppName;

        RegisterClass(&wndclass);
    }

    hwnd = CreateWindow(szAppName, szTitle,
                        WS_OVERLAPPEDWINDOW,
                        CW_USEDEFAULT, CW_USEDEFAULT,
                        400, 200,
                        NULL, NULL, hInstance, NULL);

    ShowWindow(hwnd, nCmdShow);
    UpdateWindow(hwnd);

    while (GetMessage(&msg, NULL, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }
    return msg.wParam;
}

/*
 * Hàm xử lý thông điệp cửa sổ (Window Procedure) cho GUI.
 */
long FAR PASCAL _export WndProc(HWND hwnd, UINT message, WPARAM wParam, LPARAM lParam) {
    HDC hdc;
    PAINTSTRUCT ps;
    RECT rect;
    char szBuf[128];

    switch (message) {
        case WM_CREATE:
            SetTimer(hwnd, TIMER_ID, 2000, NULL);
            return 0;

        case WM_TIMER:
            dwTicks = GetTickCount();
            wEntropy = (wEntropy + 7) ^ (unsigned int)(dwTicks & 0xFFFF);
            WriteJsonFile(szWallet, dwTicks ^ wEntropy);
            InvalidateRect(hwnd, NULL, TRUE);
            return 0;

        case WM_PAINT:
            hdc = BeginPaint(hwnd, &ps);
            GetClientRect(hwnd, &rect);

            sprintf(szBuf, "Wallet: %s", szWallet);
            TextOut(hdc, 20, 20, szBuf, strlen(szBuf));

            sprintf(szBuf, "System Ticks: %lu", dwTicks);
            TextOut(hdc, 20, 50, szBuf, strlen(szBuf));

            sprintf(szBuf, "PoA Entropy: 0x%04X", wEntropy);
            TextOut(hdc, 20, 80, szBuf, strlen(szBuf));

            EndPaint(hwnd, &ps);
            return 0;

        case WM_DESTROY:
            KillTimer(hwnd, TIMER_ID);
            PostQuitMessage(0);
            return 0;
    }
    return DefWindowProc(hwnd, message, wParam, lParam);
}
