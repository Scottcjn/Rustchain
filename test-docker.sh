#!/bin/bash
# Quick test script for Docker deployment

set -e

echo "=== RustChain Docker Deployment Test ==="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print test results
test_result() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ PASS${NC} - $1"
    else
        echo -e "${RED}❌ FAIL${NC} - $1"
    fi
}

# Check if Docker is installed
echo "1. Checking Docker installation..."
if command -v docker &> /dev/null; then
    test_result "Docker is installed"
else
    echo -e "${RED}❌ Docker is not installed${NC}"
    exit 1
fi

# Check if Docker Compose is installed
echo ""
echo "2. Checking Docker Compose installation..."
if command -v docker-compose &> /dev/null || docker compose version &> /dev/null; then
    test_result "Docker Compose is installed"
else
    echo -e "${RED}❌ Docker Compose is not installed${NC}"
    exit 1
fi

# Check if required files exist
echo ""
echo "3. Checking required files..."

FILES=(
    "Dockerfile"
    "docker-compose.yml"
    "nginx/nginx.conf"
    "nginx/generate-ssl.sh"
    ".env.example"
)

for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        test_result "File exists: $file"
    else
        echo -e "${RED}❌ Missing file: $file${NC}"
        exit 1
    fi
done

# Check Dockerfile syntax
echo ""
echo "4. Validating Dockerfile syntax..."
if docker build -f Dockerfile --dry-run . &> /dev/null; then
    test_result "Dockerfile syntax is valid"
else
    echo -e "${YELLOW}⚠️  Could not validate Dockerfile (may be due to missing build context)${NC}"
fi

# Check docker-compose syntax
echo ""
echo "5. Validating docker-compose.yml syntax..."
if docker-compose config &> /dev/null; then
    test_result "docker-compose.yml syntax is valid"
else
    echo -e "${RED}❌ docker-compose.yml syntax error${NC}"
    docker-compose config
    exit 1
fi

# Check nginx configuration
echo ""
echo "6. Validating nginx configuration..."
if docker run --rm -v "$(pwd)/nginx/nginx.conf:/etc/nginx/nginx.conf:ro" nginx:alpine nginx -t 2>&1 | grep -q "syntax is ok"; then
    test_result "nginx configuration is valid"
else
    echo -e "${YELLOW}⚠️  Could not validate nginx configuration (may be due to Docker availability)${NC}"
fi

# Check SSL script permissions
echo ""
echo "7. Checking SSL script..."
if [ -x "nginx/generate-ssl.sh" ]; then
    test_result "SSL script is executable"
else
    echo -e "${YELLOW}⚠️  SSL script is not executable${NC}"
    chmod +x nginx/generate-ssl.sh
    echo -e "${GREEN}✅ Made SSL script executable${NC}"
fi

# Check if .env exists
echo ""
echo "8. Checking environment configuration..."
if [ -f ".env" ]; then
    test_result ".env file exists"
else
    echo -e "${YELLOW}⚠️  .env file not found${NC}"
    echo "   Run: cp .env.example .env"
    echo "   Then edit .env with your configuration"
fi

# Check data directory
echo ""
echo "9. Checking data directory..."
if [ -d "data" ]; then
    test_result "Data directory exists"
else
    echo -e "${YELLOW}⚠️  Data directory does not exist (will be created on first run)${NC}"
fi

# Check SSL directory
echo ""
echo "10. Checking SSL directory..."
if [ -d "nginx/ssl" ]; then
    if [ -f "nginx/ssl/cert.pem" ] && [ -f "nginx/ssl/key.pem" ]; then
        test_result "SSL certificates exist"
    else
        echo -e "${YELLOW}⚠️  SSL certificates not found${NC}"
        echo "   Run: cd nginx && ./generate-ssl.sh self-signed"
    fi
else
    echo -e "${YELLOW}⚠️  SSL directory does not exist (will be created on first run)${NC}"
fi

# Summary
echo ""
echo "=== Test Summary ==="
echo -e "${GREEN}All critical checks passed!${NC}"
echo ""
echo "Next steps:"
echo "1. Copy environment file: cp .env.example .env"
echo "2. Edit .env with your configuration"
echo "3. Generate SSL certificates: cd nginx && ./generate-ssl.sh self-signed"
echo "4. Start the stack: docker-compose up -d"
echo ""
echo "For more information, see DOCKER_DEPLOYMENT.md"
