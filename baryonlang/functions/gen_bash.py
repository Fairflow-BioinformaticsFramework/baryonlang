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

def gen_bash(sections, script_name, as_function=False):
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

    # -------------------------------------------------------------------------
    # Collect directories
    # -------------------------------------------------------------------------
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

    # -------------------------------------------------------------------------
    # Collect files
    # -------------------------------------------------------------------------
    files = []
    for item in sections:
        if item['type'] == 'file':
            c = item['content']
            files.append({
                'name':        c.get('name', 'input_file'),
                'copy':        c.get('copy', 'yes').strip().lower() in ('true', 'yes'),
                'description': c.get('description', ''),
                'optional':    c.get('optional', 'false').strip().lower() in ('true', 'yes'),
                'quote':       c.get('quote', 'false').strip().lower() in ('true', 'yes'),
                'flag':        c.get('flag', '').strip().lower(),
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
                'value':       c.get('default', '').strip().strip("'\""),
                'optional':    c.get('optional', 'false').strip().lower() in ('true', 'yes'),
                'quote':       c.get('quote', 'false').strip().lower() in ('true', 'yes'),
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

    # -------------------------------------------------------------------------
    # Header — shebang and color codes
    # -------------------------------------------------------------------------
    if not as_function:
        w(
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            "",
        )

    w(
        "# ANSI color codes",
        "RED='\\033[91m'",
        "WHITE='\\033[97m'",
        "YELLOW='\\033[93m'",
        "ORANGE='\\033[38;5;208m'",
        "GREEN='\\033[92m'",
        "RESET='\\033[0m'",
        "",
    )

    # -------------------------------------------------------------------------
    # Build usage string parts (needed in both modes)
    # -------------------------------------------------------------------------
    usage_parts = []
    for item in dynamic_items:
        name  = item['content']['name']
        color = TYPE_COLORS.get(item['type'], DEFAULT_COLOR)
        usage_parts.append(f'"${{{color}}}<{name}>${{RESET}}"')

    usage_str_expr = ' '.join(usage_parts)
    research_desc  = res_sec.get('description', '')
    func_params    = [item['content']['name'] for item in dynamic_items]
    n_args         = len(dynamic_items)

    # -------------------------------------------------------------------------
    # Script mode: positional $1..$N with arg count check
    # Function mode: function with named parameters
    # -------------------------------------------------------------------------
    if not as_function:
        w(f'USAGE_STR=$(echo -e {usage_str_expr})')
        w("")
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
            if item['type'] == 'file':
                copy_val  = item['content'].get('copy', 'yes')
                file_flag = item['content'].get('flag', '')
                flag_str  = f" [copy={copy_val}{', ro' if file_flag == 'ro' else ''}]"
            else:
                flag = item['content'].get('flag', '')
                flag_str = f" [{flag}]" if flag else ""
            w(f'    echo -e "${{{color}}}{name.ljust(15)}${{RESET}}{flag_str.ljust(6)} {desc}"')
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
    else:
        usage_parts_str = ' '.join(f'<{n}>' for n in func_params)
        params_sig      = ' '.join(func_params)
        w(f"{exec_name}() {{")
        w(f'    # Parameters: {params_sig}')
        w("")
        # Assign named locals from positional args inside the function
        for idx, item in enumerate(dynamic_items):
            name = item['content']['name']
            w(f'    local {name}="${{{idx + 1}:-}}"')
        w("")
        # NULL check — any empty parameter triggers usage
        checks = ' || '.join(f'[ -z "${{{n}}}" ]' for n in func_params)
        w(f'    if {checks}; then')
        w(f'        USAGE_STR=$(echo -e {usage_str_expr})')
        w(f'        echo -e "${{WHITE}}Usage: {exec_name} ${{USAGE_STR}}${{RESET}}\\n"')
        if research_desc:
            w(f'        echo -e "${{YELLOW}}{research_desc}${{RESET}}\\n"')
        w('        echo -e "${WHITE}Arguments:${RESET}"')
        for item in dynamic_items:
            name  = item['content']['name']
            color = TYPE_COLORS.get(item['type'], DEFAULT_COLOR)
            desc  = item['content'].get('description', '')
            if item['type'] == 'file':
                copy_val  = item['content'].get('copy', 'yes')
                file_flag = item['content'].get('flag', '')
                flag_str  = f" [copy={copy_val}{', ro' if file_flag == 'ro' else ''}]"
            else:
                flag = item['content'].get('flag', '')
                flag_str = f" [{flag}]" if flag else ""
            w(f'        echo -e "${{{color}}}{name.ljust(15)}${{RESET}}{flag_str.ljust(6)} {desc}"')
        w(
            "        return 1",
            "    fi",
            "",
        )

    # Indentation prefix for function body
    p = "    " if as_function else ""

    w(f"{p}# --- Resolve 'default' keyword using each parameter's configured value= ---")
    for param in parameters:
        if param['value']:
            name = param['name']
            w(
                f'{p}if [ "${{{name}}}" = "default" ]; then',
                f'{p}    {name}="{param["value"]}"',
                f"{p}fi",
            )
    w("")

    # -------------------------------------------------------------------------
    # Validation block
    # -------------------------------------------------------------------------
    w(f"{p}# --- Input validation ---")
    w(f"{p}errors=()")
    w("")

    for item in dynamic_items:
        if item['type'] != 'directory':
            continue
        name     = item['content']['name']
        optional = item['content'].get('optional', 'false').lower() in ('true', 'yes')
        if optional:
            w(
                f'{p}if [ "${{{name}}}" != "dummy" ] && [ ! -d "${{{name}}}" ]; then',
                f'{p}    errors+=("Directory not found: {name} = ${{{name}}}")',
                f"{p}fi",
            )
        else:
            w(
                f'{p}if [ ! -d "${{{name}}}" ]; then',
                f'{p}    errors+=("Directory not found: {name} = ${{{name}}}")',
                f"{p}fi",
            )
    for item in dynamic_items:
        if item['type'] != 'file':
            continue
        name     = item['content']['name']
        optional = item['content'].get('optional', 'false').lower() in ('true', 'yes')
        if optional:
            w(
                f'{p}if [ "${{{name}}}" != "dummy" ] && [ ! -f "${{{name}}}" ]; then',
                f'{p}    errors+=("File not found: {name} = ${{{name}}}")',
                f"{p}fi",
            )
        else:
            w(
                f'{p}if [ ! -f "${{{name}}}" ]; then',
                f'{p}    errors+=("File not found: {name} = ${{{name}}}")',
                f"{p}fi",
            )

    for param in parameters:
        if not param['values']:
            continue
        name            = param['name']
        allowed         = '|'.join(re.escape(v) for v in param['values'])
        allowed_display = str(param['values'])
        if param['optional']:
            w(
                f'{p}if [ "${{{name}}}" != "dummy" ] && ! echo "${{{name}}}" | grep -qE "^({allowed})$"; then',
                f'{p}    errors+=("Invalid value for {name}: ${{{name}}}. Allowed: {allowed_display}")',
                f"{p}fi",
            )
        else:
            w(
                f'{p}if ! echo "${{{name}}}" | grep -qE "^({allowed})$"; then',
                f'{p}    errors+=("Invalid value for {name}: ${{{name}}}. Allowed: {allowed_display}")',
                f"{p}fi",
            )
    if as_function:
        w(
            "",
            f'{p}if [ "${{#errors[@]}}" -gt 0 ]; then',
            f"{p}    for e in \"${{errors[@]}}\"; do",
            f'{p}        echo -e "${{RED}}ERROR:${{RESET}} ${{WHITE}}${{e}}${{RESET}}"',
            f"{p}    done",
            f"{p}    return 1",
            f"{p}fi",
            "",
        )
    else:
        w(
            "",
            f'{p}if [ "${{#errors[@]}}" -gt 0 ]; then',
            f"{p}    for e in \"${{errors[@]}}\"; do",
            f'{p}        echo -e "${{RED}}ERROR:${{RESET}} ${{WHITE}}${{e}}${{RESET}}"',
            f"{p}    done",
            f"{p}    exit 1",
            f"{p}fi",
            "",
        )

    # -------------------------------------------------------------------------
    # Scratch directory setup
    # -------------------------------------------------------------------------
    w(
        f"{p}# --- Scratch directory setup ---",
        f"{p}n=1",
        f"{p}while true; do",
    )

    conds = [f'[ -d "$(realpath "${{workdir}}")/scratch${{n}}" ]']
    if has_outdir:
        conds.append(f'[ -d "$(realpath "${{outdir}}")/output${{n}}" ]')

    cond_str = ' || '.join(conds)
    w(
        f'{p}    if {cond_str}; then',
        f"{p}        n=$((n + 1))",
        f"{p}    else",
        f"{p}        break",
        f"{p}    fi",
        f"{p}done",
        "",
    )

    if has_workdir:
        w(
            f'{p}scratch_path="$(realpath "${{workdir}}")/scratch${{n}}"',
            f'{p}mkdir -p "${{scratch_path}}"',
        )
    if has_outdir:
        w(
            f'{p}scratch_out_path="$(realpath "${{outdir}}")/output${{n}}"',
            f'{p}mkdir -p "${{scratch_out_path}}"',
        )
    w("")

    # -------------------------------------------------------------------------
    # Docker volume mounts construction
    # -------------------------------------------------------------------------
    w(
        f"{p}# --- Build docker volume mounts ---",
        f"{p}mounts=()",
        f"{p}declare -A docker_vals",
        f"{p}service_idx=1",
        "",
    )

    if has_workdir:
        wdir_mount = directories['workdir']['mount']
        w(
            f'{p}mounts+=("-v \\"${{scratch_path}}:{wdir_mount}\\"")',
            f'{p}docker_vals["workdir"]="{wdir_mount}"',
            "",
        )

    if has_outdir:
        odir_mount = directories['outdir']['mount']
        w(
            f'{p}mounts+=("-v \\"${{scratch_out_path}}:{odir_mount}\\"")',
            f'{p}docker_vals["outdir"]="{odir_mount}"',
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
        indent    = f"{p}    " if optional else p

        if copy_dir:
            body = [
                f"{indent}# {name}: copy into workdir, then mount the copy ({label})",
                f'{indent}_copy_src_{name}="$(realpath "${{{name}}}")"',
                f'{indent}_copy_dst_{name}="${{scratch_path}}/$(basename "${{_copy_src_{name}}}")"',
                f'{indent}cp -r "${{_copy_src_{name}}}" "${{_copy_dst_{name}}}"',
                f'{indent}mounts+=("-v \\"${{_copy_dst_{name}}}:{mount}{ro_suffix}\\"")',
                f'{indent}docker_vals["{name}"]="{mount}"',
            ]
        else:
            body = [
                f"{indent}# {name}: {label}",
                f'{indent}mounts+=("-v \\"$(realpath "${{{name}}}"):{mount}{ro_suffix}\\"")',
                f'{indent}docker_vals["{name}"]="{mount}"',
            ]

        if optional:
            w(f"{p}# {name} is optional: mount only if a real path is passed, use 'dummy' placeholder otherwise")
            w(f'{p}if [ "${{{name}}}" != "dummy" ]; then')
            w(*body)
            w(f"{p}else")
            w(f'{p}    docker_vals["{name}"]="dummy"')
            w(f"{p}fi")
        else:
            w(*body)
        w("")
    w(
        f"{p}# --- Bind files and service volumes ---",
        f"{p}declare -A mounted_folders",
    )
    for f in files:
        name      = f['name']
        copy_file = f['copy']
        optional  = f['optional']
        flag      = f.get('flag', '')
        ro_suffix = ':ro' if flag == 'ro' else ''
        indent    = f"{p}    " if optional else p
        if copy_file:
            wdir_mount = directories.get('workdir', {}).get('mount', '/workdir')
            body = [
                f'{indent}_src_{name}="$(realpath "${{{name}}}")"',
                f'{indent}cp "${{_src_{name}}}" "${{scratch_path}}/"',
                f'{indent}docker_vals["{name}"]="{wdir_mount}/$(basename "${{_src_{name}}}")"',
            ]
        else:  
            body = [
                f'{indent}_src_{name}="$(realpath "${{{name}}}")"',
                f'{indent}_dir_{name}="$(dirname "${{_src_{name}}}")"',
                f'{indent}if [ -z "${{mounted_folders[${{_dir_{name}}}]+x}}" ]; then',
                f'{indent}    _m_point="/service${{service_idx}}"',
                f'{indent}    mounted_folders["${{_dir_{name}}}"]="${{_m_point}}"',
                f'{indent}    mounts+=("-v \\"${{_dir_{name}}}:${{_m_point}}{ro_suffix}\\"")',
                f'{indent}    service_idx=$((service_idx + 1))',
                f"{indent}fi",
                f'{indent}docker_vals["{name}"]="${{mounted_folders[${{_dir_{name}}}]}}/$(basename "${{_src_{name}}}")"',
            ]
        if optional:
            w(f'{p}if [ "${{{name}}}" != "dummy" ]; then')
            w(*body)
            w(f"{p}else")
            w(f'{p}    docker_vals["{name}"]="dummy"')
            w(f"{p}fi")
        else:
            w(*body)
        w("")
    for param in parameters:
        name = param['name']
        w(f'{p}docker_vals["{name}"]="${{{name}}}"')
    w("")

    # -------------------------------------------------------------------------
    # Assemble and run docker command
    # -------------------------------------------------------------------------
    full_template = f"{bala_img} {bala_script} {bala_usage}"
    w(f'{p}mount_str="${{mounts[*]}}"')
    if bala_cmd.split()[0].lower() == 'singularity':
        w(
            f'{p}mount_str="${{mount_str//-v \\"/ --bind }}"',
            f'{p}mount_str="${{mount_str//\\"}}"',
        )
    quote_names = [n for n, d in directories.items() if d.get('quote', False)]
    quote_names += [f['name'] for f in files if f.get('quote', False)]
    quote_names += [p['name'] for p in parameters if p.get('quote', False)]
    quote_names_str = ' '.join(f'"{n}"' for n in quote_names)
    param_names = [p['name'] for p in parameters]
    param_names_str = ' '.join(f'"{n}"' for n in param_names)

    _special_class = "[;&|()<>$`\"'[:space:]]"
    _special_class_escaped = _special_class.replace("'", "'\"'\"'")

    w(
        f'{p}PARAM_NAMES=({param_names_str})',
        f'{p}QUOTE_KEYS=({quote_names_str})',
        f"{p}special_chars_re='{_special_class_escaped}'",
        f'{p}cmd="{bala_cmd} ${{mount_str}} {full_template}"',
        f'{p}for key in "${{!docker_vals[@]}}"; do',
        f'{p}    val="${{docker_vals[${{key}}]}}"',
        f'{p}    is_param=0',
        f'{p}    for p_name in "${{PARAM_NAMES[@]}}"; do',
        f'{p}        if [ "${{key}}" = "${{p_name}}" ]; then is_param=1; break; fi',
        f'{p}    done',
        f'{p}    force_quote=0',
        f'{p}    for q_name in "${{QUOTE_KEYS[@]}}"; do',
        f'{p}        if [ "${{key}}" = "${{q_name}}" ]; then force_quote=1; break; fi',
        f'{p}    done',
        f'{p}    if [ "${{force_quote}}" -eq 1 ] || ( [ "${{is_param}}" -eq 1 ] && [[ "${{val}}" =~ ${{special_chars_re}} ]] ); then',
        f'{p}        escaped_val=$(echo "${{val}}" | sed \'s/"/\\\\"/g\')',
        f'{p}        cmd="${{cmd//<${{key}}>/\\"${{escaped_val}}\\"}}"',
        f'{p}    else',
        f'{p}        cmd="${{cmd//<${{key}}>/${{val}}}}"',
        f'{p}    fi',
        f'{p}done',
        f'{p}echo -e "\\n${{YELLOW}}Running:${{RESET}}\\n${{WHITE}}${{cmd}}${{RESET}}\\n"',
    )

    w(
        f'{p}log_path="${{scratch_path}}/output_log.txt"',
        f'{p}echo -e "${{YELLOW}}Log:${{RESET}} ${{WHITE}}${{log_path}}${{RESET}}\\n"',
        "",
        f'{p}eval "${{cmd}}" 2>&1 | tee "${{log_path}}"',
        f"{p}exit_code=${{PIPESTATUS[0]}}",
        "",
    )

    if as_function:
        w(
            f'{p}if [ "${{exit_code}}" -eq 0 ]; then',
            f'{p}    echo -e "\\n${{GREEN}}Done. Log saved to: ${{log_path}}${{RESET}}"',
            f"{p}else",
            f'{p}    echo -e "\\n${{RED}}Docker exited with code ${{exit_code}}. See log: ${{log_path}}${{RESET}}"',
            f"{p}fi",
            f"{p}return ${{exit_code}}",
            "}",   # chiude la funzione
        )
    else:
        w(
            f'{p}if [ "${{exit_code}}" -eq 0 ]; then',
            f'{p}    echo -e "\\n${{GREEN}}Done. Log saved to: ${{log_path}}${{RESET}}"',
            f"{p}else",
            f'{p}    echo -e "\\n${{RED}}Docker exited with code ${{exit_code}}. See log: ${{log_path}}${{RESET}}"',
            f"{p}fi",
            "exit ${exit_code}",
        )

    # -------------------------------------------------------------------------
    # Write output file
    # -------------------------------------------------------------------------
    output_filename = f"{exec_name}.sh"
    with open(output_filename, "w", encoding="utf-8") as out_f:
        out_f.write("\n".join(L))
    print(f"\033[92mBash script '{output_filename}' generated successfully.\033[0m")
    # -------------------------------------------------------------------------
    # Sample launch command file
    # -------------------------------------------------------------------------
    arg_placeholders = []
    for item in dynamic_items:
        name = item['content']['name']
        if item['type'] == 'parameter':
            param = next((pm for pm in parameters if pm['name'] == name), None)
            default_val = param['value'] if param else ''
            if default_val:
                value = default_val
            else:
                value = f"<{name}>"
        elif item['type'] == 'directory':
            value = f"/path/to/directory/{name}"
        else:  # file
            value = f"/path/to/file/{name}"
        if name in quote_names:
            value = f'"{value}"'
        arg_placeholders.append(value)

    args_str = ' '.join(arg_placeholders)
    if as_function:
        sample_cmd = f"source {exec_name}.sh && {exec_name} {args_str}"
    else:
        sample_cmd = f"bash {exec_name}.sh {args_str}"
    command_file = f"{exec_name}_command.txt"
    marker = "# ------- bash sample command ------- #"
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