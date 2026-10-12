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

    usage_str = ' '.join([f'\033[93m<workdir>{RESET}', f'\033[93m<data>{RESET}', f'\033[92m<matrixname>{RESET}', f'\033[92m<format>{RESET}', f'\033[92m<threshold>{RESET}', f'\033[92m<separator>{RESET}', f'\033[92m<logged>{RESET}', f'\033[92m<type>{RESET}'])

    if len(sys.argv) != 9:
        print(f'{WHITE}Usage: python topx.py {usage_str}{RESET}\n')
        print(f'{YELLOW}Filters a gene count matrix, selecting the most relevant genes by variance (using edgeR) or by total count.{RESET}\n')
        print(f'{WHITE}Arguments:{RESET}')
        print(f'\033[93mworkdir        {RESET} [io]  Path to the working directory')
        print(f'\033[93mdata           {RESET} [io]  Path to the folder containing input data and receiving output results')
        print(f'\033[92mmatrixname     {RESET}       Input file name without extension')
        print(f'\033[92mformat         {RESET}       Input file format')
        print(f'\033[92mthreshold      {RESET}       Threshold for selecting top genes (typically between 10 and 2000 depending on dataset size)')
        print(f'\033[92mseparator      {RESET}       File separator (use \",\" for CSV, \"\t\" for TSV)')
        print(f'\033[92mlogged         {RESET}       Indicates whether the count matrix values are already log-transformed (TRUE) or not (FALSE).')
        print(f'\033[92mtype           {RESET}       Type of analysis to perform.')
        sys.exit(1)

    # Parse positional arguments
    args = {}
    args['workdir'] = sys.argv[1]
    args['data'] = sys.argv[2]
    args['matrixname'] = sys.argv[3]
    args['format'] = sys.argv[4]
    args['threshold'] = sys.argv[5]
    args['separator'] = sys.argv[6]
    args['logged'] = sys.argv[7]
    args['type'] = sys.argv[8]

    # --- Resolve 'default' keyword using each parameter's configured value= ---
    if args['matrixname'] == 'default':
        args['matrixname'] = 'annotated'
    if args['format'] == 'default':
        args['format'] = 'csv'
    if args['threshold'] == 'default':
        args['threshold'] = '10'
    if args['separator'] == 'default':
        args['separator'] = ','

    # --- Input validation ---
    errors = []

    if not os.path.isdir(args['workdir']):
        errors.append(f'Directory not found: workdir = {args["workdir"]}')
    if not os.path.isdir(args['data']):
        errors.append(f'Directory not found: data = {args["data"]}')
    if args['format'] not in ['csv', 'txt']:
        errors.append(f"""Invalid value for format: {args["format"]}. Allowed: ['csv', 'txt']""")
    if args['separator'] not in [',', '\\t']:
        errors.append(f"""Invalid value for separator: {args["separator"]}. Allowed: [',', '\\t']""")
    if args['logged'] not in ['FALSE', 'TRUE']:
        errors.append(f"""Invalid value for logged: {args["logged"]}. Allowed: ['FALSE', 'TRUE']""")
    if args['type'] not in ['expression', 'variance']:
        errors.append(f"""Invalid value for type: {args["type"]}. Allowed: ['expression', 'variance']""")

    if errors:
        for e in errors:
            print(f'{RED}ERROR:{RESET} {WHITE}{e}{RESET}')
        sys.exit(1)

    # --- Scratch directory setup ---
    n = 1
    while True:
        if os.path.exists(os.path.join(os.path.abspath(args['workdir']), f'scratch{n}')):
            n += 1
        else:
            break

    scratch_path = os.path.join(os.path.abspath(args['workdir']), f'scratch{n}')
    os.makedirs(scratch_path, exist_ok=True)

    # --- Build docker volume mounts ---
    mounts = []
    docker_vals = {}   # placeholder -> docker-internal path
    service_idx = 1    # counter for read-only service mounts

    mounts.append(f'-v "{scratch_path}:/workdir"')
    docker_vals['workdir'] = '/workdir'

    # data: copy into workdir, then mount the copy (read-write directory [io])
    _copy_src_data = os.path.abspath(args["data"])
    _copy_dst_data = os.path.join(scratch_path, os.path.basename(_copy_src_data))
    shutil.copytree(_copy_src_data, _copy_dst_data, dirs_exist_ok=True)
    mounts.append(f'-v "{_copy_dst_data}:/data"')
    docker_vals['data'] = '/data'

    # --- Bind files and service volumes ---
    mounted_folders = {}
    docker_vals['matrixname'] = args['matrixname']
    docker_vals['format'] = args['format']
    docker_vals['threshold'] = args['threshold']
    docker_vals['separator'] = args['separator']
    docker_vals['logged'] = args['logged']
    docker_vals['type'] = args['type']

    # --- Assemble docker command ---
    cmd = ' repbioinfo/topxv2:1 Rscript /bin/top.R <matrixname> <format> <separator> <logged> <threshold> <type>'
    mount_str = ' '.join(mounts)
    cmd = ' '.join(['docker run --rm', mount_str, ' repbioinfo/topxv2:1 Rscript /bin/top.R <matrixname> <format> <separator> <logged> <threshold> <type>'])
    PARAM_NAMES = ['matrixname', 'format', 'threshold', 'separator', 'logged', 'type']
    QUOTE_NAMES = ['data', 'format', 'separator']
    def replace_placeholder(match):
        key = match.group(1)
        val = str(docker_vals.get(key, match.group(0)))
        if key in QUOTE_NAMES and val != 'dummy':
            escaped_val = val.replace('"', '\\"')
            return f'"{escaped_val}"'
        if key in PARAM_NAMES:
            if re.search(r'[;&|()<>$`"\'\s]', val):
                escaped_val = val.replace('"', '\\"')
                return f'"{escaped_val}"'
        return val

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