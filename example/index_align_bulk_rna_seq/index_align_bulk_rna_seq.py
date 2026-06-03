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
        print(f'{YELLOW}Funzione per eseguire l\'allineamento e l\'indicizzazione{RESET}\n')
        print(f'{WHITE}Arguments:{RESET}')
        print(f'\033[93mworkdir        {RESET} [io]  percorso cartella di lavoro')
        print(f'\033[93mgenome         {RESET} [io]  percorso cartella di lavoro, Genome')
        print(f'\033[93mscratch        {RESET} [io]  percorso cartella Data, qui viene salvato il log e andrebbero piazzati i file di output. Scratch')
        sys.exit(1)

    # Parse positional arguments
    args = {}
    args['workdir'] = sys.argv[1]
    args['genome'] = sys.argv[2]
    args['scratch'] = sys.argv[3]

    # --- Input validation ---
    errors = []

    if not os.path.isdir(args['workdir']):
        errors.append(f'Directory not found: workdir = {args["workdir"]}"')
    if not os.path.isdir(args['genome']):
        errors.append(f'Directory not found: genome = {args["genome"]}"')
    if not os.path.isdir(args['scratch']):
        errors.append(f'Directory not found: scratch = {args["scratch"]}"')

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

    # genome: read-write directory [io]
    mounts.append(f'-v "{os.path.abspath(args["genome"])}:/genome"')
    docker_vals['genome'] = '/genome'

    # scratch: read-write directory [io]
    mounts.append(f'-v "{os.path.abspath(args["scratch"])}:/scratch"')
    docker_vals['scratch'] = '/scratch'

    # --- Bind files and service volumes ---
    mounted_folders = {}

    # --- Assemble docker command ---
    cmd = 'docker run --rm repbioinfo/rnaseqstar_v2 /home/index_align.sh '
    mount_str = ' '.join(mounts)
    cmd = cmd.replace("docker run", f"docker run {mount_str}", 1)
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