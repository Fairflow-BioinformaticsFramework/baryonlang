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

    usage_str = ' '.join([f'\033[38;5;208m<filein>{RESET}', f'\033[93m<workdir>{RESET}', f'\033[93m<outdir>{RESET}', f'\033[92m<fileout>{RESET}', f'\033[92m<command>{RESET}', f'\033[92m<length>{RESET}'])

    if len(sys.argv) != 7:
        print(f'{WHITE}Usage: python seqkit.py {usage_str}{RESET}\n')
        print(f'{YELLOW}A comprehensive toolkit for FASTA/FASTQ file manipulation, filtering, and statistics.{RESET}\n')
        print(f'{WHITE}Arguments:{RESET}')
        print(f'\033[38;5;208mfilein         {RESET} [cp]  file to analize')
        print(f'\033[93mworkdir        {RESET} [io]  working directory')
        print(f'\033[93moutdir         {RESET} [out] output directory')
        print(f'\033[92mfileout        {RESET}       output file name')
        print(f'\033[92mcommand        {RESET}       SeqKit subcommands to run')
        print(f'\033[92mlength         {RESET}       maximum sequence length to keep (-M option)')
        sys.exit(1)

    # Parse positional arguments
    args = {}
    args['filein'] = sys.argv[1]
    args['workdir'] = sys.argv[2]
    args['outdir'] = sys.argv[3]
    args['fileout'] = sys.argv[4]
    args['command'] = sys.argv[5]
    args['length'] = sys.argv[6]

    # --- Input validation ---
    errors = []

    if not os.path.isdir(args['workdir']):
        errors.append(f'Directory not found: workdir = {args["workdir"]}"')
    if not os.path.isdir(args['outdir']):
        errors.append(f'Directory not found: outdir = {args["outdir"]}"')
    if not os.path.isfile(args['filein']):
        errors.append(f'File not found: filein = {args["filein"]}"')
    if args['command'] not in ['seq', 'stats']:
        errors.append(f"""Invalid value for command: {args["command"]}. Allowed: ['seq', 'stats']""")

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

    mounts.append(f'-v "{scratch_out_path}:/outDir"')
    docker_vals['outdir'] = '/outDir'

    # --- Bind files and service volumes ---
    mounted_folders = {}
    _src_filein = os.path.abspath(args['filein'])
    shutil.copy(_src_filein, scratch_path)
    docker_vals['filein'] = f'/workDir/{os.path.basename(_src_filein)}'

    docker_vals['fileout'] = args['fileout']
    docker_vals['command'] = args['command']
    docker_vals['length'] = args['length']

    # --- Assemble docker command ---
    cmd = ' docker://quay.io/biocontainers/seqkit:2.8.1--h9ee0642_0 seqkit <command> -M <length> <filein> -o <outdir>/<fileout>'
    mount_str = ' '.join(mounts)
    mount_str = mount_str.replace('-v "', '--bind ').replace('"', '')
    cmd = ' '.join(['singularity exec --writable-tmpfs', mount_str, ' docker://quay.io/biocontainers/seqkit:2.8.1--h9ee0642_0 seqkit <command> -M <length> <filein> -o <outdir>/<fileout>'])
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