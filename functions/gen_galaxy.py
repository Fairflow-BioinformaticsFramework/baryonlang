import re
import xml.etree.ElementTree as ET
import xml.dom.minidom

def parse_values(raw_values):
    tokens = []
    for match in re.finditer(r"'[^']*'|\"[^\"]*\"|[^,]+", raw_values):
        token = match.group(0).strip()
        if token:
            tokens.append(token)
    return tokens
def restore_cdata_quotes(xml_string):
    def fix_cdata(match):
        return match.group(0).replace("&quot;", '"')
    return re.sub(r'<!\[CDATA\[.*?\]\]>', fix_cdata, xml_string, flags=re.DOTALL)

def gen_galaxy(sections):
    res_sec = next((s['content'] for s in sections if s['type'] == 'research'), {})
    run_sec = next((s['content'] for s in sections if s['type'] == 'run'), {})
    if run_sec.get('command', 'docker run --rm').strip().split()[0].lower() == 'singularity':
        print("\033[93mGalaxy tool generation skipped: Singularity runtime is not supported.\033[0m")
        return
    tool_name       = res_sec.get('name', 'output').replace(" ", "_")
    tool_name_lower = tool_name.lower()
    def is_input(flag):
        return flag in ('in', 'io')
    def is_output(flag):
        return flag in ('out', 'io')
    dir_mounts_map = {}
    directories = []
    for item in sections:
        if item['type'] == 'directory':
            content = item['content']
            name = content.get('name', '')
            mount = content.get('mount', f'/{name}').strip()
            dir_mounts_map[name.lower()] = mount
            if name.lower() == 'workdir':
                continue
            flag = content.get('flag', 'io').strip().lower()
            mount_clean = mount.lstrip('/')
            directories.append({
                'name':        name,
                'flag':        flag,
                'mount':       mount,
                'mount_clean': mount_clean,
                'description': content.get('description', mount_clean),
            })
    input_dirs  = [d for d in directories if is_input(d['flag'])]
    output_dirs = [d for d in directories if is_output(d['flag'])]
    all_mounts  = [d['mount'] for d in directories]
    file_params = set()
    for item in sections:
        if item['type'] == 'file':
            f_name = item['content'].get('name', 'input_file')
            file_params.add(f_name.lower())
    usage_val = run_sec.get('usage', '').strip()
    def replace_placeholders(match):
        placeholder_name = match.group(1)
        placeholder_lower = placeholder_name.lower()
        if placeholder_lower in dir_mounts_map:
            return dir_mounts_map[placeholder_lower]
        if placeholder_lower in file_params:
            return f"${{{placeholder_name}.element_identifier}}"
        return f"${placeholder_name}"
    formatted_usage = re.sub(r'<(.*?)>', replace_placeholders, usage_val)
    run_script    = run_sec.get('script', '').strip()
    exec_command  = f"    {run_script} {formatted_usage} > '$output_log' 2>&1 &&"
    tar_out_lines = []
    for d in output_dirs:
        tar_out_lines.append(f"    tar -chzf {d['mount_clean']}_archive.tar.gz -C {d['mount']} . &&")
    variants = ['standard']
    if input_dirs:
        variants.append('targz')
    for variant in variants:
        suffix = "_targz" if variant == 'targz' else ""
        current_id = f"{tool_name_lower}{suffix}"
        current_name = f"{tool_name}{suffix}"
        tool = ET.Element("tool", id=current_id, name=current_name, version="1.0.0")
        ET.SubElement(tool, "description").text = res_sec.get('description', '')
        reqs = ET.SubElement(tool, "requirements")
        ET.SubElement(reqs, "container", type="docker").text = run_sec.get('image', '').strip()
        cmd_lines = []
        if all_mounts:
            cmd_lines.append(f"    mkdir -p {' '.join(all_mounts)} &&")
        for item in sections:
            if item['type'] == 'file':
                f_name = item['content'].get('name', 'input_file')
                cmd_lines.append(f"    ln -s '${f_name}' '${{{f_name}.element_identifier}}' &&")
        for d in input_dirs:
            if variant == 'targz':
                cmd_lines.append(f"    tar -xf '${d['mount_clean']}_tar' -C {d['mount']} &&")
            else:
                cmd_lines.append(f"    #for $element in ${d['mount_clean']}_collection:")
                cmd_lines.append(f"        ln -s '$element' \"{d['mount']}/${{element.element_identifier}}\" &&")
                cmd_lines.append(f"    #end for")
        cmd_lines.append(exec_command)
        cmd_lines.extend(tar_out_lines)
        cmd_lines.append("    true")
        command_text = "\n".join(cmd_lines)
        command_el = ET.SubElement(tool, "command", detect_errors="exit_code")
        command_el.text = f"<![CDATA[\n{command_text}\n]]>"
        inputs = ET.SubElement(tool, "inputs")
        for item in sections:
            if item['type'] == 'file':
                content = item['content']
                f_name   = content.get('name', 'input_file')
                f_label  = content.get('description', f_name)
                f_format = content.get('format', 'data')
                ET.SubElement(inputs, "param", name=f_name, type="data", format=f_format, label=f_label)
        for item in sections:
            if item['type'] == 'parameter':
                content    = item['content']
                p_name     = content.get('name', 'param')
                p_label    = content.get('description', p_name)
                raw_values = content.get('values', content.get('value', ''))
                p_values   = parse_values(raw_values)
                if not p_values:
                    continue
                param_el = ET.SubElement(inputs, "param", name=p_name, type="select", label=p_label)
                for val in p_values:
                    clean_val = val.strip("'\"")
                    if not clean_val:
                        clean_val = val[1:-1]
                    ET.SubElement(param_el, "option", value=clean_val).text = val
        for d in input_dirs:
            if variant == 'targz':
                ET.SubElement(inputs, "param",
                              name=f"{d['mount_clean']}_tar",
                              type="data",
                              format="tar.gz",
                              label=f"{d['description']} (Tar Archive)")
            else:
                ET.SubElement(inputs, "param",
                              name=f"{d['mount_clean']}_collection",
                              type="data_collection",
                              format="data",
                              label=d['description'])
        outputs_el = ET.SubElement(tool, "outputs")
        ET.SubElement(outputs_el, "data", name="output_log", format="txt", label="${tool.name} Global Log")
        for d in output_dirs:
            ET.SubElement(outputs_el, "data",
                          name=f"archivio_{d['mount_clean']}",
                          format="tar.gz",
                          from_work_dir=f"{d['mount_clean']}_archive.tar.gz",
                          label=f"Full Archive {d['mount_clean'].capitalize()}")
        xml_str    = ET.tostring(tool, encoding="utf-8")
        dom        = xml.dom.minidom.parseString(xml_str)
        pretty_xml = dom.toprettyxml(indent="    ")
        final_xml = pretty_xml.replace("&lt;![CDATA[", "<![CDATA[") \
                      .replace("]]&gt;",        "]]>")       \
                      .replace("&gt;",          ">")         \
                      .replace("&lt;",          "<")         \
                      .replace("&amp;amp;",     "&")         \
                      .replace("&amp;",         "&")

        final_xml = restore_cdata_quotes(final_xml)        
        output_filename = f"{current_id}.xml"
        with open(output_filename, "w") as f:
            f.write(final_xml)
        print(f"\033[92mGalaxy Tool '{output_filename}' generated successfully.\033[0m")