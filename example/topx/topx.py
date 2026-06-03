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
        print(f'{YELLOW}Seleziona i geni con i valori piÃ¹ alti secondo una metrica scelta (espressione o varianza) e restituisce solo i top X dalla matrice di conteggi.{RESET}\n')
        print(f'{WHITE}Arguments:{RESET}')
        print(f'\033[93mworkdir        {RESET} [io]  percorso cartella di lavoro')
        print(f'\033[93mdata           {RESET} [io]  percorso cartella contenente i dati e ricevente i risultati')
        print(f'\033[92mmatrixname     {RESET}       name del file di input senza estensione')
        print(f'\033[92mformat         {RESET}       formato del file di input')
        print(f'\033[92mthreshold      {RESET}       Soglia per selezionare i geni top (solitamente fra 10 e 2000 a seconda delle dimensioni del datase)')
        print(f'\033[92mseparator      {RESET}       Separatore del file (Separatore usato nel file Usare \",\" per CSV, \"\t\" per TSV)')
        print(f'\033[92mlogged         {RESET}       Indica se i valori della matrice di conteggi sono giÃ  logâ€‘trasformati (TRUE) oppure no (FALSE).')
        print(f'\033[92mtype           {RESET}       Tipo di analisi da eseguire.')
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

    # --- Input validation ---
    errors = []

    if not os.path.isdir(args['workdir']):
        errors.append(f'Directory not found: workdir = {args["workdir"]}"')
    if not os.path.isdir(args['data']):
        errors.append(f'Directory not found: data = {args["data"]}"')
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

    # data: read-write directory [io]
    mounts.append(f'-v "{os.path.abspath(args["data"])}:/data"')
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
    cmd = 'docker run --rm repbioinfo/topxv2:1 Rscript /bin/top.R <matrixname> <format> <separator> <logged> <threshold> <type>'
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