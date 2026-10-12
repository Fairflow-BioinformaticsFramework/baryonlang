import re
import os

def gen_nextflow(sections, script_name):
    run_sec    = next((s['content'] for s in sections if s['type'] == 'run'), {})
    res_sec    = next((s['content'] for s in sections if s['type'] == 'research'), {})
    if run_sec.get('command', 'docker run --rm').strip().split()[0].lower() == 'singularity':
        print("\033[93mNextflow tool generation skipped: Singularity runtime is not supported.\033[0m")
        return
    config_content = "docker.enabled = true\ndocker.runOptions = ''"
    with open("nextflow.config", "w") as f:
        f.write(config_content)
    raw_name  = script_name or res_sec.get('name', 'baryon_tool')
    tool_id = raw_name.lower().replace(" ", "_")
    image      = run_sec.get('image', '').strip()
    script     = run_sec.get('script', '').strip()
    directories = [s['content'] for s in sections if s['type'] == 'directory']
    workdir_param = next(d['name'] for d in directories if d['name'].lower() == 'workdir')    
    files       = [s['content'] for s in sections if s['type'] == 'file']
    parameters  = [s['content'] for s in sections if s['type'] == 'parameter']
    file_names = {f['name'] for f in files}
    def optional_prefix(item):
        is_optional = item.get('optional', 'false').strip().lower() in ('true', 'yes')
        return "optional, " if is_optional else ""
    def is_quoted(item):
        return item.get('quote', 'false').strip().lower() in ('true', 'yes')
    quote_flags = {}
    for f in files:
        quote_flags[f['name']] = is_quoted(f)
    for d in directories:
        quote_flags[d['name']] = is_quoted(d)
    for p in parameters:
        quote_flags[p['name']] = is_quoted(p)
    wdmount = next((s['content'].get('mount', s['content'].get('name')) for s in sections if s['type'] == 'directory' and s['content'].get('name', '').lower() == 'workdir'), "/workdir")
    path_overrides = {}
    for f in files:
        fname = f['name']
        flag = f.get('flag', '').strip().lower()
        default_copy = 'no' if flag == 'ro' else 'yes'
        copy_val = f.get('copy', default_copy).strip().lower()
        if copy_val in ('true', 'yes'):
            path_overrides[fname] = fr"{wdmount}/scratch\$n/${{{fname}.name}}"
    for d in directories:
        dname = d['name']
        if dname.lower() in ('workdir', 'outdir'):
            continue
        copy_val = d.get('copy', 'false').strip().lower()
        if copy_val in ('true', 'yes'):
            path_overrides[dname] = fr"{wdmount}/scratch\$n/\${dname}_base"
    dir_mounts = {s['content']['name'].lower(): s['content'].get('mount', s['content'].get('name')) for s in sections if s['type'] == 'directory'}
    def replace_placeholder(match):
        var_name = match.group(1)
        var_name_lower = var_name.lower()

        if var_name in path_overrides:
            placeholder = path_overrides[var_name]
        elif var_name_lower in dir_mounts:
            actual_mount = dir_mounts[var_name_lower]
            if var_name_lower == 'workdir':
                placeholder = fr"{actual_mount}/scratch\$n"
            elif var_name_lower == 'outdir':
                placeholder = fr"{actual_mount}/output\$n"
            else:
                placeholder = actual_mount
        elif var_name in file_names:
            placeholder = f"${{{var_name}}}"
        else:
            placeholder = f"${{params.{var_name}}}"

        if quote_flags.get(var_name, False):
            return f"\"{placeholder}\""
        return placeholder
    usage = re.sub(r'<(.*?)>', replace_placeholder, run_sec.get('usage', '').strip())
    container_opts = f'"--user \\$(id -u):\\$(id -g) ' + " ".join(f"--volume ${{params.{d['name']}}}:{d.get('mount', d['name'])}{':ro' if d.get('flag') == 'ro' else ''}" for d in directories) + '"'
    nf_lines = ["nextflow.enable.dsl=2\n"]
    nf_lines.append("/*")
    nf_lines.append(f" * Pipeline: {res_sec.get('name', 'Unnamed')}")
    nf_lines.append(f" * Description: {res_sec.get('description', '')}")
    nf_lines.append(" */\n")

    nf_lines.append("// --- PARAMETERS ---")

    for d in directories:
        nf_lines.append(f"params.{d['name']} = \"/path/to/directory/{d['name']}\" // {optional_prefix(d)}{d.get('description', '')}")
    for f in files:
        nf_lines.append(f"params.{f['name']} = \"/path/to/file/{f['name']}\" // {optional_prefix(f)}{f.get('description', '')}")
    for p in parameters:
        list_values = ""
        if 'values' in p:
            list_values = (f" - Possible values: {p['values']}")
        main_val = ""
        if 'default' in p:
            main_val = str(p['default']).strip().strip("'\"")
        elif 'values' in p:
            matches = re.findall(r"['\"](.*?)['\"]|([^,]+)", p['values'])
            if matches:
                first_match = matches[0]
                raw_val = first_match[0] if first_match[0] else first_match[1]
                main_val = raw_val.strip().strip("'\"")
        nf_lines.append(f"params.{p['name']} = \"{main_val}\" // {optional_prefix(p)}{p.get('description', '')} {list_values}")
    nf_lines.append("")
    nf_lines.append(f"process {tool_id.upper()} {{")
    nf_lines.append(f"    container '{image}'")
    nf_lines.append(f"    containerOptions {container_opts}\n")
    nf_lines.append("") 
    if files:
        nf_lines.append("    input:")
        for f in files:
            nf_lines.append(f"    path {f['name']}")
        nf_lines.append("") 
    nf_lines.append("    output:")
    nf_lines.append("    env 'N'")
    nf_lines.append("")
    nf_lines.append("    script:")
    nf_lines.append("    \"\"\"")
    nf_lines.append("    n=1")
    nf_lines.append(fr"    while [ -d \"{wdmount}/scratch\$n\" ]; do")
    nf_lines.append(fr"        n=`expr \$n + 1`")
    nf_lines.append("    done")
    for s in sections:
        if s['type'] == 'directory':
            dname = s['content'].get('name', '').lower()
            dmount = s['content'].get('mount', s['content'].get('name'))
            if dname == 'workdir':
                nf_lines.append(fr"    mkdir -p \"{dmount}/scratch\$n\"")
            elif dname == 'outdir':
                nf_lines.append(fr"    mkdir -p \"{dmount}/output\$n\"")
            else:
                nf_lines.append(f"    mkdir -p \"{dmount}\"")
    for s in sections:
        if s['type'] == 'directory':
            content = s['content']
            dname = content.get('name', '')
            dmount = content.get('mount', dname)
            copy_val = content.get('copy', 'false').strip().lower()
            if copy_val in ('true', 'yes') and dname.lower() not in ['workdir', 'outdir']:
                nf_lines.append(f"    {dname}_src=\"${{params.{dname}}}\"")
                nf_lines.append(fr"    {dname}_base=\$(basename \"\${dname}_src\")")
                nf_lines.append(fr"    mkdir -p \"{wdmount}/scratch\$n/\${dname}_base\"")
                nf_lines.append(fr"    cp -r \"{dmount}/.\" \"{wdmount}/scratch\$n/\${dname}_base/\"")
    for f in files:
        fname = f['name']
        flag = f.get('flag', '').strip().lower()
        default_copy = 'no' if flag == 'ro' else 'yes'
        copy_val = f.get('copy', default_copy).strip().lower()
        if copy_val in ('true', 'yes'):
            nf_lines.append(fr"    cp \"${{{fname}}}\" \"{wdmount}/scratch\$n/${{{fname}.name}}\"")
    nf_lines.append(fr"    {script} {usage} > {wdmount}/scratch\$n/output_log.txt 2>&1")
    nf_lines.append(r"    export N=\$n")    
    nf_lines.append("    \"\"\"")
    nf_lines.append("}\n")
    nf_lines.append("workflow {")
    nf_lines.append("    def scratchN = null")
    nf_lines.append("")
    if files:
        for f in files:
            nf_lines.append(f"    {f['name']} = Channel.fromPath(params.{f['name']})")
        channel_args = ", ".join(f['name'] for f in files)
        nf_lines.append(f"    {tool_id.upper()}({channel_args})")
    else:
        nf_lines.append(f"    {tool_id.upper()}()")
    nf_lines.append(f"    {tool_id.upper()}.out.subscribe {{ scratchN = it }}")
    nf_lines.append("")
    nf_lines.append("    workflow.onComplete = {")
    nf_lines.append("        def src = new File(\"${workflow.launchDir}/.nextflow.log\")")
    nf_lines.append("        if (scratchN) {")
    nf_lines.append(f"            def dst = new File(\"${{params.{workdir_param}}}/scratch${{scratchN}}/nextflow.log\")")
    nf_lines.append("            if (src.exists()) dst.text = src.text")
    nf_lines.append("        }")
    nf_lines.append("    }")
    nf_lines.append("}")
    with open(f"{tool_id}.nf", "w") as f:
        f.write("\n".join(nf_lines))
    print(f"\033[92mNextflow Pipeline '{tool_id}.nf' successfully generated.\033[0m")
    # ------- launch command file ------- #
    workdir_mount = "$(pwd)"
    volume_flags = f"-v /var/run/docker.sock:/var/run/docker.sock -v {workdir_mount}:{workdir_mount}"
    #for d in directories:
    #    dir_placeholder = f"/path/to/directory/{d['name']}"
    #    volume_flags += f" -v {dir_placeholder}:{dir_placeholder}"
    volume_flags += f" -v /common/base/path:/common/base/path"
    run_cmd = (
        f"docker run -it --rm {volume_flags} -w {workdir_mount} "
        f"-e DOCKER_API_VERSION=1.44 nextflow/nextflow:26.04.6 nextflow run {tool_id}.nf"
    )
    command_file = f"{tool_id}_command.txt"
    marker = "# ------- nextflow sample command ------- #"
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
        f"{run_cmd.strip()}\n",
        "\n"
    ]
    final_lines = new_lines + new_block + remaining_lines
    with open(command_file, "w") as f:
        f.writelines(final_lines)
    action = "updated" if file_existed else "generated"
    print(f"\033[92mLaunch command file '{command_file}' successfully {action}.\033[0m")