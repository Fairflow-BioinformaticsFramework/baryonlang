import re
import os

def parse_values(raw_values):
    """Parse comma-separated values respecting single/double quoted tokens."""
    tokens = []
    for match in re.finditer(r"'[^']*'|\"[^\"]*\"|[^,]+", raw_values):
        token = match.group(0).strip()
        if token:
            tokens.append(token.strip("'\""))
    return tokens

def gen_python(sections, script_name, as_function=False):
    for item in sections:
        if isinstance(item, dict) and 'content' in item:
            content = item['content']
            if isinstance(content, dict) and 'description' in content:
                desc = content['description']
                if isinstance(desc, str):
                    content['description'] = desc.replace("'", "\\'").replace('"', '\\"')
    res_sec   = next((s['content'] for s in sections if s['type'] == 'research'), {})
    run_sec   = next((s['content'] for s in sections if s['type'] == 'run'), {})
    raw_name  = script_name or res_sec.get('name', 'baryon_tool')
    exec_name = raw_name.lower().replace(" ", "_")
    # -------------------------- Collect directories ---------------------
    directories = {}   
    for item in sections:
        if item['type'] == 'directory':
            c    = item['content']
            name = c.get('name', '')
            directories[name] = {
                'mount':       c.get('mount', f'/{name}').strip(),
                'flag':        c.get('flag', 'io').strip().lower(),
                'description': c.get('description', name),
                'copy':        c.get('copy', 'false').strip().lower(),
                'optional':    c.get('optional', 'false').strip().lower() in ('true', 'yes'),
                'quote':       c.get('quote', 'false').strip().lower() in ('true', 'yes'),
            }
    has_workdir = 'workdir' in directories
    has_outdir  = 'outdir'  in directories

    # ------------------------- Collect files ----------------------
    files = []
    for item in sections:
        if item['type'] == 'file':
            c        = item['content']
            file_flag = c.get('flag', '').strip().lower()
            copy_raw  = c.get('copy')
            copy_default = 'no' if (copy_raw is None and file_flag == 'ro') else 'yes'
            files.append({
                'name':        c.get('name', 'input_file'),
                'flag':        file_flag,
                'copy':        (copy_raw if copy_raw is not None else copy_default).strip().lower() in ('true', 'yes'),
                'description': c.get('description', ''),
                'optional':    c.get('optional', 'false').strip().lower() in ('true', 'yes'),
                'quote':       c.get('quote', 'false').strip().lower() in ('true', 'yes'),
            })
    # ------------------- Collect parameters and their allowed values --------------------
    parameters = []
    for item in sections:
        if item['type'] == 'parameter':
            c          = item['content']
            raw_values = c.get('values', '')
            parameters.append({
                'name':        c.get('name', 'param'),
                'description': c.get('description', ''),
                'values':      parse_values(raw_values),
                'value':       c.get('default', '').strip().strip("'\""),
                'optional':    c.get('optional', 'false').strip().lower() in ('true', 'yes'),
                'quote':       c.get('quote', 'false').strip().lower() in ('true', 'yes'),
            })
    # ------------------- names for which the resolved value must be wrapped in double quotes in the generated command line, regardless of its content ------------------- #
    QUOTE_NAMES = (
        {n for n, d in directories.items() if d['quote']}
        | {f['name'] for f in files if f['quote']}
        | {p['name'] for p in parameters if p['quote']}
    )            
    # ------------------- Build docker command template -------------------
    bala_cmd    = run_sec.get('command', 'docker run --rm').strip()
    bala_img    = run_sec.get('image', '').strip()
    bala_script = run_sec.get('script', '').strip()
    bala_usage  = run_sec.get('usage', '').strip()
    full_template = f" {bala_img} {bala_script} {bala_usage}"
    dynamic_items = []
    for item in sections:
        if item['type'] in ('directory', 'file', 'parameter') and 'name' in item['content']:
            dynamic_items.append(item)
    TYPE_COLORS = {
        'directory': '\\033[93m',   
        'file':      '\\033[38;5;208m',  
        'parameter': '\\033[92m',   
    }
    DEFAULT_COLOR = '\\033[97m'
    # --------------------------- Start building the generated script lines -----------------
    L = []  
    def w(*lines):
        for line in lines:
            L.append(line)
    if as_function:
        func_args = ", ".join(f"{item['content']['name']}=None" for item in dynamic_items)
        w(
            "import os, sys, shutil, subprocess, re",
            "",
            "# ANSI color codes",
            "RED    = '\\033[91m'",
            "WHITE  = '\\033[97m'",
            "YELLOW = '\\033[93m'",
            "ORANGE = '\\033[38;5;208m'",
            "GREEN  = '\\033[92m'",
            "RESET  = '\\033[0m'",
            "",
            "",
            f"def {exec_name}({func_args}):",
            "    if os.name == 'nt':",
            "        os.system('color')",
            "",
        )
    else:
        w(
            "import os, sys, shutil, subprocess, re",
            "",
            "# ANSI color codes",
            "RED    = '\\033[91m'",
            "WHITE  = '\\033[97m'",
            "YELLOW = '\\033[93m'",
            "ORANGE = '\\033[38;5;208m'",
            "GREEN  = '\\033[92m'",
            "RESET  = '\\033[0m'",
            "",
            "",
            "def main():",
            "    if os.name == 'nt':",
            "        os.system('color')",
            "",
        )
    # -------------------------- Build usage string ----------------------
    usage_parts = []
    for item in dynamic_items:
        name  = item['content']['name']
        color = TYPE_COLORS.get(item['type'], DEFAULT_COLOR)
        usage_parts.append(f"f'{color}<{name}>{{RESET}}'")

    if not as_function:
        w(f"    usage_str = ' '.join([{', '.join(usage_parts)}])")
        w("")
        n_args = len(dynamic_items)
        research_desc = res_sec.get('description', '')
        w(
            f"    if len(sys.argv) != {n_args + 1}:",
            f"        print(f'{{WHITE}}Usage: python {exec_name}.py {{usage_str}}{{RESET}}\\n')",
        )
        if research_desc:
            w(f"        print(f'{{YELLOW}}{research_desc}{{RESET}}\\n')")
        w("        print(f'{WHITE}Arguments:{RESET}')")
        for item in dynamic_items:
            name  = item['content']['name']
            color = TYPE_COLORS.get(item['type'], DEFAULT_COLOR)
            desc  = item['content'].get('description', '')
            if item['type'] == 'file':
                copy_val = item['content'].get('copy', 'yes')
                flag_str = f" [copy={copy_val}]"
            else:
                flag = item['content'].get('flag', '')
                flag_str = f" [{flag}]" if flag else ""
            w(f"        print(f'{color}{name.ljust(15)}{{RESET}}{flag_str.ljust(6)} {desc}')")
        w(
            "        sys.exit(1)",
            "",
            "    # Parse positional arguments",
            "    args = {}",
        )
        for idx, item in enumerate(dynamic_items):
            name = item['content']['name']
            w(f"    args['{name}'] = sys.argv[{idx + 1}]")
        w("")
    else:
        func_params = [item['content']['name'] for item in dynamic_items]
        w("    args = {}")
        for item in dynamic_items:
            name = item['content']['name']
            w(f"    args['{name}'] = {name}")
        w("")
        usage_parts_str = ' '.join(f'<{n}>' for n in func_params)
        w(
            f"    if any(v is None for v in [{', '.join(func_params)}]):",
            f"        print(f'{{WHITE}}Usage: {exec_name}({usage_parts_str}){{RESET}}\\n')",
        )
        research_desc = res_sec.get('description', '')
        if research_desc:
            w(f"        print(f'{{YELLOW}}{research_desc}{{RESET}}\\n')")
        w("        print(f'{WHITE}Arguments:{RESET}')")
        for item in dynamic_items:
            name  = item['content']['name']
            color = TYPE_COLORS.get(item['type'], DEFAULT_COLOR)
            desc  = item['content'].get('description', '')
            if item['type'] == 'file':
                copy_val = item['content'].get('copy', 'yes')
                flag_str = f" [copy={copy_val}]"
            else:
                flag = item['content'].get('flag', '')
                flag_str = f" [{flag}]" if flag else ""
            w(f"        print(f'{color}{name.ljust(15)}{{RESET}}{flag_str.ljust(6)} {desc}')")
        w(
            "        raise ValueError('Missing required arguments')",
            "",
        )
    w("    # --- Resolve 'default' keyword using each parameter's configured value= ---")
    for p in parameters:
        if p['value']:
            name = p['name']
            w(
                f"    if args['{name}'] == 'default':",
                f"        args['{name}'] = {p['value']!r}",
            )
    w("")
    # --------------------------------  Validation block --------------------------
    w("    # --- Input validation ---")
    w("    errors = []")
    w("")
    for item in dynamic_items:
        if item['type'] != 'directory':
            continue
        name     = item['content']['name']
        optional = item['content'].get('optional', 'false').lower() in ('true', 'yes')
        if optional:
            w(
                f"    if args['{name}'] != 'dummy' and not os.path.isdir(args['{name}']):",
                f"        errors.append(f'Directory not found: {name} = {{args[\"{name}\"]}}')",
            )
        else:
            w(
                f"    if not os.path.isdir(args['{name}']):",
                f"        errors.append(f'Directory not found: {name} = {{args[\"{name}\"]}}')",
            )
    for item in dynamic_items:
        if item['type'] != 'file':
            continue
        name     = item['content']['name']
        optional = item['content'].get('optional', 'false').lower() in ('true', 'yes')
        if optional:
            w(
                f"    if args['{name}'] != 'dummy' and not os.path.isfile(args['{name}']):",
                f"        errors.append(f'File not found: {name} = {{args[\"{name}\"]}}')",
            )
        else:
            w(
                f"    if not os.path.isfile(args['{name}']):",
                f"        errors.append(f'File not found: {name} = {{args[\"{name}\"]}}')",
            )
    for p in parameters:
        if not p['values']:
            continue
        name         = p['name']
        allowed_repr = repr(p['values'])
        if p['optional']:
            w(
                f"    if args['{name}'] != 'dummy' and args['{name}'] not in {allowed_repr}:",
                f'        errors.append(f"""Invalid value for {name}: {{args["{name}"]}}. Allowed: {p["values"]}""")'
            )
        else:
            w(
                f"    if args['{name}'] not in {allowed_repr}:",
                f'        errors.append(f"""Invalid value for {name}: {{args["{name}"]}}. Allowed: {p["values"]}""")'
            )
    if as_function:
        w(
            "",
            "    if errors:",
            "        for e in errors:",
            "            print(f'{RED}ERROR:{RESET} {WHITE}{e}{RESET}')",
            "        raise ValueError('Input validation failed')",
            "",
        )
    else:
        w(
            "",
            "    if errors:",
            "        for e in errors:",
            "            print(f'{RED}ERROR:{RESET} {WHITE}{e}{RESET}')",
            "        sys.exit(1)",
            "",
        )
    w(
        "    # --- Scratch directory setup ---",
        "    n = 1",
        "    while True:",
    )
    conds = ["os.path.exists(os.path.join(os.path.abspath(args['workdir']), f'scratch{n}'))"]
    if has_outdir:
        conds.append("os.path.exists(os.path.join(os.path.abspath(args['outdir']), f'output{n}'))")
    w(f"        if {' or '.join(conds)}:")
    w("            n += 1")
    w("        else:")
    w("            break")
    w("")
    
    w(
        "    scratch_path = os.path.join(os.path.abspath(args['workdir']), f'scratch{n}')",
        "    os.makedirs(scratch_path, exist_ok=True)",
    )
    if has_outdir:
        w(
            "    scratch_out_path = os.path.join(os.path.abspath(args['outdir']), f'output{n}')",
            "    os.makedirs(scratch_out_path, exist_ok=True)",
        )
    w("")
    # --------------------- Docker volume mounts construction ---------------------------
    w("    # --- Build docker volume mounts ---")
    w("    mounts = []")
    w("    docker_vals = {}   # placeholder -> docker-internal path")
    w("    service_idx = 1    # counter for read-only service mounts")
    w("")
    if has_workdir:
        wdir_mount = directories['workdir']['mount']
        w(
            f"    mounts.append(f'-v \"{{scratch_path}}:{wdir_mount}\"')",
            f"    docker_vals['workdir'] = '{wdir_mount}'",
            "",
        )
    if has_outdir:
        odir_mount = directories['outdir']['mount']
        w(
            f"    mounts.append(f'-v \"{{scratch_out_path}}:{odir_mount}\"')",
            f"    docker_vals['outdir'] = '{odir_mount}'",     
            "",
        )
    for name, d in directories.items():
        if name in ('workdir', 'outdir'):
            continue
        mount     = d['mount']
        flag      = d['flag']
        copy_dir  = d.get('copy', 'false') in ('true', 'yes')
        optional  = d.get('optional', False)
        ro_suffix = ':ro' if flag == 'ro' else ''
        label     = 'read-only directory' if flag == 'ro' else f'read-write directory [{flag}]'
        indent    = '        ' if optional else '    '

        if copy_dir:
            body = [
                f"{indent}# {name}: copy into workdir, then mount the copy ({label})",
                f'{indent}_copy_src_{name} = os.path.abspath(args["{name}"])',
                f'{indent}_copy_dst_{name} = os.path.join(scratch_path, os.path.basename(_copy_src_{name}))',
                f"{indent}shutil.copytree(_copy_src_{name}, _copy_dst_{name}, dirs_exist_ok=True)",
                f"{indent}mounts.append(f'-v \"{{_copy_dst_{name}}}:{mount}{ro_suffix}\"')",
                f"{indent}docker_vals['{name}'] = '{mount}'",
            ]
        else:
            body = [
                f"{indent}# {name}: {label}",
                f"{indent}mounts.append(f'-v \"{{os.path.abspath(args[\"{name}\"])}}:{mount}{ro_suffix}\"')",
                f"{indent}docker_vals['{name}'] = '{mount}'",
            ]

        if optional:
            w(f"    # {name} is optional: mount only if a real path is passed, use 'dummy' placeholder otherwise")
            w(f"    if args['{name}'] != 'dummy':")
            w(*body)
            w("    else:")
            w(f"        docker_vals['{name}'] = 'dummy'")
        else:
            w(*body)
        w("")
    w(
        "    # --- Bind files and service volumes ---",
        "    mounted_folders = {}", 
    )
    for f in files:
        name      = f['name']
        copy_file = f['copy']
        optional  = f['optional']
        ro_suffix = ':ro' if f.get('flag', '') == 'ro' else ''        
        indent    = '        ' if optional else '    '
        if copy_file:
            wdir_mount = directories.get('workdir', {}).get('mount', '/workdir')
            body = [
                f"{indent}_src_{name} = os.path.abspath(args['{name}'])",
                f"{indent}shutil.copy(_src_{name}, scratch_path)",
                f"{indent}docker_vals['{name}'] = f'{wdir_mount}/{{os.path.basename(_src_{name})}}'",
            ]
        else: 
            body = [
                f"{indent}_src_{name} = os.path.abspath(args['{name}'])",
                f"{indent}_dir_{name} = os.path.dirname(_src_{name})",
                f"{indent}if _dir_{name} not in mounted_folders:",
                f"{indent}    _m_point = f'/service{{service_idx}}'",
                f"{indent}    mounted_folders[_dir_{name}] = _m_point",
                f"{indent}    mounts.append(f'-v \"{{_dir_{name}}}:{{_m_point}}{ro_suffix}\"')",
                f"{indent}    service_idx += 1",
                f"{indent}docker_vals['{name}'] = f'{{mounted_folders[_dir_{name}]}}/{{os.path.basename(_src_{name})}}'",
            ]
        if optional:
            w(f"    if args['{name}'] != 'dummy':")
            w(*body)
            w("    else:")
            w(f"        docker_vals['{name}'] = 'dummy'")
        else:
            w(*body)
        w("")
    for p in parameters:
        name = p['name']
        w(f"    docker_vals['{name}'] = args['{name}']")
    w("")
    # --------------------------------- Assemble and run docker command -----------------------------
    w(
        "    # --- Assemble docker command ---",
        f"    cmd = {repr(full_template)}",
        "    mount_str = ' '.join(mounts)")
    if bala_cmd.split()[0].lower() == 'singularity':     
       w( "    mount_str = mount_str.replace('-v \"', '--bind ').replace('\"', '')")

    param_names = [p['name'] for p in parameters]
    w(
        f"    cmd = ' '.join(['{bala_cmd}', mount_str, {repr(full_template)}])",
        f"    PARAM_NAMES = {param_names!r}",
        f"    QUOTE_NAMES = {sorted(QUOTE_NAMES)!r}",
        "    def replace_placeholder(match):",
        "        key = match.group(1)",
        "        val = str(docker_vals.get(key, match.group(0)))",
        "        if key in QUOTE_NAMES and val != 'dummy':",
        "            escaped_val = val.replace('\"', '\\\\\"')",
        "            return f'\"{escaped_val}\"'",
        "        if key in PARAM_NAMES:",
        "            if re.search(r'[;&|()<>$`\"\\'\\s]', val):",
        "                escaped_val = val.replace('\"', '\\\\\"')",
        "                return f'\"{escaped_val}\"'",
        "        return val",
        "",
        "    cmd = re.sub(r'<([^>]+)>', replace_placeholder, cmd)",
        "",
        "    print(f'\\n{YELLOW}Running:{RESET}\\n{WHITE}{cmd}{RESET}\\n')",
        "",
    )
    w(
        "    log_path = os.path.join(scratch_path, 'output_log.txt')",
        "    print(f'{YELLOW}Log:{RESET} {WHITE}{log_path}{RESET}\\n')",
        "    with open(log_path, 'w', encoding='utf-8') as log_f:",
        "        p = subprocess.Popen(",
        "            cmd, shell=True,",
        "            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,",
        "            text=True",
        "        )",
        "        for line in p.stdout:",
        "            sys.stdout.write(line)",
        "            log_f.write(line)",
        "        p.wait()",
        ""
    )
    if as_function:
        w(
            "    if p.returncode == 0:",
            "        print(f'\\n{GREEN}Done. Log saved to: {log_path}{RESET}')",
            "    else:",
            "        print(f'\\n{RED}Docker exited with code {p.returncode}. See log: {log_path}{RESET}')",
            "    return p.returncode",
        )
    else:
        w(
            "    if p.returncode == 0:",
            "        print(f'\\n{GREEN}Done. Log saved to: {log_path}{RESET}')",
            "    else:",
            "        print(f'\\n{RED}Docker exited with code {p.returncode}. See log: {log_path}{RESET}')",
            "    sys.exit(p.returncode)",
            "",
            "",
            "if __name__ == '__main__':",
            "    main()",
        )
    # -------------------- Write output file ----------------
    output_filename = f"{exec_name}.py"
    with open(output_filename, "w", encoding="utf-8") as out_f:
        out_f.write("\n".join(L))
    print(f"\033[92mPython script '{output_filename}' generated successfully.\033[0m")
    # ------------------ Sample launch command file -------------------
    arg_placeholders = []       
    kwarg_placeholders = []     
    for item in dynamic_items:
        name = item['content']['name']
        if item['type'] == 'parameter':
            param = next((pm for pm in parameters if pm['name'] == name), None)
            default_val = param['value'] if param else ''
            value = default_val if default_val else f"<{name}>"
        elif item['type'] == 'directory':
            value = f"/path/to/directory/{name}"
        else:  # file
            value = f"/path/to/file/{name}"
        arg_placeholders.append(f'"{value}"' if name in QUOTE_NAMES else value)
        kwarg_placeholders.append(f'{name}="{value}"')

    if as_function:
        args_str = ', '.join(kwarg_placeholders)
        sample_cmd = f"from {exec_name} import {exec_name}\n{exec_name}({args_str})"
    else:
        args_str = ' '.join(arg_placeholders)
        sample_cmd = f"python {exec_name}.py {args_str}"
    command_file = f"{exec_name}_command.txt"
    marker = "# ------- python sample command ------- #"
    file_existed = os.path.exists(command_file)
    if file_existed:
        with open(command_file, "r") as f:
            lines = f.readlines()
        marker_index = -1
        for i, line in enumerate(lines):
            if marker in line:
                marker_index = i
                break
        if marker_index != -1:
            del lines[marker_index : marker_index + 4]
            new_lines = lines[:marker_index]
            remaining_lines = lines[marker_index:]
        else:
            new_lines = lines
            remaining_lines = []
    else:
        new_lines = []
        remaining_lines = []
    new_block = [
        f"{marker}\n",
        "\n",
        f"{sample_cmd.strip()}\n",
        "\n",
    ]
    final_lines = new_lines + new_block + remaining_lines
    with open(command_file, "w") as f:
        f.writelines(final_lines)
    action = "updated" if file_existed else "generated"
    print(f"\033[92mSample command file '{command_file}' successfully {action}.\033[0m")