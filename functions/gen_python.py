import re

def parse_values(raw_values):
    """Parse comma-separated values respecting single/double quoted tokens."""
    tokens = []
    for match in re.finditer(r"'[^']*'|\"[^\"]*\"|[^,]+", raw_values):
        token = match.group(0).strip()
        if token:
            tokens.append(token.strip("'\""))
    return tokens

def gen_python(sections):
    for item in sections:
        if isinstance(item, dict) and 'content' in item:
            content = item['content']
            if isinstance(content, dict) and 'description' in content:
                desc = content['description']
                if isinstance(desc, str):
                    content['description'] = desc.replace("'", "\\'").replace('"', '\\"')
    res_sec   = next((s['content'] for s in sections if s['type'] == 'research'), {})
    run_sec   = next((s['content'] for s in sections if s['type'] == 'run'), {})
    exec_name = res_sec.get('name', 'baryon_tool').lower().replace(" ", "_")
    # -------------------------------------------------------------------------
    # Collect directories
    # -------------------------------------------------------------------------
    directories = {}   # name -> {mount, flag, description}
    for item in sections:
        if item['type'] == 'directory':
            c    = item['content']
            name = c.get('name', '')
            directories[name] = {
                'mount':       c.get('mount', f'/{name}').strip(),
                'flag':        c.get('flag', 'io').strip().lower(),
                'description': c.get('description', name),
            }
    has_workdir = 'workdir' in directories
    has_outdir  = 'outdir'  in directories
    # -------------------------------------------------------------------------
    # Collect files
    # -------------------------------------------------------------------------
    files = []
    for item in sections:
        if item['type'] == 'file':
            c = item['content']
            files.append({
                'name':        c.get('name', 'input_file'),
                'flag':        c.get('flag', 'cp').strip().lower(),
                'description': c.get('description', ''),
            })
    # -------------------------------------------------------------------------
    # Collect parameters and their allowed values
    # -------------------------------------------------------------------------
    parameters = []
    for item in sections:
        if item['type'] == 'parameter':
            c          = item['content']
            raw_values = c.get('values', '')
            parameters.append({
                'name':        c.get('name', 'param'),
                'description': c.get('description', ''),
                'values':      parse_values(raw_values),
            })
    # -------------------------------------------------------------------------
    # Build docker command template
    # -------------------------------------------------------------------------
    bala_cmd    = run_sec.get('command', 'docker run --rm').strip()
    bala_img    = run_sec.get('image', '').strip()
    bala_script = run_sec.get('script', '').strip()
    bala_usage  = run_sec.get('usage', '').strip()
    full_template = f"{bala_cmd} {bala_img} {bala_script} {bala_usage}"
    dynamic_items = []
    for item in sections:
        if item['type'] in ('directory', 'file', 'parameter') and 'name' in item['content']:
            dynamic_items.append(item)
    TYPE_COLORS = {
        'directory': '\\033[93m',   # yellow
        'file':      '\\033[38;5;208m',  # orange
        'parameter': '\\033[92m',   # green
    }
    DEFAULT_COLOR = '\\033[97m'
    # -------------------------------------------------------------------------
    # Start building the generated script lines
    # -------------------------------------------------------------------------
    L = []  # lines
    def w(*lines):
        for line in lines:
            L.append(line)
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
    # --- Build usage string ---
    usage_parts = []
    for item in dynamic_items:
        name  = item['content']['name']
        color = TYPE_COLORS.get(item['type'], DEFAULT_COLOR)
        usage_parts.append(f"f'{color}<{name}>{{RESET}}'")
    w(f"    usage_str = ' '.join([{', '.join(usage_parts)}])")
    w("")
    # --- Expected argument count ---
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
        flag  = item['content'].get('flag', '')
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
    # -------------------------------------------------------------------------
    # Validation block
    # -------------------------------------------------------------------------
    w("    # --- Input validation ---")
    w("    errors = []")
    w("")
    for item in dynamic_items:
        if item['type'] != 'directory':
            continue
        name = item['content']['name']
        w(
            f"    if not os.path.isdir(args['{name}']):",
            f"        errors.append(f'Directory not found: {name} = {{args[\"{name}\"]}}\"')",
        )
    for item in dynamic_items:
        if item['type'] != 'file':
            continue
        name = item['content']['name']
        w(
            f"    if not os.path.isfile(args['{name}']):",
            f"        errors.append(f'File not found: {name} = {{args[\"{name}\"]}}\"')",
        )
    for p in parameters:
        if not p['values']:
            continue
        allowed_repr = repr(p['values'])
        name         = p['name']
        w(
            f"    if args['{name}'] not in {allowed_repr}:",
            f'        errors.append(f"""Invalid value for {name}: {{args["{name}"]}}. Allowed: {p["values"]}""")'
        )
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
        conds.append("os.path.exists(os.path.join(os.path.abspath(args['outdir']), f'scratch{n}'))")
        
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
            "    scratch_out_path = os.path.join(os.path.abspath(args['outdir']), f'scratch{n}')",
            "    os.makedirs(scratch_out_path, exist_ok=True)",
        )
    w("")
    # -------------------------------------------------------------------------
    # Docker volume mounts construction
    # -------------------------------------------------------------------------
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
            f"    _host_out_base = os.path.abspath(args['outdir'])",
            f"    mounts.append(f'-v \"{{_host_out_base}}:{odir_mount}\"')", 
            f"    docker_vals['outdir'] = f'{odir_mount}/scratch{{n}}'",     
            "",
        )
    for name, d in directories.items():
        if name in ('workdir', 'outdir'):
            continue
        mount = d['mount']
        flag  = d['flag']
        if flag == 'ro':
            w(
                f"    # {name}: read-only directory",
                f"    mounts.append(f'-v \"{{os.path.abspath(args[\"{name}\"])}}:{mount}:ro\"')",
                f"    docker_vals['{name}'] = '{mount}'",
                "",
            )
        else:
            w(
                f"    # {name}: read-write directory [{flag}]",
                f"    mounts.append(f'-v \"{{os.path.abspath(args[\"{name}\"])}}:{mount}\"')",
                f"    docker_vals['{name}'] = '{mount}'",
                "",
            )
    w(
        "    # --- Bind files and service volumes ---",
        "    mounted_folders = {}", 
    )

    for f in files:
        name = f['name']
        flag = f['flag']
        
        if flag == 'cp' or flag not in ('ro', 'nc'):
            wdir_mount = directories.get('workdir', {}).get('mount', '/workdir')
            w(
                f"    _src_{name} = os.path.abspath(args['{name}'])",
                f"    shutil.copy(_src_{name}, scratch_path)",
                f"    docker_vals['{name}'] = f'{wdir_mount}/{{os.path.basename(_src_{name})}}'",
                "",
            )
            
        elif flag in ('ro', 'nc'):
            w(
                f"    _src_{name} = os.path.abspath(args['{name}'])",
                f"    _dir_{name} = os.path.dirname(_src_{name})",
                f"    if _dir_{name} not in mounted_folders:",
                f"        _m_point = f'/service{{service_idx}}'",
                f"        mounted_folders[_dir_{name}] = _m_point",
                f"        mounts.append(f'-v \"{{_dir_{name}}}:{{_m_point}}:ro\"')",
                f"        service_idx += 1",
                f"    docker_vals['{name}'] = f'{{mounted_folders[_dir_{name}]}}/{{os.path.basename(_src_{name})}}'",
                "",
            )
    for p in parameters:
        name = p['name']
        w(f"    docker_vals['{name}'] = args['{name}']")
    w("")

    # -------------------------------------------------------------------------
    # Assemble and run docker command
    # -------------------------------------------------------------------------
    w(
        "    # --- Assemble docker command ---",
        f"    cmd = {repr(full_template)}",
        "    mount_str = ' '.join(mounts)",
        '    cmd = cmd.replace("docker run", f"docker run {mount_str}", 1)',
        "    def replace_placeholder(match):",
        "        key = match.group(1)",
        "        return str(docker_vals.get(key, match.group(0)))",
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
        "",
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
    # -------------------------------------------------------------------------
    # Write output file
    # -------------------------------------------------------------------------
    output_filename = f"{exec_name}.py"
    with open(output_filename, "w", encoding="utf-8") as out_f:
        out_f.write("\n".join(L))
    print(f"\033[92mPython script '{output_filename}' generated successfully.\033[0m")