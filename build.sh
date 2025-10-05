#!/bin/bash

# MunkiAdmin Build, Sign, and Notarize Script
# Handles Icon Composer integration, code signing, and notarization
# Uses .env file for secure credential management

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"

# Load environment variables from .env file
if [ -f "$SCRIPT_DIR/.env" ]; then
    echo -e "${BLUE}Loading credentials from .env file...${NC}"
    # Load variables from .env file properly handling spaces and special chars
    while IFS= read -r line; do
        if [[ $line =~ ^[^#]*= ]] && [[ ! $line =~ ^[[:space:]]*$ ]]; then
            # Remove quotes if present and export
            eval "export $line"
        fi
    done < "$SCRIPT_DIR/.env"
else
    echo -e "${RED}Error: .env file not found. Please create one with your credentials.${NC}"
    echo -e "${YELLOW}Required variables:${NC}"
    echo "TEAM_ID=7TF6CSP83S"
    echo "SIGNING_IDENTITY=Developer ID Application: Emily Carr University of Art and Design (7TF6CSP83S)"
    echo "KEYCHAIN_PROFILE=notarization_credentials"
    exit 1
fi

# Validate required environment variables
required_vars=("TEAM_ID" "SIGNING_IDENTITY" "KEYCHAIN_PROFILE")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo -e "${RED}Error: $var is not set in .env file${NC}"
        exit 1
    fi
done

# Project settings
WORKSPACE_FILE="MunkiAdmin.xcworkspace"
SCHEME="MunkiAdmin"
CONFIGURATION="Release"
APP_NAME="MunkiAdmin"

# Generate date-based version (YYYY.MM.DD.HHMM)
DATE_VERSION=$(date +"%Y.%m.%d.%H%M")
echo -e "${BLUE}Fork version: ${DATE_VERSION}${NC}"

# Build paths
BUILD_DIR="$HOME/Library/Developer/Xcode/DerivedData/MunkiAdmin-bkxgphikjyusbkgzxdtbtgohyoxk/Build/Products/$CONFIGURATION"
APP_PATH="$BUILD_DIR/$APP_NAME.app"
ZIP_PATH="$BUILD_DIR/$APP_NAME.zip"
ENTITLEMENTS_PATH="$PROJECT_DIR/MunkiAdmin/MunkiAdmin.entitlements"

# Functions
print_step() {
    echo -e "\n${BLUE}==== $1 ====${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

check_prerequisites() {
    print_step "Checking Prerequisites"
    
    # Check if we're in the right directory
    if [ ! -d "$WORKSPACE_FILE" ]; then
        print_error "MunkiAdmin.xcworkspace not found. Are you in the project directory?"
        exit 1
    fi
    
    # Check if entitlements file exists
    if [ ! -f "$ENTITLEMENTS_PATH" ]; then
        print_error "Entitlements file not found at $ENTITLEMENTS_PATH"
        exit 1
    fi
    
    # Check if signing identity exists
    if ! security find-identity -v -p codesigning | grep -q -F "$SIGNING_IDENTITY"; then
        print_error "Signing identity not found: $SIGNING_IDENTITY"
        echo "Available identities:"
        security find-identity -v -p codesigning
        exit 1
    fi
    
    print_success "Prerequisites check passed"
}

setup_keychain_profile() {
    print_step "Checking Keychain Profile"
    
    # Check if profile exists and works
    if xcrun notarytool history --keychain-profile "$KEYCHAIN_PROFILE" --team-id "$TEAM_ID" >/dev/null 2>&1; then
        print_success "Keychain profile '$KEYCHAIN_PROFILE' is ready"
        return 0
    else
        print_error "Keychain profile '$KEYCHAIN_PROFILE' not found or invalid"
        echo -e "${YELLOW}You need to create this profile manually with:${NC}"
        echo "xcrun notarytool store-credentials \"$KEYCHAIN_PROFILE\" --apple-id YOUR_APPLE_ID --team-id \"$TEAM_ID\" --password"
        exit 1
    fi
}

clean_build() {
    print_step "Cleaning Previous Build"
    
    xcodebuild clean \
        -workspace "$WORKSPACE_FILE" \
        -scheme "$SCHEME" \
        -configuration "$CONFIGURATION"
    
    print_success "Clean completed"
}

build_app() {
    print_step "Building MunkiAdmin with Icon Composer Integration"
    echo -e "${BLUE}Version will be set dynamically by Xcode build script: ${DATE_VERSION}${NC}"
    
    xcodebuild build \
        -workspace "$WORKSPACE_FILE" \
        -scheme "$SCHEME" \
        -configuration "$CONFIGURATION" \
        -destination "platform=macOS" \
        CODE_SIGN_IDENTITY="" \
        CODE_SIGNING_REQUIRED=NO
    
    if [ $? -eq 0 ]; then
        print_success "Build completed successfully"
        
        # Check if Icon Composer assets were generated
        if [ -f "$APP_PATH/Contents/Resources/Assets.car" ]; then
            ASSETS_SIZE=$(du -h "$APP_PATH/Contents/Resources/Assets.car" | cut -f1)
            print_success "Icon Composer Assets.car generated: $ASSETS_SIZE"
        else
            print_warning "Assets.car not found - Icon Composer may not have processed correctly"
        fi
    else
        print_error "Build failed"
        exit 1
    fi
}

sign_app() {
    print_step "Code Signing Application"
    
    # Remove existing signature
    codesign --remove-signature "$APP_PATH" 2>/dev/null || true
    
    # Sign with Developer ID
    codesign --force \
        --sign "$SIGNING_IDENTITY" \
        --options runtime \
        --entitlements "$ENTITLEMENTS_PATH" \
        --timestamp \
        --deep \
        "$APP_PATH"
    
    if [ $? -eq 0 ]; then
        print_success "Code signing completed"
        
        # Verify signature
        print_step "Verifying Code Signature"
        if codesign --verify --deep --strict --verbose=2 "$APP_PATH"; then
            print_success "Code signature verification passed"
        else
            print_error "Code signature verification failed"
            exit 1
        fi
    else
        print_error "Code signing failed"
        exit 1
    fi
}

create_archive() {
    print_step "Creating Archive for Notarization"
    
    # Remove existing archive
    rm -f "$ZIP_PATH"
    
    # Create ZIP archive
    cd "$BUILD_DIR"
    ditto -c -k --keepParent "$APP_NAME.app" "$APP_NAME.zip"
    cd - > /dev/null
    
    if [ -f "$ZIP_PATH" ]; then
        ZIP_SIZE=$(du -h "$ZIP_PATH" | cut -f1)
        print_success "Archive created: $ZIP_SIZE"
    else
        print_error "Failed to create archive"
        exit 1
    fi
}

notarize_app() {
    print_step "Submitting for Notarization"
    
    # Submit for notarization
    NOTARIZATION_OUTPUT=$(xcrun notarytool submit "$ZIP_PATH" \
        --keychain-profile "$KEYCHAIN_PROFILE" \
        --team-id "$TEAM_ID" \
        --wait 2>&1)
    
    echo "$NOTARIZATION_OUTPUT"
    
    if echo "$NOTARIZATION_OUTPUT" | grep -q "status: Accepted"; then
        print_success "Notarization completed successfully"
        
        # Extract submission ID for stapling
        SUBMISSION_ID=$(echo "$NOTARIZATION_OUTPUT" | grep "id:" | head -1 | awk '{print $2}')
        
        if [ ! -z "$SUBMISSION_ID" ]; then
            print_step "Stapling Notarization Ticket"
            
            if xcrun stapler staple "$APP_PATH"; then
                print_success "Notarization ticket stapled successfully"
            else
                print_warning "Failed to staple notarization ticket, but notarization was successful"
            fi
        fi
        
        return 0
    elif echo "$NOTARIZATION_OUTPUT" | grep -q "status: Invalid"; then
        print_error "Notarization failed - Invalid submission"
        
        # Get submission ID for more details
        SUBMISSION_ID=$(echo "$NOTARIZATION_OUTPUT" | grep "id:" | head -1 | awk '{print $2}')
        if [ ! -z "$SUBMISSION_ID" ]; then
            print_step "Getting Notarization Log"
            xcrun notarytool log "$SUBMISSION_ID" --keychain-profile "$KEYCHAIN_PROFILE" --team-id "$TEAM_ID"
        fi
        exit 1
    else
        print_error "Notarization failed or timed out"
        echo "$NOTARIZATION_OUTPUT"
        exit 1
    fi
}

verify_final_app() {
    print_step "Final Verification"
    
    # Check Gatekeeper
    if spctl --assess --verbose "$APP_PATH"; then
        print_success "Gatekeeper assessment passed"
    else
        print_warning "Gatekeeper assessment failed"
    fi
    
    # Check notarization status
    if xcrun stapler validate "$APP_PATH"; then
        print_success "Notarization ticket validation passed"
    else
        print_warning "Notarization ticket validation failed"
    fi
    
    # Display app info
    APP_SIZE=$(du -sh "$APP_PATH" | cut -f1)
    APP_VERSION=$(defaults read "$APP_PATH/Contents/Info.plist" CFBundleShortVersionString 2>/dev/null || echo "Unknown")
    
    print_success "Final app size: $APP_SIZE"
    print_success "App version: $APP_VERSION"
    print_success "App location: $APP_PATH"
}

# Main execution
main() {
    echo -e "${GREEN}"
    echo "╔════════════════════════════════════════════╗"
    echo "║     MunkiAdmin Build & Notarize Script     ║"
    echo "║    with Icon Composer Integration          ║"
    echo "╚════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    check_prerequisites
    setup_keychain_profile
    clean_build
    build_app
    sign_app
    create_archive
    notarize_app
    verify_final_app
    
    echo -e "\n${GREEN}"
    echo "╔════════════════════════════════════════════╗"
    echo "║            SUCCESS!                        ║"
    echo "║   MunkiAdmin has been built, signed,       ║"
    echo "║   and notarized with Icon Composer         ║"
    echo "╚════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    echo -e "${BLUE}Ready for distribution:${NC}"
    echo -e "App: ${APP_PATH}"
    echo -e "Archive: ${ZIP_PATH}"
}

# Run main function
main "$@"