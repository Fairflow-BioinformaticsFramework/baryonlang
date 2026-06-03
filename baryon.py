# ----------------------------------------------------------------------------------------------------------------------
# Date      : 2026-05-22
# Project   : https://github.com/Fairflow-BioinformaticsFramework
# Authors   : 
# Version   : 1.0
# ----------------------------------------------------------------------------------------------------------------------

from functions.gen_nextflow import gen_nextflow
from functions.gen_streamflow import gen_streamflow
from functions.gen_galaxy import gen_galaxy
from functions.gen_python import gen_python
from functions.gen_erre import gen_erre
from functions.gen_bash import gen_bash

import os
import sys
import re

WHITE = '\033[97m'
BLUE = '\033[94m'
YELLOW = '\033[93m'
ORANGE = '\033[38;5;208m'
RED = '\033[91m'
GREEN = '\033[92m'
GRAY = '\033[90m'
PINK = '\033[95m'
BROWN = '\033[33m'
RESET = '\033[0m'

# ----------------------------------------------------------------------------------------------------------------------
# -------------------------- get color for section ---------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------
def get_color_for_section(section_type):
    stype = section_type.lower()
    if stype == 'research': return PINK 
    if stype == 'file': return ORANGE
    if stype == 'run': return PINK
    if stype == 'directory': return ORANGE
    if stype == 'parameter': return BROWN
    return GRAY
# ----------------------------------------------------------------------------------------------------------------------
# -------------------------- validate file bala and load dictionary (section) ------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------
def parse_and_validate(filepath):
    if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
        print(f"{RED}Error: File '{filepath}' not found or empty.{RESET}")
        return None
    sections = []
    current_section = None
    errors = []
    filename_only = os.path.basename(filepath)
    print(f"{GRAY}Verification of file '{filename_only}' in progress...{RESET}")
    with open(filepath, 'r') as f:
        for line_num, line in enumerate(f, 1):
            original = line.strip()
            if not original or original.startswith('#'): continue
            work_line = line.strip()
            section_match = re.match(r'^\[(\w+)\]$', work_line.lower())
            if section_match:
                stype = section_match.group(1).lower()
                current_section = {'type': stype, 'content': {}, 'line': line_num}
                sections.append(current_section)
                work_line = work_line.replace(section_match.group(0), "", 1)
            elif current_section is not None and '=' in work_line:
                key, raw_value = work_line.split('=', 1)
                clean_key = key.strip().lower()
                if clean_key in ['name', 'flag', 'mount']:
                    value_parts = raw_value.strip().split()
                    clean_value = value_parts[0] if value_parts else ""
                else:
                    clean_value = raw_value.strip()
                current_section['content'][clean_key] = clean_value
                work_line = work_line.replace(key, "", 1)
                work_line = work_line.replace("=", "", 1)
                work_line = work_line.replace(clean_value, "", 1)            
            residual = work_line.strip()
            if residual:
                errors.append(f"Line {line_num}: '{original}' -> Ignored characters: '{residual}'")
# -------------------- Normalize specific values (name, flag, placeholders) to lowercase before validation
    for s in sections:
        content = s['content']
        for target_key in ['name', 'flag', 'flags']:
            if target_key in content:
                content[target_key] = content[target_key].lower()
        for text_key in ['command', 'usage']:
            if text_key in content:
                content[text_key] = re.sub(r'<([^>]+)>', lambda m: f"<{m.group(1).lower()}>", content[text_key])
# -------------------- verify mandatory sections -----------------------------------------                
    section_types = [s['type'] for s in sections]
    if 'research' not in section_types: errors.append("Missing mandatory section: [research]")
    if 'run' not in section_types: errors.append("Missing mandatory section: [run]")
    dir_names = [s['content'].get('name', '') for s in sections if s['type'] == 'directory']
    if 'workdir' not in dir_names: errors.append("Mandatory directory 'workDir' missing.")
# -------------------- Validation loop for sections (File, Directory, Flags, Names, Mounts)
    for s in sections:
        stype = s['type']
        content = s['content']
        line_num = s.get('line', '?')
        allowed_sections = ['research', 'run', 'file', 'directory', 'parameter']
        if stype not in allowed_sections:
            errors.append(f"Line {line_num}: unknown section type '[{stype}]'")
            continue  
        allowed_keys_by_section = {
            'research': ['description', 'name', 'script'],
            'run': ['command', 'script', 'image', 'usage'],
            'file': ['name', 'flag', 'description'],
            'directory': ['name', 'description', 'flag', 'mount'],
            'parameter': ['name', 'values', 'value', 'description']  
        }
        for actual_key in content.keys():
            if actual_key not in allowed_keys_by_section[stype]:
                errors.append(f"Line {line_num}: unexpected keyword '{actual_key}' inside [{stype}] section")
        if stype in ['file', 'directory']:
            if 'flag' not in content:
                errors.append(f"Line {line_num}: missing mandatory 'flag' keyword in [{stype}] section")
            else:
                flag_value = content['flag']
                if stype == 'file':
                    if flag_value not in ['cp', 'nc', 'ro']:
                        errors.append(f"Line {line_num}: invalid flag '{content['flag']}' for [file] section (allowed: cp, nc, ro)")
                elif stype == 'directory':
                    if flag_value not in ['ro', 'in', 'out', 'io']:
                        errors.append(f"Line {line_num}: invalid flag '{content['flag']}' for [directory] section (allowed: ro, in, out, io)")
        if stype == 'directory':
            if 'mount' not in content:
                errors.append(f"Line {line_num}: missing mandatory 'mount' keyword in [directory] section")
        if 'name' in content:
            name_value = content['name']
            if not re.match(r'^\w+$', name_value):
                errors.append(f"Line {line_num}: invalid name '{name_value}' (must contain only letters, numbers, and underscores)")                
        if stype == 'directory':
            dirname = content.get('name', '')
            if dirname in ['workdir', 'outdir']:
                if content.get('flag', '') == 'ro':
                    errors.append(f"Directory '{content.get('name')}' cannot be readonly.")
# ------------ Collect all tags from BOTH 'command' and 'usage' and verify presence
    run_sec = next((s['content'] for s in sections if s['type'] == 'run'), {})
    for key in ['command', 'script', 'image']:
        if key not in run_sec:
            errors.append(f"Section [run] is missing mandatory keyword: {key}")
    combined_text = run_sec.get('command', '') + " " + run_sec.get('usage', '')
    required_names = re.findall(r'<(.*?)>', combined_text)
    seen_names = {}   
    seen_mounts = {}  
    for s in sections:
        content = s['content']
        line_num = s.get('line', '?')
        if 'name' in content:
            name_val = content['name']
            if name_val in seen_names:
                seen_names[name_val].append(line_num)
            else:
                seen_names[name_val] = [line_num]
        if 'mount' in content:
            mount_val = content['mount']
            if mount_val in seen_mounts:
                seen_mounts[mount_val].append(line_num)
            else:
                seen_mounts[mount_val] = [line_num]
    for name_val, lines in seen_names.items():
        if len(lines) > 1:
            lines_str = ", ".join(map(str, lines))
            errors.append(f"Duplicate name '{name_val}' found across multiple lines: {lines_str}")
    for mount_val, lines in seen_mounts.items():
        if len(lines) > 1:
            lines_str = ", ".join(map(str, lines))
            errors.append(f"Duplicate mount path '{mount_val}' found across multiple lines: {lines_str}")
    defined_names_map = {s['content'].get('name', ''): s['content'].get('name') 
                         for s in sections if 'name' in s['content']}
    for req in required_names:
        if req not in defined_names_map:
            errors.append(f"Parameter <{req}> required but not defined in any section (name={req})")
    if errors:
        for err in errors: print(f"{RED}Error: {err}{RESET}")
        return None
    print(f"{WHITE}Bala file is formally correct{RESET}")
    return sections
# -------------------------- display summary sections ------------------------------------------------------------------
def display_summary(sections):
    print(f"\n{GRAY}--- FILE CONTENT SUMMARY ---{RESET}")
    for sec in sections:
        color = get_color_for_section(sec['type']) 
        display_values = []
        content = sec['content']
        for key, val in content.items():
            display_values.append(val) 
        if display_values:
            print(f"{color}{', '.join(display_values)}{RESET}") 
    print(f"{GRAY}----------------------------{RESET}\n")
# -------------------------- M A I N -----------------------------------------------------------------------------------
def main():
    filename = ""
    overwrite_mode = False
    args_list = sys.argv[1:]
    if "--overwrite" in args_list or "-o" in args_list:
        overwrite_mode = True
        args_list = [a for a in args_list if a not in ("--overwrite", "-o")]
    if len(args_list) > 0:
        filename = args_list[0]
        if not filename.lower().endswith('.bala'):
            filename += '.bala'
        if not os.path.exists(filename):
            print(f"\n{RED}Error: The specified file '{filename}' does not exist.{RESET}\n")
            sys.exit(1)
    else:
        bala_files = [f for f in os.listdir('.') if f.lower().endswith('.bala')]
        if not bala_files:
            filename = input(f"{WHITE}Enter .bala file path/name: {RESET}").strip()
            if not filename.lower().endswith('.bala'):
                filename += '.bala'
            if not os.path.exists(filename):
                print(f"\n{RED}Error: The specified file '{filename}' does not exist.{RESET}\n")
                sys.exit(1)
        else:
            print(f"\n{YELLOW}Available .bala files:{RESET}")
            for i, f in enumerate(bala_files, 1):
                print(f"  [{i}] {f}")
            print()
            prompt = f"{WHITE}Enter .bala file path/name or enter the corresponding number: {RESET}"
            user_input = input(prompt).strip()
            if user_input.isdigit():
                choice = int(user_input)
                if 1 <= choice <= len(bala_files):
                    filename = bala_files[choice - 1]
                else:
                    print(f"{RED}Error: Invalid selection number.{RESET}")
                    return
            else:
                filename = user_input
                if not filename.lower().endswith('.bala'):
                    filename += '.bala'
    if not filename: 
        return
    sections = parse_and_validate(filename)
    if sections:
        display_summary(sections)
        research_sec = next((s['content'] for s in sections if s['type'] == 'research'), {})
        tool_id = research_sec.get('name', 'baryon_tool').lower().replace(" ", "_")
        all_possible_files = [
            f"{tool_id}.nf", "nextflow.config", f"{tool_id}_nextflow.txt", f"{tool_id}.cwl", f"{tool_id}-params.yml", f"{tool_id}.yml",  f"{tool_id}_targz.xml", f"{tool_id}.xml", f"{tool_id}.py", f"{tool_id}.R", f"{tool_id}.sh"
        ]
        existing_files = [f for f in all_possible_files if os.path.exists(f)]
        if existing_files:
            if overwrite_mode:
                print(f"\n{GREEN}[Overwrite Mode] Deleting existing target files automatically...{RESET}")
                for f in existing_files:
                    try:
                        os.remove(f)
                    except OSError as e:
                        print(f"{RED}Error deleting {f}: {e}{RESET}")
            else:
                print(f"\n{YELLOW}Warning: The following target file(s) already exist:{RESET}")
                for f in existing_files:
                    print(f"  - {f}")
                prompt = f"\n{WHITE}Do you want to delete them and regenerate? (yes/no): {RESET}"
                user_response = input(prompt).strip().lower()
                if user_response in ['yes', 'y']:
                    print(f"{GREEN}Deleting existing files and proceeding with generation...{RESET}")
                    for f in existing_files:
                        try:
                            os.remove(f)
                        except OSError as e:
                            print(f"{RED}Error deleting {f}: {e}{RESET}")
                else:
                    print(f"{ORANGE}Operation cancelled by user. Exiting without changes.{RESET}")
                    sys.exit(0)
        script_value = research_sec.get('script', 'all').lower()
        if 'nextflow' in script_value or 'all' in script_value:
            gen_nextflow(sections)
        if 'streamflow' in script_value or 'all' in script_value:
            gen_streamflow(sections)
        if 'streamflow' in script_value or 'all' in script_value:
            gen_galaxy(sections)
        if 'python' in script_value or 'all' in script_value:
            gen_python(sections)            
        if 'r' in script_value or 'all' in script_value:
            gen_erre(sections)            
        if 'bash' in script_value or 'all' in script_value:
            gen_bash(sections)            


if __name__ == "__main__":
    if os.name == 'nt': os.system('color')
    main()