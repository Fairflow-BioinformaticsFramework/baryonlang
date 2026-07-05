import os, sys, shutil, subprocess, re

# ANSI color codes
RED    = '\033[91m'
WHITE  = '\033[97m'
YELLOW = '\033[93m'
ORANGE = '\033[38;5;208m'
GREEN  = '\033[92m'
RESET  = '\033[0m'


def main():
    if os.name == 'nt':
        os.system('color')

    usage_str = ' '.join([f'\033[93m<workdir>{RESET}', f'\033[93m<outdir>{RESET}', f'\033[38;5;208m<xmlfile>{RESET}', f'\033[92m<configtype>{RESET}'])

    if len(sys.argv) != 5:
        print(f'{WHITE}Usage: python sample_sheettolibinfo.py {usage_str}{RESET}\n')
        print(f'{YELLOW}Converts experiment metadata from an Excel spreadsheet into a KEY=VALUE format readable by downstream HTGTS Bash pipeline scripts.{RESET}\n')
        print(f'{WHITE}Arguments:{RESET}')
        print(f'\033[93mworkdir        {RESET} [io]  working directory path')
        print(f'\033[93moutdir         {RESET} [out] output directory path')
        print(f'\033[38;5;208mxmlfile        {RESET} [nc]  name of the xml file')
        print(f'\033[92mconfigtype     {RESET}       cell type')
        sys.exit(1)

    # Parse positional arguments
    args = {}
    args['workdir'] = sys.argv[1]
    args['outdir'] = sys.argv[2]
    args['xmlfile'] = sys.argv[3]
    args['configtype'] = sys.argv[4]

    # --- Input validation ---
    errors = []

    if not os.path.isdir(args['workdir']):
        errors.append(f'Directory not found: workdir = {args["workdir"]}"')
    if not os.path.isdir(args['outdir']):
        errors.append(f'Directory not found: outdir = {args["outdir"]}"')
    if not os.path.isfile(args['xmlfile']):
        errors.append(f'File not found: xmlfile = {args["xmlfile"]}"')
    if args['configtype'] not in ['HTGTS_mouse', 'HTGTS_human', 'CELTICSseq', 'polyA']:
        errors.append(f"""Invalid value for configtype: {args["configtype"]}. Allowed: ['HTGTS_mouse', 'HTGTS_human', 'CELTICSseq', 'polyA']""")

    if errors:
        for e in errors:
            print(f'{RED}ERROR:{RESET} {WHITE}{e}{RESET}')
        sys.exit(1)

    # --- Scratch directory setup ---
    n = 1
    while True:
        if os.path.exists(os.path.join(os.path.abspath(args['workdir']), f'scratch{n}')) or os.path.exists(os.path.join(os.path.abspath(args['outdir']), f'output{n}')):
            n += 1
        else:
            break

    scratch_path = os.path.join(os.path.abspath(args['workdir']), f'scratch{n}')
    os.makedirs(scratch_path, exist_ok=True)
    scratch_out_path = os.path.join(os.path.abspath(args['outdir']), f'output{n}')
    os.makedirs(scratch_out_path, exist_ok=True)

    # --- Build docker volume mounts ---
    mounts = []
    docker_vals = {}   # placeholder -> docker-internal path
    service_idx = 1    # counter for read-only service mounts

    mounts.append(f'-v "{scratch_path}:/workDir"')
    docker_vals['workdir'] = '/workDir'

    _host_out_base = os.path.abspath(args['outdir'])
    mounts.append(f'-v "{_host_out_base}:/outDir"')
    docker_vals['outdir'] = f'/outDir/output{n}'

    # --- Bind files and service volumes ---
    mounted_folders = {}
    _src_xmlfile = os.path.abspath(args['xmlfile'])
    _dir_xmlfile = os.path.dirname(_src_xmlfile)
    if _dir_xmlfile not in mounted_folders:
        _m_point = f'/service{service_idx}'
        mounted_folders[_dir_xmlfile] = _m_point
        mounts.append(f'-v "{_dir_xmlfile}:{_m_point}:ro"')
        service_idx += 1
    docker_vals['xmlfile'] = f'{mounted_folders[_dir_xmlfile]}/{os.path.basename(_src_xmlfile)}'

    docker_vals['configtype'] = args['configtype']

    # --- Assemble docker command ---
    cmd = ' repbioinfo/htgts_pipeline_lts_v16:latest python3 /Algorithm/sample_sheetTolibInfo.py <xmlfile> <outdir>/fof.txt <outdir>/rof.txt <configtype>'
    mount_str = ' '.join(mounts)
    cmd = ' '.join(['docker run --rm -v <workdir>:/work -v <outdir>:/Out', mount_str, ' repbioinfo/htgts_pipeline_lts_v16:latest python3 /Algorithm/sample_sheetTolibInfo.py <xmlfile> <outdir>/fof.txt <outdir>/rof.txt <configtype>'])
    def replace_placeholder(match):
        key = match.group(1)
        return str(docker_vals.get(key, match.group(0)))

    cmd = re.sub(r'<([^>]+)>', replace_placeholder, cmd)

    print(f'\n{YELLOW}Running:{RESET}\n{WHITE}{cmd}{RESET}\n')

    log_path = os.path.join(scratch_path, 'output_log.txt')
    print(f'{YELLOW}Log:{RESET} {WHITE}{log_path}{RESET}\n')
    with open(log_path, 'w', encoding='utf-8') as log_f:
        p = subprocess.Popen(
            cmd, shell=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True
        )
        for line in p.stdout:
            sys.stdout.write(line)
            log_f.write(line)
        p.wait()

    if p.returncode == 0:
        print(f'\n{GREEN}Done. Log saved to: {log_path}{RESET}')
    else:
        print(f'\n{RED}Docker exited with code {p.returncode}. See log: {log_path}{RESET}')
    sys.exit(p.returncode)


if __name__ == '__main__':
    main()