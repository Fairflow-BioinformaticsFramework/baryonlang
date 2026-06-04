import re

def parse_values(raw_values):
    """Parse comma-separated values respecting single/double quoted tokens."""
    tokens = []
    for match in re.finditer(r"'[^']*'|\"[^\"]*\"|[^,]+", raw_values):
        token = match.group(0).strip()
        if token:
            tokens.append(token.strip("'\""))
    return tokens

def gen_bash(sections):
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

    dynamic_items = []
    for item in sections:
        if item['type'] in ('directory', 'file', 'parameter') and 'name' in item['content']:
            dynamic_items.append(item)

    TYPE_COLORS = {
        'directory': 'YELLOW',
        'file':      'ORANGE',
        'parameter': 'GREEN',
    }
    DEFAULT_COLOR = 'WHITE'

    # -------------------------------------------------------------------------
    # Start building the generated bash script lines
    # -------------------------------------------------------------------------
    L = []  # lines

    def w(*lines):
        for line in lines:
            L.append(line)

    w(
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        "# ANSI color codes",
        "RED='\\033[91m'",
        "WHITE='\\033[97m'",
        "YELLOW='\\033[93m'",
        "ORANGE='\\033[38;5;208m'",
        "GREEN='\\033[92m'",
        "RESET='\\033[0m'",
        "",
    )

    # --- Build usage string ---
    usage_parts = []
    for item in dynamic_items:
        name  = item['content']['name']
        color = TYPE_COLORS.get(item['type'], DEFAULT_COLOR)
        usage_parts.append(f'"${{{color}}}<{name}>${{RESET}}"')

    usage_str_expr = ' '.join(usage_parts)
    w(f'USAGE_STR=$(echo -e {usage_str_expr})')
    w("")

    # --- Expected argument count ---
    n_args = len(dynamic_items)
    research_desc = res_sec.get('description', '')

    w(
        f'if [ "$#" -ne {n_args} ]; then',
        f'    echo -e "${{WHITE}}Usage: bash {exec_name}.sh ${{USAGE_STR}}${{RESET}}\\n"',
    )
    if research_desc:
        w(f'    echo -e "${{YELLOW}}{research_desc}${{RESET}}\\n"')

    w('    echo -e "${WHITE}Arguments:${RESET}"')

    for item in dynamic_items:
        name  = item['content']['name']
        color = TYPE_COLORS.get(item['type'], DEFAULT_COLOR)
        desc  = item['content'].get('description', '')
        flag  = item['content'].get('flag', '')
        flag_str = f" [{flag}]" if flag else ""
        padded_name = name.ljust(15)
        padded_flag = flag_str.ljust(6)
        w(f'    echo -e "${{{color}}}{padded_name}${{RESET}}{padded_flag} {desc}"')

    w(
        "    exit 1",
        "fi",
        "",
        "# Parse positional arguments",
    )

    for idx, item in enumerate(dynamic_items):
        name = item['content']['name']
        w(f'{name}="${{{idx + 1}}}"')

    w("")

    # -------------------------------------------------------------------------
    # Validation block
    # -------------------------------------------------------------------------
    w("# --- Input validation ---")
    w("errors=()")
    w("")

    for item in dynamic_items:
        if item['type'] != 'directory':
            continue
        name = item['content']['name']
        w(
            f'if [ ! -d "${{{name}}}" ]; then',
            f'    errors+=("Directory not found: {name} = ${{{name}}}")',
            "fi",
        )

    for item in dynamic_items:
        if item['type'] != 'file':
            continue
        name = item['content']['name']
        w(
            f'if [ ! -f "${{{name}}}" ]; then',
            f'    errors+=("File not found: {name} = ${{{name}}}")',
            "fi",
        )

    for p in parameters:
        if not p['values']:
            continue
        name    = p['name']
        allowed = '|'.join(re.escape(v) for v in p['values'])
        allowed_display = str(p['values'])
        w(
            f'if ! echo "${{{name}}}" | grep -qE "^({allowed})$"; then',
            f'    errors+=("Invalid value for {name}: ${{{name}}}. Allowed: {allowed_display}")',
            "fi",
        )

    w(
        "",
        'if [ "${#errors[@]}" -gt 0 ]; then',
        "    for e in \"${errors[@]}\"; do",
        '        echo -e "${RED}ERROR:${RESET} ${WHITE}${e}${RESET}"',
        "    done",
        "    exit 1",
        "fi",
        "",
    )

    # -------------------------------------------------------------------------
    # Scratch directory setup
    # -------------------------------------------------------------------------
    w(
        "# --- Scratch directory setup ---",
        "n=1",
        "while true; do",
    )
    conds = [f'[ -d "$(realpath "${{{("workdir" if has_workdir else list(directories.keys())[0] if directories else "workdir")}}}")/scratch${{n}}" ]']
    if has_workdir:
        conds = [f'[ -d "$(realpath "${{workdir}}")/scratch${{n}}" ]']
        if has_outdir:
            conds.append(f'[ -d "$(realpath "${{outdir}}")/scratch${{n}}" ]')

    cond_str = ' || '.join(conds)
    w(
        f'    if {cond_str}; then',
        "        n=$((n + 1))",
        "    else",
        "        break",
        "    fi",
        "done",
        "",
    )

    if has_workdir:
        w(
            'scratch_path="$(realpath "${workdir}")/scratch${n}"',
            'mkdir -p "${scratch_path}"',
        )
    if has_outdir:
        w(
            'scratch_out_path="$(realpath "${outdir}")/scratch${n}"',
            'mkdir -p "${scratch_out_path}"',
        )
    w("")

    # -------------------------------------------------------------------------
    # Docker volume mounts construction
    # -------------------------------------------------------------------------
    w(
        "# --- Build docker volume mounts ---",
        "mounts=()",
        "declare -A docker_vals",
        "service_idx=1",
        "",
    )

    if has_workdir:
        wdir_mount = directories['workdir']['mount']
        w(
            f'mounts+=("-v \\"${{scratch_path}}:{wdir_mount}\\"")',
            f'docker_vals["workdir"]="{wdir_mount}"',
            "",
        )

    if has_outdir:
        odir_mount = directories['outdir']['mount']
        w(
            '_host_out_base="$(realpath "${outdir}")"',
            f'mounts+=("-v \\"${{_host_out_base}}:{odir_mount}\\"")',
            f'docker_vals["outdir"]="{odir_mount}/scratch${{n}}"',
            "",
        )

    for name, d in directories.items():
        if name in ('workdir', 'outdir'):
            continue
        mount = d['mount']
        flag  = d['flag']
        if flag == 'ro':
            w(
                f"# {name}: read-only directory",
                f'mounts+=("-v \\"$(realpath "${{{name}}}"):{mount}:ro\\"")',
                f'docker_vals["{name}"]="{mount}"',
                "",
            )
        else:
            w(
                f"# {name}: read-write directory [{flag}]",
                f'mounts+=("-v \\"$(realpath "${{{name}}}"):{mount}\\"")',
                f'docker_vals["{name}"]="{mount}"',
                "",
            )

    w(
        "# --- Bind files and service volumes ---",
        "declare -A mounted_folders",
    )

    for f in files:
        name = f['name']
        flag = f['flag']

        if flag == 'cp' or flag not in ('ro', 'nc'):
            wdir_mount = directories.get('workdir', {}).get('mount', '/workdir')
            w(
                f'_src_{name}="$(realpath "${{{name}}}")"',
                f'cp "${{_src_{name}}}" "${{scratch_path}}/"',
                f'docker_vals["{name}"]="{wdir_mount}/$(basename "${{_src_{name}}}")"',
                "",
            )
        elif flag in ('ro', 'nc'):
            w(
                f'_src_{name}="$(realpath "${{{name}}}")"',
                f'_dir_{name}="$(dirname "${{_src_{name}}}")"',
                f'if [ -z "${{mounted_folders[${{_dir_{name}}}]+x}}" ]; then',
                f'    _m_point="/service${{service_idx}}"',
                f'    mounted_folders["${{_dir_{name}}}"]="${{_m_point}}"',
                f'    mounts+=("-v \\"${{_dir_{name}}}:${{_m_point}}:ro\\"")',
                f'    service_idx=$((service_idx + 1))',
                f'fi',
                f'docker_vals["{name}"]="${{mounted_folders[${{_dir_{name}}}]}}/$(basename "${{_src_{name}}}")"',
                "",
            )

    for p in parameters:
        name = p['name']
        w(f'docker_vals["{name}"]="${{{name}}}"')
    w("")

    # -------------------------------------------------------------------------
    # Assemble and run docker command
    # -------------------------------------------------------------------------
    full_template = f"{bala_img} {bala_script} {bala_usage}"
    w('mount_str="${mounts[*]}"')
    if bala_cmd.split()[0].lower() == 'singularity':
        w(
            'mount_str="${mount_str//-v \\"/ --bind }"',
            'mount_str="${mount_str//\\"}"',
        )
    w(
        f'cmd="{bala_cmd} ${{mount_str}} {full_template}"',
        'for key in "${!docker_vals[@]}"; do',
        '    cmd="${cmd//<${key}>/${docker_vals[${key}]}}"',
        "done",
        'echo -e "\\n${YELLOW}Running:${RESET}\\n${WHITE}${cmd}${RESET}\\n"',
    )
    w(
        'log_path="${scratch_path}/output_log.txt"',
        'echo -e "${YELLOW}Log:${RESET} ${WHITE}${log_path}${RESET}\\n"',
        "",
        'eval "${cmd}" 2>&1 | tee "${log_path}"',
        "exit_code=${PIPESTATUS[0]}",
        "",
        'if [ "${exit_code}" -eq 0 ]; then',
        '    echo -e "\\n${GREEN}Done. Log saved to: ${log_path}${RESET}"',
        "else",
        '    echo -e "\\n${RED}Docker exited with code ${exit_code}. See log: ${log_path}${RESET}"',
        "fi",
        "exit ${exit_code}",
    )

    # -------------------------------------------------------------------------
    # Write output file
    # -------------------------------------------------------------------------
    output_filename = f"{exec_name}.sh"
    with open(output_filename, "w", encoding="utf-8") as out_f:
        out_f.write("\n".join(L))
    print(f"\033[92mBash script '{output_filename}' generated successfully.\033[0m")
