// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import os
import tempfile
import zipfile
import json
from flask import Flask, request, jsonify, send_file, render_template_string
from datetime import datetime

app = Flask(__name__)

def generate_pom_xml(group_id, artifact_id, version):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <groupId>{group_id}</groupId>
    <artifactId>{artifact_id}</artifactId>
    <version>{version}</version>
    <packaging>jar</packaging>

    <name>RustChain Java SDK</name>
    <description>Java SDK for RustChain blockchain integration</description>

    <properties>
        <maven.compiler.source>11</maven.compiler.source>
        <maven.compiler.target>11</maven.compiler.target>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    </properties>

    <dependencies>
        <dependency>
            <groupId>com.squareup.okhttp3</groupId>
            <artifactId>okhttp</artifactId>
            <version>4.12.0</version>
        </dependency>
        <dependency>
            <groupId>com.squareup.retrofit2</groupId>
            <artifactId>retrofit</artifactId>
            <version>2.9.0</version>
        </dependency>
        <dependency>
            <groupId>com.squareup.retrofit2</groupId>
            <artifactId>converter-gson</artifactId>
            <version>2.9.0</version>
        </dependency>
        <dependency>
            <groupId>org.bouncycastle</groupId>
            <artifactId>bcprov-jdk15on</artifactId>
            <version>1.70</version>
        </dependency>
        <dependency>
            <groupId>com.google.code.gson</groupId>
            <artifactId>gson</artifactId>
            <version>2.10.1</version>
        </dependency>
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter-engine</artifactId>
            <version>5.9.2</version>
            <scope>test</scope>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-compiler-plugin</artifactId>
                <version>3.11.0</version>
            </plugin>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-surefire-plugin</artifactId>
                <version>3.0.0</version>
            </plugin>
        </plugins>
    </build>
</project>"""

def generate_build_gradle(group_id, artifact_id, version):
    return f"""plugins {{
    id 'java-library'
    id 'maven-publish'
}}

group = '{group_id}'
version = '{version}'

java {{
    sourceCompatibility = JavaVersion.VERSION_11
    targetCompatibility = JavaVersion.VERSION_11
}}

repositories {{
    mavenCentral()
}}

dependencies {{
    implementation 'com.squareup.okhttp3:okhttp:4.12.0'
    implementation 'com.squareup.retrofit2:retrofit:2.9.0'
    implementation 'com.squareup.retrofit2:converter-gson:2.9.0'
    implementation 'org.bouncycastle:bcprov-jdk15on:1.70'
    implementation 'com.google.code.gson:gson:2.10.1'

    testImplementation 'org.junit.jupiter:junit-jupiter-engine:5.9.2'
    testRuntimeOnly 'org.junit.platform:junit-platform-launcher'
}}

test {{
    useJUnitPlatform()
}}

publishing {{
    publications {{
        maven(MavenPublication) {{
            from components.java
        }}
    }}
}}"""

def generate_rustchain_client():
    return """package io.rustchain.sdk;

import retrofit2.Call;
import retrofit2.http.*;
import java.util.Map;

public interface RustChainClient {
    @GET("/api/blocks/latest")
    Call<Map<String, Object>> getLatestBlock();

    @GET("/api/blocks/{hash}")
    Call<Map<String, Object>> getBlock(@Path("hash") String hash);

    @GET("/api/address/{address}/balance")
    Call<Map<String, Object>> getBalance(@Path("address") String address);

    @POST("/api/transactions")
    Call<Map<String, Object>> submitTransaction(@Body Map<String, Object> transaction);

    @GET("/api/epochs/current")
    Call<Map<String, Object>> getCurrentEpoch();

    @GET("/api/node/status")
    Call<Map<String, Object>> getNodeStatus();
}"""

def generate_rustchain_sdk():
    return """package io.rustchain.sdk;

import retrofit2.Retrofit;
import retrofit2.converter.gson.GsonConverterFactory;
import okhttp3.OkHttpClient;
import java.util.concurrent.TimeUnit;

public class RustChainSDK {
    private final String baseUrl;
    private final RustChainClient client;
    private final Retrofit retrofit;

    public RustChainSDK(String baseUrl) {
        this.baseUrl = baseUrl;

        OkHttpClient httpClient = new OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(60, TimeUnit.SECONDS)
            .build();

        this.retrofit = new Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(httpClient)
            .addConverterFactory(GsonConverterFactory.create())
            .build();

        this.client = retrofit.create(RustChainClient.class);
    }

    public RustChainClient getClient() {
        return client;
    }

    public String getBaseUrl() {
        return baseUrl;
    }
}"""

def generate_wallet_utils():
    return """package io.rustchain.sdk.wallet;

import org.bouncycastle.crypto.generators.Ed25519KeyPairGenerator;
import org.bouncycastle.crypto.params.Ed25519KeyGenerationParameters;
import org.bouncycastle.crypto.params.Ed25519PrivateKeyParameters;
import org.bouncycastle.crypto.params.Ed25519PublicKeyParameters;
import org.bouncycastle.crypto.AsymmetricCipherKeyPair;
import java.security.SecureRandom;
import java.util.Base64;

public class WalletUtils {
    private static final SecureRandom RANDOM = new SecureRandom();

    public static class KeyPair {
        private final String privateKey;
        private final String publicKey;

        public KeyPair(String privateKey, String publicKey) {
            this.privateKey = privateKey;
            this.publicKey = publicKey;
        }

        public String getPrivateKey() { return privateKey; }
        public String getPublicKey() { return publicKey; }
    }

    public static KeyPair generateKeyPair() {
        Ed25519KeyPairGenerator generator = new Ed25519KeyPairGenerator();
        generator.init(new Ed25519KeyGenerationParameters(RANDOM));

        AsymmetricCipherKeyPair keyPair = generator.generateKeyPair();
        Ed25519PrivateKeyParameters privateKey = (Ed25519PrivateKeyParameters) keyPair.getPrivate();
        Ed25519PublicKeyParameters publicKey = (Ed25519PublicKeyParameters) keyPair.getPublic();

        String privateKeyB64 = Base64.getEncoder().encodeToString(privateKey.getEncoded());
        String publicKeyB64 = Base64.getEncoder().encodeToString(publicKey.getEncoded());

        return new KeyPair(privateKeyB64, publicKeyB64);
    }

    public static String generateAddress(String publicKey) {
        // Simple RustChain address format: rtc_ + first 32 chars of base64 pubkey
        return "rtc_" + publicKey.substring(0, Math.min(32, publicKey.length()));
    }

    public static boolean isValidAddress(String address) {
        return address != null && address.startsWith("rtc_") && address.length() >= 36;
    }
}"""

def generate_cli_app():
    return """package io.rustchain.cli;

import io.rustchain.sdk.RustChainSDK;
import io.rustchain.sdk.wallet.WalletUtils;
import java.util.Scanner;

public class RustChainCLI {
    private static RustChainSDK sdk;
    private static Scanner scanner = new Scanner(System.in);

    public static void main(String[] args) {
        System.out.println("RustChain CLI Wallet v1.0");
        System.out.println("========================");

        System.out.print("Enter RustChain node URL (default: http://localhost:8080): ");
        String nodeUrl = scanner.nextLine().trim();
        if (nodeUrl.isEmpty()) {
            nodeUrl = "http://localhost:8080";
        }

        sdk = new RustChainSDK(nodeUrl);

        while (true) {
            showMenu();
            String choice = scanner.nextLine().trim();

            switch (choice) {
                case "1":
                    generateNewWallet();
                    break;
                case "2":
                    checkBalance();
                    break;
                case "3":
                    showLatestBlock();
                    break;
                case "4":
                    showNodeStatus();
                    break;
                case "0":
                    System.out.println("Goodbye!");
                    System.exit(0);
                    break;
                default:
                    System.out.println("Invalid choice. Please try again.");
            }
        }
    }

    private static void showMenu() {
        System.out.println("\\nChoose an option:");
        System.out.println("1. Generate new wallet");
        System.out.println("2. Check balance");
        System.out.println("3. Show latest block");
        System.out.println("4. Show node status");
        System.out.println("0. Exit");
        System.out.print("Choice: ");
    }

    private static void generateNewWallet() {
        WalletUtils.KeyPair keyPair = WalletUtils.generateKeyPair();
        String address = WalletUtils.generateAddress(keyPair.getPublicKey());

        System.out.println("\\nNew wallet generated:");
        System.out.println("Address: " + address);
        System.out.println("Public Key: " + keyPair.getPublicKey());
        System.out.println("Private Key: " + keyPair.getPrivateKey());
        System.out.println("\\n⚠️  IMPORTANT: Save your private key securely!");
    }

    private static void checkBalance() {
        System.out.print("Enter RustChain address: ");
        String address = scanner.nextLine().trim();

        if (!WalletUtils.isValidAddress(address)) {
            System.out.println("Invalid address format!");
            return;
        }

        try {
            // This would make actual API call to get balance
            System.out.println("Balance check for " + address + " would be performed here.");
            System.out.println("(API integration needed)");
        } catch (Exception e) {
            System.out.println("Error checking balance: " + e.getMessage());
        }
    }

    private static void showLatestBlock() {
        try {
            System.out.println("Latest block info would be displayed here.");
            System.out.println("(API integration needed)");
        } catch (Exception e) {
            System.out.println("Error fetching latest block: " + e.getMessage());
        }
    }

    private static void showNodeStatus() {
        try {
            System.out.println("Node status would be displayed here.");
            System.out.println("(API integration needed)");
        } catch (Exception e) {
            System.out.println("Error fetching node status: " + e.getMessage());
        }
    }
}"""

def generate_readme():
    return """# RustChain Java SDK

Java SDK and tools for RustChain blockchain integration.

## Features

- RustChain API client with Retrofit
- Ed25519 wallet utilities with BouncyCastle
- CLI wallet application
- Maven and Gradle build support

## Quick Start

### Maven

Add to your `pom.xml`:

```xml
<dependency>
    <groupId>io.rustchain</groupId>
    <artifactId>rustchain-java-sdk</artifactId>
    <version>1.0.0</version>
</dependency>
```

### Gradle

Add to your `build.gradle`:

```gradle
implementation 'io.rustchain:rustchain-java-sdk:1.0.0'
```

## Usage

### Basic SDK Usage

```java
RustChainSDK sdk = new RustChainSDK("http://localhost:8080");
RustChainClient client = sdk.getClient();

// Get latest block
Call<Map<String, Object>> call = client.getLatestBlock();
```

### Wallet Operations

```java
// Generate new wallet
WalletUtils.KeyPair keyPair = WalletUtils.generateKeyPair();
String address = WalletUtils.generateAddress(keyPair.getPublicKey());

// Validate address
boolean isValid = WalletUtils.isValidAddress("rtc_abc123...");
```

### CLI Wallet

Run the CLI application:

```bash
mvn compile exec:java -Dexec.mainClass="io.rustchain.cli.RustChainCLI"
```

Or with Gradle:

```bash
gradle run
```

## Building

### Maven

```bash
mvn clean package
```

### Gradle

```bash
gradle build
```

## Requirements

- Java 11 or higher
- Maven 3.6+ or Gradle 7+

## License

MIT License
"""

@app.route('/java-tools')
def java_tools_page():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>RustChain Java SDK Generator</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
        .container { background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; margin-bottom: 30px; }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; color: #555; }
        input, select { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 16px; }
        .btn { background: #007bff; color: white; padding: 12px 24px; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }
        .btn:hover { background: #0056b3; }
        .info { background: #e7f3ff; padding: 15px; border-radius: 4px; margin-bottom: 20px; border-left: 4px solid #007bff; }
    </style>
</head>
<body>
    <div class="container">
        <h1>RustChain Java SDK Generator</h1>

        <div class="info">
            <strong>Generate production-ready Java SDK for RustChain integration</strong><br>
            Includes Maven/Gradle projects, CLI tools, wallet utilities, and API clients.
        </div>

        <form action="/generate-java-sdk" method="post">
            <div class="form-group">
                <label>Group ID:</label>
                <input type="text" name="group_id" value="io.rustchain" required>
            </div>

            <div class="form-group">
                <label>Artifact ID:</label>
                <input type="text" name="artifact_id" value="rustchain-java-sdk" required>
            </div>

            <div class="form-group">
                <label>Version:</label>
                <input type="text" name="version" value="1.0.0" required>
            </div>

            <div class="form-group">
                <label>Project Type:</label>
                <select name="project_type" required>
                    <option value="complete">Complete SDK (CLI + Libraries)</option>
                    <option value="sdk-only">SDK Library Only</option>
                    <option value="cli-only">CLI Tools Only</option>
                </select>
            </div>

            <button type="submit" class="btn">Generate Java Project</button>
        </form>
    </div>
</body>
</html>
    """)

@app.route('/generate-java-sdk', methods=['POST'])
def generate_java_sdk():
    group_id = request.form['group_id']
    artifact_id = request.form['artifact_id']
    version = request.form['version']
    project_type = request.form['project_type']

    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, f"{artifact_id}-{version}.zip")

    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Build files
            zipf.writestr('pom.xml', generate_pom_xml(group_id, artifact_id, version))
            zipf.writestr('build.gradle', generate_build_gradle(group_id, artifact_id, version))
            zipf.writestr('README.md', generate_readme())

            # Source directory structure
            src_base = 'src/main/java/'
            package_path = group_id.replace('.', '/')

            if project_type in ['complete', 'sdk-only']:
                # SDK core files
                zipf.writestr(f'{src_base}{package_path}/sdk/RustChainClient.java', generate_rustchain_client())
                zipf.writestr(f'{src_base}{package_path}/sdk/RustChainSDK.java', generate_rustchain_sdk())
                zipf.writestr(f'{src_base}{package_path}/sdk/wallet/WalletUtils.java', generate_wallet_utils())

            if project_type in ['complete', 'cli-only']:
                # CLI application
                zipf.writestr(f'{src_base}{package_path}/cli/RustChainCLI.java', generate_cli_app())

            # Test directory structure
            test_base = 'src/test/java/'
            zipf.writestr(f'{test_base}{package_path}/sdk/RustChainSDKTest.java',
                         'package ' + group_id + '.sdk;\n\n' +
                         'import org.junit.jupiter.api.Test;\n' +
                         'import static org.junit.jupiter.api.Assertions.*;\n\n' +
                         'public class RustChainSDKTest {\n' +
                         '    @Test\n' +
                         '    public void testSDKInitialization() {\n' +
                         '        RustChainSDK sdk = new RustChainSDK("http://localhost:8080");\n' +
                         '        assertNotNull(sdk.getClient());\n' +
                         '        assertEquals("http://localhost:8080", sdk.getBaseUrl());\n' +
                         '    }\n' +
                         '}')

        return send_file(zip_path,
                        as_attachment=True,
                        download_name=f"{artifact_id}-{version}.zip",
                        mimetype='application/zip')

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/java-tools/status')
def java_tools_status():
    return jsonify({
        "status": "active",
        "generator_version": "1.0.0",
        "supported_features": [
            "Maven project generation",
            "Gradle project generation",
            "Retrofit API client",
            "Ed25519 wallet utilities",
            "CLI wallet application",
            "Unit test templates"
        ],
        "timestamp": datetime.now().isoformat()
    })

if __name__ == '__main__':
    app.run(debug=True, port=5003)
