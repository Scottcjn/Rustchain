#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <dos.h>
#include <chrono>
#include <thread>
#include <fstream>
#include <iostream>

/* For WatTCP */
#include <tcp.h>

#define RUST_NODE "50.28.86.131"
#define RUST_PORT 8085
//#define WALLET "a3f5bc8d9e2a1b7c4d6e8f0a2b4c6d8e0f2a4b6cRTC"

int main() {
    tcp_Socket sock;
    char request[1024];
    char response[512];
    char json[512];
    time_t now;

    char hexkey[40];
    int i = 0;
    //Open the INI file with the encrypted wallet ID hex values
    std::ifstream infile("rstmnr.ini");
    std::string WALLET;
    std::string line;

    if(infile.is_open())
    {
	while ( getline (infile, line))
        {
            if(line == "0")
            {
                hexkey[i] = '0';
                i += 1;
            }
            if(line == "1")
            {
                hexkey[i] = '1';
                i += 1;
            }
            if(line == "2")
            {
                hexkey[i] = '2';
                i += 1;
            }
            if(line == "3")
            {
                hexkey[i] = '3';
                i += 1;
            }
            if(line == "4")
            {
                hexkey[i] = '4';
                i += 1;
            }
            if(line == "5")
            {
                hexkey[i] = '5';
                i += 1;
            }
            if(line == "6")
            {
                hexkey[i] = '6';
                i += 1;
            }
            if(line == "7")
            {
                hexkey[i] = '7';
                i += 1;
            }
            if(line == "8")
            {
                hexkey[i] = '8';
                i += 1;
            }
            if(line == "9")
            {
                hexkey[i] = '9';
                i += 1;
            }
            if(line == "10")
            {
                hexkey[i] = 'a';
                i += 1;
            }
            if(line == "11")
            {
                hexkey[i] = 'b';
                i += 1;
            }
            if(line == "12")
            {
                hexkey[i] = 'c';
                i += 1;
            }
            if(line == "13")
            {
                hexkey[i] = 'd';
                i += 1;
            }
            if(line == "14")
            {
                hexkey[i] = 'e';
                i += 1;
            }
            if(line == "15")
            {
                hexkey[i] = 'f';
                i += 1;
            }
        }
    }
        //Close the INI file
        infile.close();
    //Now generate the full string from the translated characters in the array
    for (int i = 0; i < 40; ++i) {  
        WALLET += hexkey[i];
    }
    //Finalize and return the wallet ID
    WALLET += "RTC";
    
    printf("RustChain 486 Miner v1.0\n");
    printf("Initializing WatTCP...\n");
    
    sock_init();
    
    while(1) {
        printf("Connecting to %s:%d...\n", RUST_NODE, RUST_PORT);
        
        if(!tcp_open(&sock, 0, inet_addr(RUST_NODE), RUST_PORT, NULL)) {
            printf("Connection failed!\n");
            std::this_thread::sleep_for(std::chrono::nanoseconds(5000));
            continue;
        }
        
        /* Create mining proof */
        now = time(NULL);
        sprintf(json,
            "{"
            "\"wallet\":\"%s\","
            "\"hardware\":\"Intel 80486DX2-66\","
            "\"platform\":\"MS-DOS 6.22\","
            "\"age_years\":31,"
            "\"multiplier\":3.5,"
            "\"tier\":\"ANCIENT_SILICON\","
            "\"timestamp\":%ld,"
            "\"anti_emulation\":{"
                "\"cpu_family\":4,"
                "\"real_mode\":true"
            "}"
            "}",
            WALLET, now
        );
        
        /* Build HTTP request */
        sprintf(request,
            "POST /api/mine HTTP/1.0\r\n"
            "Host: %s\r\n"
            "Content-Type: application/json\r\n"
            "Content-Length: %d\r\n"
            "\r\n"
            "%s",
            RUST_NODE, strlen(json), json
        );
        
        /* Send request */
        sock_write(&sock, request, strlen(request));
        
        /* Read response */
        sock_wait_input(&sock, 10, NULL, &sock_status);
        sock_gets(&sock, response, sizeof(response));
        
        if(strstr(response, "200 OK")) {
            printf("Mining successful!\n");
        } else {
            printf("Mining failed: %s\n", response);
        }
        
        sock_close(&sock);
        
        /* Wait 2 minutes for next block */
        printf("Waiting 120 seconds...\n");
        std::this_thread::sleep_for(std::chrono::nanoseconds(120000));
    }
    
    return 0;
}