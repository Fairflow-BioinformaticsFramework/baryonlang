import re

def gen_nextflow(sections):
    config_content = "docker.enabled = true\ndocker.runOptions = ''"
    with open("nextflow.config", "w") as f:
        f.write(config_content)

    run_sec    = next((s['content'] for s in sections if s['type'] == 'run'), {})
    res_sec    = next((s['content'] for s in sections if s['type'] == 'research'), {})
    if run_sec.get('command', 'docker run --rm').strip().split()[0].lower() == 'singularity':
        print("\033[93mNextflow tool generation skipped: Singularity runtime is not supported.\033[0m")
        return
    tool_id    = res_sec.get('name', 'baryon_tool').lower().replace(" ", "_")
    image      = run_sec.get('image', '').strip()
    script     = run_sec.get('script', '').strip()
    directories = [s['content'] for s in sections if s['type'] == 'directory' and s['content']['name'].lower() != 'workdir']
    files       = [s['content'] for s in sections if s['type'] == 'file']
    parameters  = [s['content'] for s in sections if s['type'] == 'parameter']
    file_names = {f['name'] for f in files}
    def replace_placeholder(match):
        var_name = match.group(1)
        if var_name in file_names:
            return f"${{{var_name}}}"     
        else:
            return f"${{params.{var_name}}}" 
    usage = re.sub(r'<(.*?)>', replace_placeholder, run_sec.get('usage', '').strip())
    container_opts = " ".join(
        f"--volume ${{params.{d['name']}}}:{d['mount']}{':ro' if d.get('flag') == 'r' else ''}"
        for d in directories
    )

    # --- .nf ---
    nf_lines = ["nextflow.enable.dsl=2\n"]
    nf_lines.append("/*")
    nf_lines.append(f" * Pipeline: {res_sec.get('name', 'Unnamed')}")
    nf_lines.append(f" * Description: {res_sec.get('description', '')}")
    nf_lines.append(" */\n")

    nf_lines.append("// --- PARAMETERS ---")
    for d in directories:
        nf_lines.append(f"params.{d['name']} = \"/path/to/directory/{d['name']}\" // {d.get('description', '')}")    
    for f in files:
        nf_lines.append(f"params.{f['name']} = \"/path/to/file/{f['name']}\" // {f.get('description', '')}")
    for p in parameters:
        list_values=""
        if 'values' in p:
            list_values=(f" - Possible values: {p['values']}")
        main_val = ""
        if 'value' in p:
            main_val = p['value']
        elif 'values' in p:
            matches = re.findall(r"['\"](.*?)['\"]|([^,]+)", p['values'])
            if matches:
                first_match = matches[0]
                main_val = first_match[0] if first_match[0] else first_match[1].strip()
        nf_lines.append(f"params.{p['name']} = \"{main_val}\" // {p.get('description', '')} {list_values}")
    nf_lines.append("")
    nf_lines.append(f"process {tool_id.upper()} {{")
    nf_lines.append(f"    container '{image}'")
    nf_lines.append(f"    containerOptions \"{container_opts}\"\n")
    nf_lines.append("") 
    if files:
        nf_lines.append("    input:")
        for f in files:
            nf_lines.append(f"    path {f['name']}")
        nf_lines.append("") 
    nf_lines.append("    script:")
    nf_lines.append("    \"\"\"")
    nf_lines.append(f"    {script} {usage}")
    nf_lines.append("    \"\"\"")
    nf_lines.append("}\n")
    nf_lines.append("workflow {")
    if files:
        for f in files:
            nf_lines.append(f"    {f['name']} = Channel.fromPath(params.{f['name']})")
        channel_args = ", ".join(f['name'] for f in files)
        nf_lines.append(f"    {tool_id.upper()}({channel_args})")
    else:
        nf_lines.append(f"    {tool_id.upper()}()")
    nf_lines.append("}")
    with open(f"{tool_id}.nf", "w") as f:
        f.write("\n".join(nf_lines))
    print(f"\033[92mNextflow Pipeline '{tool_id}.nf' successfully generated.\033[0m")

    # --- file con comando di lancio ---
    my_path   = f"/c/path/to/{tool_id}"
    run_cmd = (f"docker run -it --rm -v /var/run/docker.sock:/var/run/docker.sock -v {my_path}:{my_path} -w {my_path} -e DOCKER_API_VERSION=1.44 nextflow/nextflow:26.04.2 nextflow run {tool_id}.nf" )

    with open(f"{tool_id}_nextflow.txt", "w") as f:
        f.write(run_cmd)
    print(f"\033[92mLaunch command file '{tool_id}_nextflow.txt' successfully generated.\033[0m")