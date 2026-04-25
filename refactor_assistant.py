#!/usr/bin/env python3
"""Automated refactoring assistant for the Pilomar project."""

import re
import os
from pathlib import Path


class PilomarRefactorer:
    """Assists in refactoring Pilomar code to follow Python best practices."""

    def __init__(self):
        """Initialize the refactorer with naming mappings."""
        # Class name mappings (lowercase -> PascalCase)
        self.class_mappings = {
            'attributemaster': 'AttributeMaster',
            'astrolens': 'AstroLens',
            'astrosensor': 'AstroSensor',
            'astrocamera': 'AstroCamera',
            'camera_util': 'CameraUtil',
            'celestrak': 'Celestrak',
            'cpumonitor': 'CpuMonitor',
            'memorymonitor': 'MemoryMonitor',
            'discmonitor': 'DiskMonitor',
            'logfile': 'LogFile',
            'oscommand': 'OsCommand',
            'timer': 'Timer',
            'progresstimer': 'ProgressTimer',
            'pilomarimage': 'PilomarImage',
            'pilomarkeogram': 'PilomarKeogram',
            'textcolor': 'TextColor',
            'keyboardscanner': 'KeyboardScanner',
            'messagewindow': 'MessageWindow',
            'colordisplay': 'ColorDisplay',
            'bigletters': 'BigLetters',
            'cdsprite': 'CdSprite',
            'field': 'Field',
            'menu': 'Menu',
            'proceduremenu': 'ProcedureMenu',
            'optionmenu': 'OptionMenu',
            'listchooser': 'ListChooser',
            'filechooser': 'FileChooser',
            'hardware': 'Hardware',
            'parameters': 'Parameters',
            'quickstar': 'QuickStar',
            'folderhandler': 'FolderHandler',
            'microcontroller': 'Microcontroller',
            'motorcontrol': 'MotorControl',
            'sessionstatus': 'SessionStatus',
            'imagetracker': 'ImageTracker',
            'localstars': 'LocalStars',
            'target': 'Target',
            'sessionentry': 'SessionEntry',
            'sessionlist': 'SessionList',
            'inputpin_gpio': 'InputPinGpio',
            'outputpin_gpio': 'OutputPinGpio',
            'inputpin_gpiod': 'InputPinGpiod',
            'outputpin_gpiod': 'OutputPinGpiod',
            'data_set': 'DataSet',
            'data_point': 'DataPoint',
            'fd_object': 'FdObject',
            'fd_edge': 'FdEdge',
            'FixedPoint': 'FixedPoint',  # Already correct
        }

        # Method name patterns to convert (CamelCase -> snake_case)
        self.method_patterns = [
            (r'\.SetLogger\(', '.set_logger('),
            (r'\.SaveAttributes\(', '.save_attributes('),
            (r'\.SaveToDictionary\(', '.save_to_dictionary('),
            (r'\.NowUTC\(', '._now_utc('),
            (r'\.ShowConfig\(', '.show_config('),
            (r'\.Log\(', '.log('),
            (r'\.ReportException\(', '.report_exception('),
            (r'\.RaiseException\(', '.raise_exception('),
            (r'\.RecordTraceback\(', '.record_traceback('),
            (r'\.UniqueFilename\(', '.unique_filename('),
            (r'\.Increment\(', '.increment('),
            (r'\.UpdateCount\(', '.update_count('),
            (r'\.GetTotalSeconds\(', '.get_total_seconds('),
            (r'\.GetETA\(', '.get_eta('),
            (r'\.RemainingSeconds\(', '.remaining_seconds('),
            (r'\.SecondsToHMS\(', '.seconds_to_hms('),
            (r'\.GetPercent\(', '.get_percent('),
            (r'\.UnitsPerSecond\(', '.units_per_second('),
            (r'\.SecondsPerUnit\(', '.seconds_per_unit('),
            (r'\.MakeProgressBar\(', '.make_progress_bar('),
            (r'\.MakeStatusLine\(', '.make_status_line('),
            (r'\.IncrementAndDisplay\(', '.increment_and_display('),
            (r'\.IncrementAndGetStatus\(', '.increment_and_get_status('),
            (r'\.Elapsed\(', '.elapsed('),
            (r'\.ElapsedPc\(', '.elapsed_percent('),
            (r'\.Remaining\(', '.remaining('),
            (r'\.Due\(', '.due('),
            (r'\.Wait\(', '.wait('),
            (r'\.Restart\(', '.restart('),
            (r'\.Trigger\(', '.trigger('),
        ]

    def camel_to_snake(self, name: str) -> str:
        """Convert CamelCase to snake_case.
        
        Args:
            name: String in CamelCase
            
        Returns:
            String in snake_case
        """
        # Insert underscore before capital letters (except first)
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        # Insert underscore before caps preceded by lowercase or numbers
        s2 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1)
        return s2.lower()

    def refactor_class_definition(self, line: str) -> str:
        """Refactor a class definition line.
        
        Args:
            line: Line containing class definition
            
        Returns:
            Refactored line
        """
        # Match: class oldname(...):
        match = re.match(r'^(\s*class\s+)(\w+)(\s*\(.*\):.*)', line)
        if match:
            indent, old_name, rest = match.groups()
            new_name = self.class_mappings.get(old_name, old_name)
            return f"{indent}{new_name}{rest}"
        return line

    def refactor_attribute_names(self, line: str) -> str:
        """Refactor self.AttributeName to self.attribute_name.
        
        Args:
            line: Line of code
            
        Returns:
            Refactored line
        """
        # Find self.Something patterns
        def replace_attr(match):
            prefix = match.group(1)
            attr = match.group(2)
            # Don't convert if it's already snake_case or all uppercase
            if '_' in attr or attr.isupper():
                return prefix + attr
            # Convert CamelCase to snake_case
            return prefix + self.camel_to_snake(attr)
        
        line = re.sub(r'(self\.)([A-Z][a-zA-Z0-9]*)', replace_attr, line)
        return line

    def refactor_method_calls(self, line: str) -> str:
        """Refactor method calls to snake_case.
        
        Args:
            line: Line of code
            
        Returns:
            Refactored line
        """
        for old_pattern, new_pattern in self.method_patterns:
            line = re.sub(old_pattern, new_pattern, line)
        return line

    def refactor_file(self, input_path: str, output_path: str):
        """Refactor an entire file.
        
        Args:
            input_path: Path to input file
            output_path: Path to output file
        """
        print(f"Refactoring {input_path} -> {output_path}")
        
        with open(input_path, 'r') as f:
            lines = f.readlines()
        
        refactored_lines = []
        for line in lines:
            # Apply transformations
            line = self.refactor_class_definition(line)
            line = self.refactor_method_calls(line)
            line = self.refactor_attribute_names(line)
            refactored_lines.append(line)
        
        # Create output directory if needed
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w') as f:
            f.writelines(refactored_lines)
        
        print(f"  ✓ Created {output_path}")

    def generate_refactoring_report(self, src_dir: str):
        """Generate a report of what needs to be refactored.
        
        Args:
            src_dir: Source directory to analyze
        """
        print("\n=== Refactoring Analysis ===\n")
        
        for py_file in Path(src_dir).glob('*.py'):
            print(f"\nAnalyzing {py_file.name}:")
            
            with open(py_file, 'r') as f:
                content = f.read()
            
            # Find all class definitions
            classes = re.findall(r'class\s+(\w+)\s*\(', content)
            if classes:
                print(f"  Classes found: {', '.join(classes)}")
            
            # Find CamelCase attributes
            camel_attrs = set(re.findall(r'self\.([A-Z][a-zA-Z0-9]*)', content))
            if camel_attrs:
                print(f"  CamelCase attributes: {len(camel_attrs)}")
                for attr in sorted(camel_attrs)[:5]:  # Show first 5
                    print(f"    - {attr} -> {self.camel_to_snake(attr)}")


if __name__ == '__main__':
    refactorer = PilomarRefactorer()
    
    # Generate analysis report
    refactorer.generate_refactoring_report('src')
    
    print("\n" + "="*60)
    print("To refactor a specific file, use:")
    print("  refactorer.refactor_file('src/old.py', 'pilomar/new/module.py')")
    print("="*60)
