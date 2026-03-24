@echo off
REM RustChain Java SDK Build Script for Windows

echo RustChain Java SDK Build Script
echo =================================
echo.

REM Check for Maven
where mvn >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo Found Maven, building...
    mvn clean package -DskipTests
    echo.
    echo Build complete! JAR file: target\rustchain-java-sdk-1.0.0.jar
    goto :end
)

echo Maven not found. Checking for Java compiler...

REM Check for Java compiler
where javac >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Error: javac not found. Please install JDK 11+ or Maven.
    goto :end
)

REM Create output directory
if not exist "target\classes" mkdir target\classes
if not exist "target\lib" mkdir target\lib

REM Check for dependencies
if not exist "target\lib\jackson-databind.jar" (
    echo Downloading dependencies...
    
    REM You would need to download jars manually or use a tool like curl
    echo Please install Maven for automatic dependency download.
    goto :end
)

REM Compile
echo Compiling Java sources...
for /r "src\main\java" %%f in (*.java) do (
    echo Compiling %%f
)

REM This is a simplified version - full compilation would need proper classpath
echo.
echo For full build, please install Maven from: https://maven.apache.org/download.cgi
echo Or use the build.sh script on Linux/Mac.

:end
echo.
pause
