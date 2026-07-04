/*
 * miner.cpp — RustChain PoA Validator for BeOS and Haiku OS (C++ Native API)
 *
 * YÊU CẦU:
 * - Ứng dụng GUI native sử dụng BApplication, BWindow và BView.
 * - Truy xuất thời gian hệ thống dạng microsecond bằng system_time().
 * - Ghi tệp JSON dạng proof_of.json trên phân vùng tệp tin BFS.
 *
 * Biên dịch trên Haiku bằng g++:
 * g++ -o Miner miner.cpp -lbe
 */

#include <Application.h>
#include <Window.h>
#include <View.h>
#include <StringView.h>
#include <Message.h>
#include <MessageRunner.h>
#include <KernelKit.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define FILENAME "proof_of.json"
const uint32 MSG_UPDATE = 'updt';

/*
 * Hàm ghi cấu trúc dữ liệu JSON ra tệp proof_of.json.
 * Tham số:
 *   - wallet: Địa chỉ ví nhận thưởng.
 *   - nonce: Giá trị nonce ngẫu nhiên sinh ra từ hệ thống.
 *   - sys_time: Thời gian hệ thống microsecond.
 * Trả về:
 *   - Không có.
 */
void WriteJsonFile(const char *wallet, uint64 nonce, bigint_t sys_time) {
    FILE *file = fopen(FILENAME, "w");
    if (file != NULL) {
        fprintf(file, "{\n");
        fprintf(file, "  \"miner\": \"%s\",\n", wallet);
        fprintf(file, "  \"nonce\": %llu,\n", (unsigned long long)nonce);
        fprintf(file, "  \"device\": {\n");
        fprintf(file, "    \"arch\": \"x86-native\",\n");
        fprintf(file, "    \"family\": \"beos-haiku\",\n");
        fprintf(file, "    \"system_time_us\": %lld\n", (long long)sys_time);
        fprintf(file, "  }\n");
        fprintf(file, "}\n");
        fclose(file);
    }
}

/*
 * Lớp MinerView xử lý giao diện hiển thị các thông tin validator.
 */
class MinerView : public BView {
public:
    BStringView *fWalletLabel;
    BStringView *fTimeLabel;
    BStringView *fEntropyLabel;

    MinerView(BRect frame) : BView(frame, "MinerView", B_FOLLOW_ALL, B_WILL_DRAW) {
        SetViewColor(ui_color(B_PANEL_BACKGROUND_COLOR));

        fWalletLabel = new BStringView(BRect(20, 20, 380, 40), "wallet", "Wallet: RTC-beos-default-wallet");
        fTimeLabel = new BStringView(BRect(20, 50, 380, 70), "time", "System Time: 0 us");
        fEntropyLabel = new BStringView(BRect(20, 80, 380, 100), "entropy", "Entropy Nonce: 0");

        AddChild(fWalletLabel);
        AddChild(fTimeLabel);
        AddChild(fEntropyLabel);
    }
};

/*
 * Lớp MinerWindow đại diện cho cửa sổ ứng dụng đồ họa trên BeOS/Haiku.
 */
class MinerWindow : public BWindow {
public:
    MinerView *fView;
    BMessageRunner *fRunner;
    char fWalletAddress[64];

    MinerWindow(BRect frame) : BWindow(frame, "RustChain BeOS Validator", B_TITLED_WINDOW, B_NOT_ZOOMABLE | B_NOT_RESIZABLE) {
        strcpy(fWalletAddress, "RTC-beos-default-wallet");
        fView = new MinerView(Bounds());
        AddChild(fView);

        /* Gửi thông điệp cập nhật mỗi 2 giây (2000000 microseconds) */
        BMessage msg(MSG_UPDATE);
        fRunner = new BMessageRunner(BMessenger(this), &msg, 2000000);
    }

    virtual ~MinerWindow() {
        delete fRunner;
    }

    virtual void MessageReceived(BMessage *message) {
        if (message->what == MSG_UPDATE) {
            bigint_t t = system_time();
            uint64 nonce = ((uint64)t * 17) ^ 0xDEADBEEF;

            char buf[128];
            sprintf(buf, "Wallet: %s", fWalletAddress);
            fView->fWalletLabel->SetText(buf);

            sprintf(buf, "System Time: %lld us", (long long)t);
            fView->fTimeLabel->SetText(buf);

            sprintf(buf, "Entropy Nonce: %llu", (unsigned long long)nonce);
            fView->fEntropyLabel->SetText(buf);

            WriteJsonFile(fWalletAddress, nonce, t);
        } else {
            BWindow::MessageReceived(message);
        }
    }

    virtual bool QuitRequested() {
        be_app->PostMessage(B_QUIT_REQUESTED);
        return true;
    }
};

/*
 * Lớp MinerApp là điểm quản lý vòng lặp sự kiện chính của ứng dụng BeOS/Haiku.
 */
class MinerApp : public BApplication {
public:
    MinerApp() : BApplication("application/x-vnd.RustChain-Miner") {}

    virtual void ReadyToRun() {
        MinerWindow *win = new MinerWindow(BRect(100, 100, 500, 240));
        win->Show();
    }
};

/*
 * Điểm khởi chạy chính (Entry point) của ứng dụng C++ BeOS/Haiku.
 */
int main(int argc, char *argv[]) {
    MinerApp app;
    app.Run();
    return 0;
}
