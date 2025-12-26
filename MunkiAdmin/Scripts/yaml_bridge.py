#!/usr/bin/env python3
"""
YAML to Property List converter for MunkiAdmin
Provides a robust bridge between YAML files and Objective-C NSDictionary objects

Implements the same key ordering as yamlutils.swift in the Munki CLI tools:
- Priority keys first: name, display_name, version
- All other keys alphabetically
- _metadata last

Note: Munki's Swift tools now handle unquoted version-like values (e.g., 10.12)
correctly via type coercion, so we don't force quotes on output.
"""

import sys
import yaml
import plistlib
import json
import io
from pathlib import Path

# Keys that should appear first in pkginfo YAML output, in this order
PRIORITY_KEYS = ['name', 'display_name', 'version']

# Keys that should appear last in pkginfo YAML output
LAST_KEYS = ['_metadata']

# Preferred key order for receipt entries - packageid first
RECEIPT_KEY_ORDER = ['packageid', 'name', 'filename', 'installed_size', 'version', 'optional']

# Preferred key order for installs items - path first
INSTALLS_KEY_ORDER = ['path', 'type', 'CFBundleIdentifier', 'CFBundleName', 
                      'CFBundleShortVersionString', 'CFBundleVersion', 'md5checksum', 'minosversion']

class RobustYAMLLoader:
    """A robust YAML loader that handles common real-world issues"""
    
    @staticmethod
    def safe_load_yaml(content):
        """Safely load YAML with multiple fallback strategies"""
        
        # Strategy 1: Try standard safe_load first
        try:
            return yaml.safe_load(content)
        except yaml.YAMLError as e:
            print(f"Standard YAML parsing failed: {e}", file=sys.stderr)
        
        # Strategy 2: Try with custom loader for common issues
        try:
            # Handle common munki-specific YAML issues
            content = RobustYAMLLoader.preprocess_yaml(content)
            return yaml.safe_load(content)
        except yaml.YAMLError as e:
            print(f"Preprocessed YAML parsing failed: {e}", file=sys.stderr)
        
        # Strategy 3: Try line-by-line parsing for very long lines
        try:
            return RobustYAMLLoader.parse_chunked_yaml(content)
        except Exception as e:
            print(f"Chunked YAML parsing failed: {e}", file=sys.stderr)
        
        return None
    
    @staticmethod
    def preprocess_yaml(content):
        """Preprocess YAML content to handle common issues"""
        lines = content.splitlines()
        processed_lines = []
        
        for line_num, line in enumerate(lines, 1):
            # Handle excessively long lines by truncating at word boundaries
            if len(line) > 10000:
                # Find last word boundary before limit
                truncate_pos = 9000
                while truncate_pos > 8000 and line[truncate_pos] not in ' \t':
                    truncate_pos -= 1
                
                if truncate_pos > 8000:
                    line = line[:truncate_pos] + "..."
                    print(f"Warning: Truncated long line {line_num} at {truncate_pos} characters", file=sys.stderr)
                else:
                    # If no word boundary found, hard truncate
                    line = line[:9000] + "..."
                    print(f"Warning: Hard truncated line {line_num}", file=sys.stderr)
            
            # Handle tab characters
            if '\t' in line:
                line = line.expandtabs(2)
            
            # Handle some common encoding issues
            try:
                line.encode('utf-8')
            except UnicodeEncodeError:
                # Replace problematic characters
                line = line.encode('utf-8', errors='replace').decode('utf-8')
                print(f"Warning: Fixed encoding issues on line {line_num}", file=sys.stderr)
            
            processed_lines.append(line)
        
        return '\n'.join(processed_lines)
    
    @staticmethod
    def parse_chunked_yaml(content):
        """Parse YAML by processing in chunks to handle large files"""
        # This is a simplified approach - split into logical YAML sections
        # and try to parse each section separately if the full parse fails
        
        lines = content.splitlines()
        if len(lines) < 100:
            # For small files, just fail normally
            return yaml.safe_load(content)
        
        # Try to identify YAML document boundaries
        yaml_docs = []
        current_doc = []
        
        for line in lines:
            if line.strip() == '---' and current_doc:
                # Found document separator
                yaml_docs.append('\n'.join(current_doc))
                current_doc = []
            else:
                current_doc.append(line)
        
        if current_doc:
            yaml_docs.append('\n'.join(current_doc))
        
        # If we found multiple documents, try to parse the first valid one
        if len(yaml_docs) > 1:
            for i, doc in enumerate(yaml_docs):
                try:
                    result = yaml.safe_load(doc)
                    if result is not None:
                        print(f"Successfully parsed YAML document {i+1} of {len(yaml_docs)}", file=sys.stderr)
                        return result
                except yaml.YAMLError:
                    continue
        
        # Fall back to original content
        raise yaml.YAMLError("All chunked parsing attempts failed")

def yaml_to_dict(yaml_file_path):
    """Convert YAML file to Python dictionary with robust error handling"""
    try:
        # Basic file checks
        file_path = Path(yaml_file_path)
        if not file_path.exists():
            print(f"Error: File not found: {yaml_file_path}", file=sys.stderr)
            return None
        
        file_size = file_path.stat().st_size
        
        # More reasonable size limits
        if file_size > 50 * 1024 * 1024:  # 50MB absolute limit
            print(f"Error: YAML file too large ({file_size} bytes)", file=sys.stderr)
            return None
        
        # Read file with robust encoding handling
        content = None
        encodings = ['utf-8', 'utf-8-sig', 'latin1', 'cp1252']
        
        for encoding in encodings:
            try:
                with open(yaml_file_path, 'r', encoding=encoding) as file:
                    content = file.read()
                break
            except UnicodeDecodeError:
                continue
        
        if content is None:
            print(f"Error: Unable to decode file with any supported encoding", file=sys.stderr)
            return None
        
        # Handle empty files
        if not content.strip():
            print("Warning: Empty YAML file", file=sys.stderr)
            return {}
        
        # Use robust YAML loader
        return RobustYAMLLoader.safe_load_yaml(content)
            
    except Exception as e:
        print(f"Error reading YAML file: {e}", file=sys.stderr)
        return None

def dict_to_plist_string(data):
    """Convert Python dictionary to property list XML string"""
    try:
        # Remove order preservation markers before converting to plist
        cleaned_data = remove_order_markers(data)
        return plistlib.dumps(cleaned_data).decode('utf-8')
    except Exception as e:
        print(f"Error converting to plist: {e}", file=sys.stderr)
        return None

def remove_order_markers(data):
    """Remove __ordered_keys__ markers from data structure"""
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if key == '__ordered_keys__':
                continue
            result[key] = remove_order_markers(value)
        return result
    elif isinstance(data, list):
        return [remove_order_markers(item) for item in data]
    else:
        return data

def dict_to_yaml_string(data):
    """Convert Python dictionary to YAML string with pkginfo key ordering.
    
    Implements the same key ordering as yamlutils.swift:
    - name, display_name, version first
    - All other keys alphabetically
    - _metadata last
    
    Note: We don't force quotes on version-like values since Munki's Swift
    tools now handle type coercion correctly.
    """
    try:
        # Process data to apply pkginfo key ordering
        ordered_data = order_pkginfo_keys(data)
        
        yaml_string = yaml.dump(ordered_data, Dumper=yaml.SafeDumper, 
                               default_flow_style=False, allow_unicode=True, sort_keys=False)
        
        # Remove trailing newline added by yaml.dump() to match Swift tool behavior
        return yaml_string.rstrip('\n')
    except Exception as e:
        print(f"Error converting to YAML: {e}", file=sys.stderr)
        return None

def is_receipt_dict(d):
    """Check if a dictionary looks like a receipt entry."""
    return isinstance(d, dict) and 'packageid' in d

def is_installs_dict(d):
    """Check if a dictionary looks like an installs item."""
    return isinstance(d, dict) and 'path' in d and 'type' in d

def sort_receipt_keys(keys):
    """Sort receipt dictionary keys with packageid first."""
    ordered = []
    other = []
    for key in keys:
        if key in RECEIPT_KEY_ORDER:
            ordered.append(key)
        else:
            other.append(key)
    # Sort ordered keys by their position in RECEIPT_KEY_ORDER
    ordered.sort(key=lambda k: RECEIPT_KEY_ORDER.index(k) if k in RECEIPT_KEY_ORDER else 999)
    other.sort()
    return ordered + other

def sort_installs_keys(keys):
    """Sort installs item dictionary keys with path first."""
    ordered = []
    other = []
    for key in keys:
        if key in INSTALLS_KEY_ORDER:
            ordered.append(key)
        else:
            other.append(key)
    # Sort ordered keys by their position in INSTALLS_KEY_ORDER
    ordered.sort(key=lambda k: INSTALLS_KEY_ORDER.index(k) if k in INSTALLS_KEY_ORDER else 999)
    other.sort()
    return ordered + other

def sort_pkginfo_keys(keys):
    """Sort pkginfo dictionary keys with custom ordering.
    
    - name, display_name, version appear first (in that order)
    - _metadata appears last
    - All other keys appear alphabetically in between
    """
    first_keys = []
    middle_keys = []
    end_keys = []
    
    for key in keys:
        if key in PRIORITY_KEYS:
            first_keys.append(key)
        elif key in LAST_KEYS:
            end_keys.append(key)
        else:
            middle_keys.append(key)
    
    # Sort first keys by their position in PRIORITY_KEYS
    first_keys.sort(key=lambda k: PRIORITY_KEYS.index(k) if k in PRIORITY_KEYS else 999)
    
    # Sort middle keys alphabetically
    middle_keys.sort()
    
    # Sort end keys alphabetically
    end_keys.sort()
    
    return first_keys + middle_keys + end_keys

def order_pkginfo_keys(data):
    """Recursively order keys in a pkginfo dictionary structure."""
    if isinstance(data, dict):
        # Remove order preservation markers
        clean_data = {k: v for k, v in data.items() if k != '__ordered_keys__'}
        
        # Determine sort order based on dict type
        if is_receipt_dict(clean_data):
            sorted_keys = sort_receipt_keys(clean_data.keys())
        elif is_installs_dict(clean_data):
            sorted_keys = sort_installs_keys(clean_data.keys())
        else:
            sorted_keys = sort_pkginfo_keys(clean_data.keys())
        
        # Create ordered dictionary
        result = {}
        for key in sorted_keys:
            value = clean_data[key]
            result[key] = order_pkginfo_keys(value)
        
        return result
    elif isinstance(data, list):
        return [order_pkginfo_keys(item) for item in data]
    else:
        return data

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
