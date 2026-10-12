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

    usage_str = ' '.join([f'\033[93m<workdir>{RESET}', f'\033[93m<genome>{RESET}', f'\033[93m<scratch>{RESET}'])

    if len(sys.argv) != 4:
        print(f'{WHITE}Usage: python index_align_bulk_rna_seq.py {usage_str}{RESET}\n')
        print(f'{YELLOW}Bulk RNA-Seq analysis. Measures average gene expression across a cell population.{RESET}\n')
        print(f'{WHITE}Arguments:{RESET}')
        print(f'\033[93mworkdir        {RESET} [io]  working directory path')
        print(f'\033[93mgenome         {RESET} [io]  genome directory path')
        print(f'\033[93mscratch        {RESET} [io]  scratch directory path(Data)')
        sys.exit(1)

    # Parse positional arguments
    args = {}
    args['workdir'] = sys.argv[1]
    args['genome'] = sys.argv[2]
    args['scratch'] = sys.argv[3]

    # --- Resolve 'default' keyword using each parameter's configured value= ---

    # --- Input validation ---
    errors = []

    if not os.path.isdir(args['workdir']):
        errors.append(f'Directory not found: workdir = {args["workdir"]}')
    if args['genome'] != 'dummy' and not os.path.isdir(args['genome']):
        errors.append(f'Directory not found: genome = {args["genome"]}')
    if not os.path.isdir(args['scratch']):
        errors.append(f'Directory not found: scratch = {args["scratch"]}')

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

    mounts.append(f'-v "{scratch_path}:/workDir"')
    docker_vals['workdir'] = '/workDir'

    # genome is optional: mount only if a real path is passed, use 'dummy' placeholder otherwise
    if args['genome'] != 'dummy':
        # genome: copy into workdir, then mount the copy (read-write directory [io])
        _copy_src_genome = os.path.abspath(args["genome"])
        _copy_dst_genome = os.path.join(scratch_path, os.path.basename(_copy_src_genome))
        shutil.copytree(_copy_src_genome, _copy_dst_genome, dirs_exist_ok=True)
        mounts.append(f'-v "{_copy_dst_genome}:/genome"')
        docker_vals['genome'] = '/genome'
    else:
        docker_vals['genome'] = 'dummy'

    # scratch: read-write directory [io]
    mounts.append(f'-v "{os.path.abspath(args["scratch"])}:/scratch"')
    docker_vals['scratch'] = '/scratch'

    # --- Bind files and service volumes ---
    mounted_folders = {}

    # --- Assemble docker command ---
    cmd = ' repbioinfo/rnaseqstar_v2 /home/index_align.sh '
    mount_str = ' '.join(mounts)
    cmd = ' '.join(['docker run --rm', mount_str, ' repbioinfo/rnaseqstar_v2 /home/index_align.sh '])
    PARAM_NAMES = []
    QUOTE_NAMES = []
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