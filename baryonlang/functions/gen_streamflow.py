import re
import os

def gen_streamflow(sections, script_name):
    res_sec = next((s['content'] for s in sections if s['type'] == 'research'), {})
    run_sec = next((s['content'] for s in sections if s['type'] == 'run'), {})
    def optional_prefix(content):
        is_optional = content.get('optional', 'false').strip().lower() in ('true', 'yes')
        return "optional, " if is_optional else ""
    if run_sec.get('command', 'docker run --rm').strip().split()[0].lower() == 'singularity':
        print("\033[93mStreamflow tool generation skipped: Singularity runtime is not supported.\033[0m")
        return
    raw_name  = script_name or res_sec.get('name', 'baryon_tool')
    tool_name = raw_name.lower().replace(" ", "_")
    params_lines = []
    params_lines.append("# -------------------- Bayron project -------------")            
    params_lines.append("Creator: \"Baryon\"")
    params_lines.append(" ")
    for s in sections:
        stype = s['type']
        content = s['content']
        name = content.get('name')

        if stype == 'file':        
            params_lines.append(f"# {optional_prefix(content)}{content.get('description', name)}")
            params_lines.append(f"{name}:")
            params_lines.append("  class: File")
            params_lines.append(f"  path: path/to/file/{name} # <=====================")
            params_lines.append(" ")
        if stype == 'directory' and content.get('copy', 'false').strip().lower() in ('true', 'yes') and name.lower() not in ('workdir', 'outdir'):
            params_lines.append(f"# Real name of the folder mounted for '{name}' -- used to name its copy in workdir/scratch")
            params_lines.append(f"{name}_origin_name: \"\" # <=====================")
            params_lines.append(" ")
        if stype == 'parameter':
            if 'description' in content:
                params_lines.append(f"# {optional_prefix(content)}{content['description']}")
            if 'values' in content:
                params_lines.append(f"# Possible values: {content['values']}")
            val = ""
            if 'default' in content:
                val = content['default'].strip().strip("'\"")
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
        f"  {tool_name}-workflow:",
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
            flag = content.get('flag', '')
            ro_suffix = ':ro' if flag == 'ro' else ''
            yml_content.append(f"        # {optional_prefix(content)}{content.get('description', name)}   =====================>")
            yml_content.append(f"        - /path/to/directory/{name}:{mount_val}{ro_suffix}")
    filename = f"{tool_name}.yml"
    with open(filename, "w") as f:
        f.write("\n".join(yml_content))
    print(f"\033[92mStreamflow Workflow file '{filename}' successfully generated.\033[0m")

# --------------------- cwl file generation -------------------------------    
    wdmount = next((s['content'].get('mount', s['content'].get('name')) for s in sections  if s['type'] == 'directory' and s['content'].get('name', '').lower() == 'workdir'), None)
    cwl_lines = [
        "cwlVersion: v1.2",
        "class: CommandLineTool",
        "baseCommand: [bash, wrapper.sh]",
        "stdout: output_log.txt ",
        "requirements:",
        "  ShellCommandRequirement: {}",
        "  InitialWorkDirRequirement:",
        "    listing:",
        "      - entryname: wrapper.sh",
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
                mkdir_lines.append(f"          mkdir -p \"{dmount}/output$n\"")
            else:
                mkdir_lines.append(f"          mkdir -p \"{dmount}\"")
    cwl_lines.extend(mkdir_lines)
    # -------------------- directory copy: mirrors the file copy logic above --------------------
    dir_path_overrides = {}
    for s in sections:
        if s['type'] != 'directory':
            continue
        content = s['content']
        dname = content.get('name')
        dname_lower = dname.lower()
        if dname_lower in ('workdir', 'outdir'):
            continue
        flag = content.get('flag', '').strip().lower()
        dmount = content.get('mount', dname)
        copy_val = content.get('copy', 'false').strip().lower()
        if flag == 'ro' and copy_val in ('true', 'yes'):
            print(f"\033[93mWarning: directory '{dname}' has flag=ro and copy=true (redundant).\033[0m")
        if copy_val in ('true', 'yes'):
            cwl_lines.append(f"          mkdir -p \"{wdmount}/scratch$n/$(inputs.{dname}_origin_name)\"")
            cwl_lines.append(f"          cp -r \"{dmount}/.\" \"{wdmount}/scratch$n/$(inputs.{dname}_origin_name)/\"")
            dir_path_overrides[dname] = f"{wdmount}/scratch$n/$(inputs.{dname}_origin_name)"
    file_path_overrides = {}
    for s in sections:
        if s['type'] != 'file':
            continue
        content = s['content']
        fname = content.get('name')
        flag = content.get('flag', '').strip().lower()
        default_copy = 'no' if flag == 'ro' else 'yes'  
        copy_val = content.get('copy', default_copy).strip().lower()
        if flag == 'ro' and copy_val in ('true', 'yes'):
            print(f"\033[93mWarning: file '{fname}' has flag=ro and copy=true (redundant).\033[0m")
        if copy_val in ('true', 'yes'):
            cwl_lines.append(f"          cp \"$(inputs.{fname}.path)\" \"{wdmount}/scratch$n/$(inputs.{fname}.basename)\"")
            file_path_overrides[fname] = f"{wdmount}/scratch$n/$(inputs.{fname}.basename)"
    bash_script = []
    script_exec = run_sec.get('script', 'bash').strip()
    file_inputs = {s['content']['name'] for s in sections if s['type'] == 'file'}
    dir_mounts = {s['content']['name'].lower(): s['content'].get('mount', s['content'].get('name')) 
                  for s in sections if s['type'] == 'directory'}
    usage_val = run_sec.get('usage', '').strip()
    sections_map = {s['content'].get('name'): s['content'] for s in sections if 'name' in s['content']}
    def replace_with_path(match):
        name = match.group(1)
        name_lower = name.lower() 
        sec_content = sections_map.get(name, {})
        use_quote = sec_content.get('quote', 'false').strip().lower() in ('true', 'yes')
        if name in file_path_overrides:
            val = file_path_overrides[name]
        elif name in dir_path_overrides:
            val = dir_path_overrides[name]
        elif name_lower in dir_mounts:
            actual_mount = dir_mounts[name_lower]
            if name_lower == 'workdir':
                val = f"{actual_mount}/scratch$n"
            elif name_lower == 'outdir':
                val = f"{actual_mount}/output$n"
            else:
                val = actual_mount
        elif name in file_inputs:
            val = f"$(inputs.{name}.path)"
        else:
            val = f"$(inputs.{name})"
        return f'"{val}"' if use_quote else val
    formatted_usage = re.sub(r'<(.*?)>', replace_with_path, usage_val)
    bash_script.append(f"          {script_exec} {formatted_usage}")
    bash_script.append("          exit_code=$?")
    bash_script.append(f"          cp output_log.txt {wdmount}/scratch$n/output_log.txt")
    bash_script.append(f"          cp wrapper.sh \"{wdmount}/scratch$n/wrapper.sh\"")
    bash_script.append("          exit $exit_code")    
    cwl_lines.extend(bash_script)
    cwl_lines.append("        writable: false")
    cwl_lines.append("inputs: []" if not (any(s['type'] in ['parameter', 'file'] for s in sections) or dir_path_overrides) else "inputs:")
    for s in sections:
        stype = s['type']
        content = s['content']
        name = content.get('name')
        if stype == 'parameter':
            cwl_lines.append(f"  {name}:\n    type: string")
        elif stype == 'file':
            cwl_lines.append(f"  {name}:\n    type: File")
        elif stype == 'directory' and name in dir_path_overrides:
            cwl_lines.append(f"  {name}_origin_name:\n    type: string")
    cwl_lines.append("outputs: []")
    with open(f"{tool_name}.cwl", "w") as f:
        f.write("\n".join(cwl_lines))
    print(f"\033[92mCWL file '{tool_name}.cwl' successfully generated.\033[0m")
    # --- launch command file ---
    directories = [s['content'] for s in sections if s['type'] == 'directory']
    workdir_mount = "$(pwd)"
    volume_flags = (
        "-v /var/run/docker.sock:/var/run/docker.sock "
        "-v $(which docker):/usr/bin/docker "
        f'-v "{workdir_mount}:/workflow"'
    )
    volume_flags += f" -v /common/base/path:/common/base/path"
    run_cmd = (
        f"docker run --rm -it {volume_flags} -w /workflow "
        f"alphaunito/streamflow streamflow run {tool_name}.yml"
    )
    command_file = f"{tool_name}_command.txt"
    marker = "# ------- streamflow sample command ------- #"
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