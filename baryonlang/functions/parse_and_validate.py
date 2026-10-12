# -------------------------- validate file bala and load dictionary (section) ------------------------------------------
from baryonlang.functions.colors import WHITE, BLUE, YELLOW, ORANGE, RED, GREEN, GRAY, PINK, BROWN, RESET
import re
import os

# -------------------- helper: split 'values=' respecting quoted substrings containing commas ------------------------
def split_quoted_values(raw):
    # matches 'quoted', "quoted", or unquoted tokens, separated by commas (handles values like ',' or '\t')
    tokens = re.findall(r"'[^']*'|\"[^\"]*\"|[^,]+", raw)
    return [t.strip().strip("'\"") for t in tokens]

def parse_and_validate(filepath):
    if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
        print(f"{RED}Error: File '{filepath}' not found or empty.{RESET}")
        return None
    sections = []
    current_section = None
    errors = []
    warnings = []
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
                if clean_key in ['name', 'flag', 'mount', 'copy', 'optional', 'quote']:
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
        for target_key in ['name', 'flag', 'flags', 'copy', 'optional', 'quote']:
            if target_key in content:
                content[target_key] = content[target_key].lower()
        for text_key in ['command', 'usage']:
            if text_key in content:
                content[text_key] = re.sub(r'<([^>]+)>', lambda m: f"<{m.group(1).lower()}>", content[text_key])
# -------------------- Migrate deprecated keywords: value= -> default=, flag=cp/nc -> copy= ----------------------------
    for s in sections:
        stype = s['type']
        content = s['content']
        line_num = s.get('line', '?')

        if stype == 'parameter' and 'value' in content:
            if 'default' in content:
                errors.append(f"Line {line_num}: cannot specify both 'value=' and 'default=' on the same [parameter] -- use 'default=' only.")
                content.pop('value')
            else:
                old_value = content.pop('value')
                content['default'] = old_value
                warnings.append(
                    f"Line {line_num}: 'value=' is deprecated for [parameter], automatically converted to 'default={old_value}'. "
                    f"Please update the .bala file to use 'default=' directly."
                )

        if stype == 'file' and content.get('flag', '') in ('cp', 'nc'):
            old_flag = content.pop('flag')
            if old_flag == 'cp':
                content['copy'] = 'yes'
                warnings.append(
                    f"Line {line_num}: 'flag=cp' is deprecated for [file], automatically converted to 'copy=yes'. "
                    f"Please update the .bala file directly."
                )
            elif old_flag == 'nc':
                content['copy'] = 'no'
                warnings.append(
                    f"Line {line_num}: 'flag=nc' is deprecated for [file], automatically converted to 'copy=no'. "
                    f"Please update the .bala file directly."
                )
# -------------------- Infer 'copy' default for [file] sections and warn on redundant flag=ro + copy=true --------------
    for s in sections:
        if s['type'] != 'file':
            continue
        content = s['content']
        line_num = s.get('line', '?')
        if 'copy' not in content:
            content['copy'] = 'no' if content.get('flag', '') == 'ro' else 'yes'
        elif content.get('flag', '') == 'ro' and content['copy'] in ('true', 'yes'):
            warnings.append(
                f"Line {line_num}: 'flag=ro' together with 'copy={content['copy']}' is redundant "
                f"(the original file is already protected because a copy is used), but not an error."
            )
# -------------------- verify mandatory sections -----------------------------------------                
    section_types = [s['type'] for s in sections]
    if 'research' not in section_types: errors.append("Missing mandatory section: [research]")
    if 'run' not in section_types: errors.append("Missing mandatory section: [run]")
    for single_type in ('research', 'run'):
        if section_types.count(single_type) > 1:
            errors.append(f"Section [{single_type}] must appear only once (found {section_types.count(single_type)})")    
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
            'research': ['description', 'name'],
            'run': ['command', 'script', 'image', 'usage'],
            'file': ['name', 'flag', 'description', 'optional', 'copy', 'quote'],
            'directory': ['name', 'description', 'flag', 'mount', 'copy', 'optional', 'quote'],
            'parameter': ['name', 'values', 'default', 'description', 'optional', 'quote']  
        }
        for actual_key in content.keys():
            if actual_key not in allowed_keys_by_section[stype]:
                errors.append(f"Line {line_num}: unexpected keyword '{actual_key}' inside [{stype}] section")
        if stype == 'parameter' and 'values' in content:
            cleaned_values = content['values'].strip().strip("'\"")
            if not cleaned_values:
                content.pop('values')
                warnings.append(
                    f"Line {line_num}: 'values=' in [parameter] is empty, automatically removed. "
                    f"Please specify at least one value or remove 'values=' from the .bala file."
                )
        if stype in ('file', 'directory', 'parameter') and 'quote' in content:
            quote_value = content['quote']
            if quote_value not in ['true', 'false', 'yes', 'no']:
                errors.append(f"Line {line_num}: invalid value '{content['quote']}' for 'quote' keyword (allowed: true, false, yes, no)")                
        if stype in ('file', 'directory', 'parameter'):
            if 'name' not in content or not content['name'].strip():
                errors.append(f"Line {line_num}: missing mandatory 'name' keyword in [{stype}] section")
        if stype == 'directory':
            if 'flag' not in content:
                errors.append(f"Line {line_num}: missing mandatory 'flag' keyword in [directory] section")
            elif content['flag'] not in ['ro', 'in', 'out', 'io']:
                errors.append(f"Line {line_num}: invalid flag '{content['flag']}' for [directory] section (allowed: ro, in, out, io)")
        if stype == 'file' and 'flag' in content and content['flag'] != 'ro':
            errors.append(f"Line {line_num}: invalid flag '{content['flag']}' for [file] section (allowed: ro)")
        if stype in ('file', 'directory') and 'copy' in content:
            copy_value = content['copy']
            if copy_value not in ['true', 'false', 'yes', 'no']:
                errors.append(f"Line {line_num}: invalid value '{content['copy']}' for 'copy' keyword (allowed: true, false, yes, no)")
            elif stype == 'directory' and content.get('flag', '') == 'out' and copy_value in ('true', 'yes'):
                errors.append(f"Line {line_num}: 'copy' cannot be used on a directory with flag 'out'")
        if stype in ('directory', 'file', 'parameter') and 'optional' in content:
            optional_value = content['optional']
            if optional_value not in ['true', 'false', 'yes', 'no']:
                errors.append(f"Line {line_num}: invalid value '{content['optional']}' for 'optional' keyword (allowed: true, false, yes, no)" )
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
                if content.get('copy', '') in ['true', 'yes']:
                    errors.append(f"Directory '{content.get('name')}' cannot use 'copy' (it is generated, not passed in).")    
                if content.get('optional', '') in ['true', 'yes']:
                    errors.append(f"Directory '{content.get('name')}' cannot be optional (it is mandatory).")
        if stype == 'parameter' and 'default' in content and 'values' in content:
            allowed_vals = split_quoted_values(content['values'])
            default_clean = content['default'].strip().strip("'\"")
            if default_clean not in allowed_vals:
                errors.append(f"Line {line_num}: default 'default={content['default']}' is not among the allowed 'values' ({content['values']})")
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
    if warnings:
        for w in warnings: print(f"{YELLOW}Warning: {w}{RESET}")
    if errors:
        for err in errors: print(f"{RED}Error: {err}{RESET}")
        return None
    print(f"{WHITE}Bala file is formally correct{RESET}")
    return sections