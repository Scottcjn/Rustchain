#!/bin/bash
# RustChain Java SDK Build Script
# This script builds the project using Maven or manual compilation

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "RustChain Java SDK Build Script"
echo "================================"
echo

# Check for Maven
if command -v mvn &> /dev/null; then
    echo "Found Maven, building..."
    mvn clean package -DskipTests
    echo
    echo "Build complete! JAR file: target/rustchain-java-sdk-1.0.0.jar"
    exit 0
fi

echo "Maven not found. Checking for manual compilation..."

# Check for Java compiler
if ! command -v javac &> /dev/null; then
    echo "Error: javac not found. Please install JDK 11+ or Maven."
    exit 1
fi

# Create output directory
mkdir -p target/classes
mkdir -p target/lib

# Download dependencies if not present
if [ ! -f target/lib/jackson-databind.jar ]; then
    echo "Downloading dependencies..."
    LIB_DIR="target/lib"
    
    # Jackson dependencies
    curl -sL -o "$LIB_DIR/jackson-databind.jar" \
        "https://repo1.maven.org/maven2/com/fasterxml/jackson/core/jackson-databind/2.16.1/jackson-databind-2.16.1.jar"
    curl -sL -o "$LIB_DIR/jackson-core.jar" \
        "https://repo1.maven.org/maven2/com/fasterxml/jackson/core/jackson-core/2.16.1/jackson-core-2.16.1.jar"
    curl -sL -o "$LIB_DIR/jackson-annotations.jar" \
        "https://repo1.maven.org/maven2/com/fasterxml/jackson/core/jackson-annotations/2.16.1/jackson-annotations-2.16.1.jar"
    
    # picocli
    curl -sL -o "$LIB_DIR/picocli.jar" \
        "https://repo1.maven.org/maven2/info/picocli/picocli/4.7.5/picocli-4.7.5.jar"
    
    # SLF4J
    curl -sL -o "$LIB_DIR/slf4j-api.jar" \
        "https://repo1.maven.org/maven2/org/slf4j/slf4j-api/2.0.11/slf4j-api-2.0.11.jar"
    curl -sL -o "$LIB_DIR/slf4j-simple.jar" \
        "https://repo1.maven.org/maven2/org/slf4j/slf4j-simple/2.0.11/slf4j-simple-2.0.11.jar"
    
    echo "Dependencies downloaded."
fi

# Build classpath
CLASSPATH="target/classes"
for jar in target/lib/*.jar; do
    CLASSPATH="$CLASSPATH:$jar"
done

# Compile
echo "Compiling Java sources..."
find src/main/java -name "*.java" > sources.txt
javac -d target/classes -cp "$CLASSPATH" -source 11 -target 11 @sources.txt
rm sources.txt

echo
echo "Build complete! Classes: target/classes/"
echo
echo "To run the CLI:"
echo "  java -cp \"target/classes:target/lib/*\" com.rustchain.cli.RustChainCLI --help"
echo
echo "To create a fat JAR, install Maven and run: mvn package"
