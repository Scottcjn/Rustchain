/* GENWALT.CPP - Generate RustChain wallet */
/* Compiled and tested with Borland C++ 4.5 */
#include <stdlib.h>
#include <time.h>
#include <fstream.h>
#include <iostream.h>
#include <dos.h>

void byteToHex(unsigned char byte, char* buffer) {
    const char* hexDigits = "0123456789ABCDEF";
    buffer[0] = hexDigits[(byte >> 4) & 0xF];
    buffer[1] = hexDigits[byte & 0xF];
}

int main() {
    const int byteLength = 20; // 20 bytes = 40 hex characters
    unsigned char randomBytes[byteLength];
    char hexString[byteLength * 2 + 1]; // +1 for null terminator
    hexString[byteLength * 2] = '\0';

    // Seed the random number generator
	 srand(time(NULL));

    // Generate 20 random bytes and convert to hex
    for (int i = 0; i < byteLength; i++) {
        randomBytes[i] = rand() % 256;
        byteToHex(randomBytes[i], &hexString[i * 2]);
    }

    // Output file
    ofstream outFile("rstmnr.ini");
    if (!outFile) {
        cerr << "Failed to open rstmnr.ini for writing." << endl;
        return 1;
    }

    outFile << hexString;
    outFile.close();

    cout << "Your RustChain wallet ID: " << hexString << "RTC" << endl;
    cout << "This has been stored in the rstmnr.ini file" << endl;

    return 0;
}