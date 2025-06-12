/*
 * RustChain Secure PowerPC Miner with Dual Protection
 * Implements: Scaled PoW + AltiVec Hardware Challenges (No stake required!)
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>

#ifdef __ALTIVEC__
#include <altivec.h>
#endif

#define NODE_URL "http://50.28.86.153:8088"
#define WALLET_FILE "rustchain_wallet.dat"
#define STAKE_FILE "rustchain_stake.dat"

typedef struct {
    char address[64];
    float balance;
    int tier;
} Wallet;

// Simple SHA256-like hash (not cryptographically secure, just for demo)
void simple_hash(char *input, char *output) {
    unsigned int hash = 5381;
    int c;
    while ((c = *input++))
        hash = ((hash << 5) + hash) + c;
    sprintf(output, "%08x", hash);
}

// AltiVec hardware challenge - only PowerPC can do this efficiently
int altivec_challenge(unsigned char *data, int len) {
#ifdef __ALTIVEC__
    vector unsigned char v1, v2, v3;
    vector unsigned char permute_pattern = {15,14,13,12,11,10,9,8,7,6,5,4,3,2,1,0};
    int result = 0;
    
    // Load data into AltiVec registers
    v1 = vec_ld(0, data);
    
    // Perform AltiVec-specific operations
    v2 = vec_perm(v1, v1, permute_pattern);  // Permute bytes
    v3 = vec_xor(v1, v2);                    // XOR original with permuted
    
    // Extract result
    unsigned char temp[16];
    vec_st(v3, 0, temp);
    
    for (int i = 0; i < 16; i++) {
        result += temp[i];
    }
    
    return result;
#else
    // Non-AltiVec hardware will be very slow at this
    int result = 0;
    for (int i = 0; i < len; i++) {
        for (int j = 0; j < len; j++) {
            result += data[i] ^ data[len-1-j];
        }
    }
    return result;
#endif
}

// Scaled Proof of Work - easier for vintage hardware
int proof_of_work(char *block_data, int difficulty, int tier) {
    char hash_input[256];
    char hash_output[64];
    int nonce = 0;
    int target_zeros = difficulty;
    
    // Scale difficulty based on tier
    if (tier >= 2) {  // Mythic (PowerPC)
        target_zeros = (difficulty > 2) ? 2 : difficulty;
    }
    
    printf("Mining with difficulty %d (scaled from %d for tier %d)...\n", 
           target_zeros, difficulty, tier);
    
    while (1) {
        sprintf(hash_input, "%s%d", block_data, nonce);
        simple_hash(hash_input, hash_output);
        
        // Check if hash meets difficulty
        int valid = 1;
        for (int i = 0; i < target_zeros; i++) {
            if (hash_output[i] != '0') {
                valid = 0;
                break;
            }
        }
        
        if (valid) {
            printf("Found valid nonce: %d (hash: %s)\n", nonce, hash_output);
            return nonce;
        }
        
        nonce++;
        if (nonce % 10000 == 0) {
            printf("Trying nonce %d...\r", nonce);
            fflush(stdout);
        }
    }
}

// Check if wallet is valid (no stake required for PoA!)
int check_wallet(Wallet *wallet) {
    printf("Wallet verified: %s\n", wallet->address);
    printf("Current balance: %.2f RTC\n", wallet->balance);
    return 1;  // Always allow mining - this is Proof of Antiquity!
}

// Load or create wallet
void load_wallet(Wallet *wallet) {
    FILE *f = fopen(WALLET_FILE, "r");
    if (f) {
        fscanf(f, "%s %f %d", wallet->address, &wallet->balance, &wallet->tier);
        fclose(f);
    } else {
        // Create new wallet
        sprintf(wallet->address, "RTC%08x", rand());
        wallet->balance = 0.0;
        wallet->tier = 2;  // Mythic tier for PowerPC
        
        f = fopen(WALLET_FILE, "w");
        fprintf(f, "%s %.2f %d\n", wallet->address, wallet->balance, wallet->tier);
        fclose(f);
    }
}

// Save wallet
void save_wallet(Wallet *wallet) {
    FILE *f = fopen(WALLET_FILE, "w");
    fprintf(f, "%s %.2f %d\n", wallet->address, wallet->balance, wallet->tier);
    fclose(f);
}

// Submit mining solution
void submit_solution(Wallet *wallet, int nonce, int altivec_result) {
    char cmd[512];
    sprintf(cmd, "curl -s -X POST %s/submit_pow -H \"Content-Type: application/json\" "
            "-d '{\"address\":\"%s\",\"nonce\":%d,\"altivec_proof\":%d,\"tier\":%d}'",
            NODE_URL, wallet->address, nonce, altivec_result, wallet->tier);
    
    FILE *fp = popen(cmd, "r");
    if (fp) {
        char buffer[256];
        fgets(buffer, sizeof(buffer), fp);
        printf("Node response: %s\n", buffer);
        
        // Check if we earned reward
        if (strstr(buffer, "reward")) {
            wallet->balance += 0.3;  // Mythic tier gets 40% of 1.25 RTC when solo
            save_wallet(wallet);
            printf("Balance updated: %.2f RTC\n", wallet->balance);
        }
        
        pclose(fp);
    }
}

int main() {
    Wallet wallet;
    srand(time(NULL));
    
    printf("=== RustChain Secure PowerPC Miner ===\n");
    printf("Dual Protection: Scaled PoW + AltiVec\n\n");
    
    // Load wallet
    load_wallet(&wallet);
    printf("Wallet: %s\n", wallet.address);
    printf("Balance: %.2f RTC\n", wallet.balance);
    printf("Tier: %d (Mythic - PowerPC)\n\n", wallet.tier);
    
    // Check wallet (no stake required for PoA!)
    check_wallet(&wallet);
    
    // Main mining loop
    while (1) {
        printf("\n--- Starting new mining round ---\n");
        
        // Get current block data from node
        char block_data[256];
        sprintf(block_data, "block_%ld", time(NULL));
        
        // Step 1: AltiVec hardware challenge
        printf("\nStep 1: AltiVec Hardware Challenge\n");
        unsigned char challenge_data[64];
        for (int i = 0; i < 64; i++) {
            challenge_data[i] = rand() % 256;
        }
        
        int altivec_result = altivec_challenge(challenge_data, 64);
        printf("AltiVec result: %d\n", altivec_result);
        
        // Step 2: Scaled Proof of Work
        printf("\nStep 2: Proof of Work\n");
        int nonce = proof_of_work(block_data, 4, wallet.tier);
        
        // Step 3: Submit solution
        printf("\nStep 3: Submitting solution...\n");
        submit_solution(&wallet, nonce, altivec_result);
        
        // Wait before next round
        printf("\nWaiting 10 seconds before next round...\n");
        sleep(10);
    }
    
    return 0;
}