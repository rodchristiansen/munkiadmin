#!/usr/bin/env python3
"""
YAML to Property List converter for MunkiAdmin
Provides a bridge between YAML files and Objective-C NSDictionary objects
"""

import sys
import yaml
import plistlib
import json
from pathlib import Path

def yaml_to_dict(yaml_file_path):
    """Convert YAML file to Python dictionary with fast pre-checks"""
    try:
        # Fast file size check first
        file_size = Path(yaml_file_path).stat().st_size
        if file_size > 5 * 1024 * 1024:  # 5MB limit (reduced from 10MB)
            print(f"Error: YAML file too large ({file_size} bytes)", file=sys.stderr)
            return None
        
        # Quick line length check without reading entire file
        with open(yaml_file_path, 'r', encoding='utf-8') as file:
            # Check first few lines for structure
            first_lines = []
            char_count = 0
            for i, line in enumerate(file):
                char_count += len(line)
                first_lines.append(line)
                
                # Quick exit if we hit a super long line early
                if len(line) > 20000:  # Reduced threshold for faster detection
                    print(f"Error: YAML contains very long line ({len(line)} chars) at line {i+1}", file=sys.stderr)
                    return None
                
                # Stop after checking first 50 lines or 100KB
                if i >= 50 or char_count > 100000:
                    break
        
        # If we got here, try to parse the full file
        with open(yaml_file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            
            # Check for tab characters and fix them
            if '\t' in content:
                print("Warning: Converting tabs to spaces", file=sys.stderr)
                content = content.expandtabs(2)
            
            return yaml.safe_load(content)
            
    except Exception as e:
        print(f"Error reading YAML file: {e}", file=sys.stderr)
        return None

def dict_to_plist_string(data):
    """Convert Python dictionary to property list XML string"""
    try:
        return plistlib.dumps(data).decode('utf-8')
    except Exception as e:
        print(f"Error converting to plist: {e}", file=sys.stderr)
        return None

def dict_to_yaml_string(data):
    """Convert Python dictionary to YAML string"""
    try:
        return yaml.dump(data, default_flow_style=False, allow_unicode=True)
    except Exception as e:
        print(f"Error converting to YAML: {e}", file=sys.stderr)
        return None

def main():
    if len(sys.argv) < 3:
        print("Usage: yaml_bridge.py <input_file> <output_format>")
        print("  output_format: plist, json, yaml")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_format = sys.argv[2].lower()
    
    if not Path(input_file).exists():
        print(f"Error: File not found: {input_file}", file=sys.stderr)
        sys.exit(1)
    
    # Determine input format
    if input_file.lower().endswith(('.yaml', '.yml')):
        data = yaml_to_dict(input_file)
    elif input_file.lower().endswith('.plist'):
        try:
            with open(input_file, 'rb') as file:
                data = plistlib.load(file)
        except Exception as e:
            print(f"Error reading plist file: {e}", file=sys.stderr)
            sys.exit(1)
    elif input_file.lower().endswith('.json'):
        try:
            with open(input_file, 'r', encoding='utf-8') as file:
                data = json.load(file)
        except Exception as e:
            print(f"Error reading JSON file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("Error: Unsupported input file format", file=sys.stderr)
        sys.exit(1)
    
    if data is None:
        sys.exit(1)
    
    # Convert to requested output format
    if output_format == 'plist':
        result = dict_to_plist_string(data)
    elif output_format == 'json':
        try:
            result = json.dumps(data, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error converting to JSON: {e}", file=sys.stderr)
            sys.exit(1)
    elif output_format == 'yaml':
        result = dict_to_yaml_string(data)
    else:
        print("Error: Unsupported output format", file=sys.stderr)
        sys.exit(1)
    
    if result:
        print(result)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
