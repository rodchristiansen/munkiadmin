# YAML Support in MunkiAdmin

## Overview

MunkiAdmin now has complete YAML support for pkginfo files and manifests, providing seamless handling of both traditional plist and modern YAML formats.

## Features

- **Format Preservation**: Edit YAML files and they remain as YAML (no conversion to plist)
- **Auto-Detection**: Automatically detects repository format preferences
- **Mixed Repository Support**: Handle repositories with both plist and YAML files
- **Backward Compatibility**: Existing plist workflows continue to work unchanged

## Implementation

### Core Components

- **YAML Bridge**: Python script (`yaml_bridge.py`) handles YAML ↔ JSON conversion
- **Repository Manager**: Enhanced with format detection and YAML-aware I/O operations
- **File Scanners**: Updated to handle both plist and YAML formats dynamically

### Format Detection

The app automatically detects your repository's preferred format by:
1. Checking user preferences
2. Sampling existing files in the repository
3. Falling back to plist as default

### YAML Parsing

Uses PyYAML through a Python bridge for robust YAML parsing:
- Handles complex YAML structures
- Maintains compatibility with munki requirements
- Provides error handling and validation

## Usage

1. **Open Repository**: Works with both plist and YAML repositories
2. **Edit Files**: Make changes in the GUI as usual
3. **Save Changes**: Files are saved in their original format automatically

## Technical Requirements

- Python 3 with PyYAML (for YAML parsing)
- macOS 10.13 or later
- Munki tools installed

## Migration

No migration needed - the app works with your existing repository regardless of format. If you want to convert between formats, use the standard munki tools for that purpose.
