#!/usr/bin/env python3
"""
YAML to Property List converter for MunkiAdmin
Provides a robust bridge between YAML files and Objective-C NSDictionary objects
"""

import sys
import yaml
import plistlib
import json
import io
from pathlib import Path

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
