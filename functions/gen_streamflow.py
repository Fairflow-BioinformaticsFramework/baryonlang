import re

def gen_streamflow(sections):
    res_sec = next((s['content'] for s in sections if s['type'] == 'research'), {})
    run_sec = next((s['content'] for s in sections if s['type'] == 'run'), {})
    tool_name = res_sec.get('name', 'output').replace(" ", "_")
    tool_name_lower = res_sec.get('name', 'output').replace(" ", "_").lower()
    params_lines = []
    params_lines.append("# -------------------- Bayron project -------------")            
    params_lines.append("Creator: \"Baryon\"")
    params_lines.append(" ")
    for s in sections:
        stype = s['type']
        content = s['content']
        name = content.get('name')
        if stype == 'file':        
            params_lines.append(f"# {content['description']}")
            params_lines.append(f"{name}:")
            params_lines.append("  class: File")
            params_lines.append(f"  path: path/to/file/{name} # <=====================")
            params_lines.append(" ")
        if stype == 'parameter':
            if 'description' in content:
                params_lines.append(f"# {content['description']}")
            if 'values' in content:
                params_lines.append(f"# Possible values: {content['values']}")
            val = ""
            if 'value' in content:
                val = content['value']
            elif 'values' in content:
                matches = re.findall(r"['\"](.*?)['\"]|([^,]+)", content['values'])
                if matches:
                    first_match = matches[0]
                    val = first_match[0] if first_match[0] else first_match[1].strip()
            params_lines.append(f"{name}: \"{val}\" # <=====================")   
            params_lines.append(" ")   
    filename = f"{tool_name}-params.yml"
    with open(filename, "w") as f:
        f.write("\n".join(params_lines))
    print(f"\033[92mParameter file '{filename}' successfully generated.\033[0m")
    image_name = run_sec.get('image', 'repbioinfo/default:latest').strip()
    yml_content = [
        "version: v1.0",
        "workflows:",
        f"  {tool_name_lower}-workflow:",
        "    type: cwl",
        "    config:",
        f"      file: {tool_name}.cwl",
        f"      settings: {tool_name}-params.yml",
        "    bindings:",
        "      - step: /",
        "        target:",
        f"          deployment: docker-{tool_name}",
        "deployments:",
        f"  docker-{tool_name}:",
        "    type: docker",
        "    config:",
        f"      image: {image_name}",
        "      volume:",
    ]
    for s in sections:
        stype = s['type']
        content = s['content']
        name = content.get('name')
        if stype == 'directory':
            mount_val = content.get('mount', name)
            desc_val = content.get('description', name).replace(' ', '/')
            flag = content.get('flag', '')
            ro_suffix = ':ro' if flag == 'r' else ''
            yml_content.append(f"        # {content['description']}   =====================>")
            yml_content.append(f"        - /c/{desc_val}:{mount_val}{ro_suffix} ")
    filename = f"{tool_name}.yml"
    with open(filename, "w") as f:
        f.write("\n".join(yml_content))
    print(f"\033[92mStreamflow Workflow file '{filename}' successfully generated.\033[0m")

# --------------------- cwl file generation -------------------------------    
    wdmount = next((s['content'].get('mount', s['content'].get('name')) for s in sections  if s['type'] == 'directory' and s['content'].get('name', '').lower() == 'workdir'), None)
    cwl_lines = [
        "cwlVersion: v1.2",
        "class: CommandLineTool",
        "baseCommand: [bash, elabora.sh]",
        "stdout: output_log.txt ",
        "requirements:",
        "  ShellCommandRequirement: {}",
        "  InitialWorkDirRequirement:",
        "    listing:",
        "      - entryname: elabora.sh",
        "        entry: |",
        "          #!/bin/bash",
        "          n=1",
        f"          while [ -d \"{wdmount}/scratch$n\" ]; do",
        "            n=`expr $n + 1`",
        "          done",
    ]
    mkdir_lines = []
    for s in sections:
        if s['type'] == 'directory':
            dname = s['content'].get('name', '').lower()
            dmount = s['content'].get('mount', s['content'].get('name'))
            if dname.lower() == 'workdir':
                mkdir_lines.append(f"          mkdir -p \"{dmount}/scratch$n\"")
            elif dname.lower() == 'outdir':
                mkdir_lines.append(f"          mkdir -p \"{dmount}/scratch$n\"")
            else:
                mkdir_lines.append(f"          mkdir -p \"{dmount}\"")
    cwl_lines.extend(mkdir_lines)
    file_path_overrides = {}
    for s in sections:
        if s['type'] == 'file' and s['content'].get('flag', '').lower() == 'c':
            fname = s['content'].get('name')
            cwl_lines.append(f"          cp \"$(inputs.{fname}.path)\" \"{wdmount}/scratch$n/$(inputs.{fname}.basename)\"")
            file_path_overrides[fname] = f"{wdmount}/scratch$n/$(inputs.{fname}.basename)"

    bash_script = []
    script_exec = run_sec.get('script', 'bash').strip()
    file_inputs = {s['content']['name'] for s in sections if s['type'] == 'file'}
    dir_mounts = {s['content']['name'].lower(): s['content'].get('mount', s['content'].get('name')) 
                  for s in sections if s['type'] == 'directory'}
    usage_val = run_sec.get('usage', '').strip()
    def replace_with_path(match):
        name = match.group(1)
        name_lower = name.lower() 
        if name in file_path_overrides:
            return file_path_overrides[name]  
        if name_lower in dir_mounts:
            actual_mount = dir_mounts[name_lower]
            if name_lower in ['workdir', 'outdir']:
                return f"{actual_mount}/scratch$n"
            return actual_mount
        if name in file_inputs:
            return f"$(inputs.{name}.path)"
        return f"$(inputs.{name})"
    formatted_usage = re.sub(r'<(.*?)>', replace_with_path, usage_val)
    bash_script.append(f"          {script_exec} {formatted_usage} &&")
    bash_script.append(f"          cp output_log.txt {wdmount}/scratch$n/output_log.txt &&")
    bash_script.append("          rm output_log.txt")
    cwl_lines.extend(bash_script)
    cwl_lines.append("        writable: false")
    cwl_lines.append("inputs: []" if not any(s['type'] in ['parameter', 'file'] for s in sections) else "inputs:")
    for s in sections:
        stype = s['type']
        content = s['content']
        name = content.get('name')
        if stype == 'parameter':
            cwl_lines.append(f"  {name}:\n    type: string")
        elif stype == 'file':
            cwl_lines.append(f"  {name}:\n    type: File")
    cwl_lines.append("outputs: []")
    with open(f"{tool_name}.cwl", "w") as f:
        f.write("\n".join(cwl_lines))
    print(f"\033[92mCWL file '{tool_name}.cwl' successfully generated.\033[0m")
