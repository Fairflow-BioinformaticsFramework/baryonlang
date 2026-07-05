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

    usage_str = ' '.join([f'\033[38;5;208m<fastq1>{RESET}', f'\033[38;5;208m<fastq2>{RESET}', f'\033[38;5;208m<expinfo>{RESET}', f'\033[38;5;208m<expinfo2>{RESET}', f'\033[93m<workdir>{RESET}', f'\033[93m<outdir>{RESET}', f'\033[92m<configtype>{RESET}', f'\033[92m<assembly>{RESET}'])

    if len(sys.argv) != 9:
        print(f'{WHITE}Usage: python htgts_full.py {usage_str}{RESET}\n')
        print(f'{YELLOW}analyze sequencing data and map genomic translocations or DNA break sites on a large scale{RESET}\n')
        print(f'{WHITE}Arguments:{RESET}')
        print(f'\033[38;5;208mfastq1         {RESET} [cp]  the first input FASTQ file name')
        print(f'\033[38;5;208mfastq2         {RESET} [cp]  the second input FASTQ file name')
        print(f'\033[38;5;208mexpinfo        {RESET} [ro]  name of the libseqInfo.txt file')
        print(f'\033[38;5;208mexpinfo2       {RESET} [nc]  name of the libseqInfo2.txt file')
        print(f'\033[93mworkdir        {RESET} [io]  working directory path')
        print(f'\033[93moutdir         {RESET} [out] output directory path')
        print(f'\033[92mconfigtype     {RESET}       cell type')
        print(f'\033[92massembly       {RESET}       reference genome version')
        sys.exit(1)

    # Parse positional arguments
    args = {}
    args['fastq1'] = sys.argv[1]
    args['fastq2'] = sys.argv[2]
    args['expinfo'] = sys.argv[3]
    args['expinfo2'] = sys.argv[4]
    args['workdir'] = sys.argv[5]
    args['outdir'] = sys.argv[6]
    args['configtype'] = sys.argv[7]
    args['assembly'] = sys.argv[8]

    # --- Input validation ---
    errors = []

    if not os.path.isdir(args['workdir']):
        errors.append(f'Directory not found: workdir = {args["workdir"]}"')
    if not os.path.isdir(args['outdir']):
        errors.append(f'Directory not found: outdir = {args["outdir"]}"')
    if not os.path.isfile(args['fastq1']):
        errors.append(f'File not found: fastq1 = {args["fastq1"]}"')
    if not os.path.isfile(args['fastq2']):
        errors.append(f'File not found: fastq2 = {args["fastq2"]}"')
    if not os.path.isfile(args['expinfo']):
        errors.append(f'File not found: expinfo = {args["expinfo"]}"')
    if not os.path.isfile(args['expinfo2']):
        errors.append(f'File not found: expinfo2 = {args["expinfo2"]}"')
    if args['configtype'] not in ['HTGTS_human', 'HTGTS_mouse', 'CELTICSseq', 'polyA']:
        errors.append(f"""Invalid value for configtype: {args["configtype"]}. Allowed: ['HTGTS_human', 'HTGTS_mouse', 'CELTICSseq', 'polyA']""")
    if args['assembly'] not in ['hg38', 'mm9', 'mm10', 'custom']:
        errors.append(f"""Invalid value for assembly: {args["assembly"]}. Allowed: ['hg38', 'mm9', 'mm10', 'custom']""")

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
    _src_fastq1 = os.path.abspath(args['fastq1'])
    shutil.copy(_src_fastq1, scratch_path)
    docker_vals['fastq1'] = f'/workDir/{os.path.basename(_src_fastq1)}'

    _src_fastq2 = os.path.abspath(args['fastq2'])
    shutil.copy(_src_fastq2, scratch_path)
    docker_vals['fastq2'] = f'/workDir/{os.path.basename(_src_fastq2)}'

    _src_expinfo = os.path.abspath(args['expinfo'])
    _dir_expinfo = os.path.dirname(_src_expinfo)
    if _dir_expinfo not in mounted_folders:
        _m_point = f'/service{service_idx}'
        mounted_folders[_dir_expinfo] = _m_point
        mounts.append(f'-v "{_dir_expinfo}:{_m_point}:ro"')
        service_idx += 1
    docker_vals['expinfo'] = f'{mounted_folders[_dir_expinfo]}/{os.path.basename(_src_expinfo)}'

    _src_expinfo2 = os.path.abspath(args['expinfo2'])
    _dir_expinfo2 = os.path.dirname(_src_expinfo2)
    if _dir_expinfo2 not in mounted_folders:
        _m_point = f'/service{service_idx}'
        mounted_folders[_dir_expinfo2] = _m_point
        mounts.append(f'-v "{_dir_expinfo2}:{_m_point}:ro"')
        service_idx += 1
    docker_vals['expinfo2'] = f'{mounted_folders[_dir_expinfo2]}/{os.path.basename(_src_expinfo2)}'

    docker_vals['configtype'] = args['configtype']
    docker_vals['assembly'] = args['assembly']

    # --- Assemble docker command ---
    cmd = ' repbioinfo/htgts_pipeline_lts_v16:latest /Algorithm/HTGTS_Full.sh -fastq1 <fastq1> -fastq2 <fastq2> -expInfo <expinfo> -expInfo2 <expinfo2> -outDir <outdir> -configType <configtype> -assembly <assembly>'
    mount_str = ' '.join(mounts)
    cmd = ' '.join(['docker run --rm', mount_str, ' repbioinfo/htgts_pipeline_lts_v16:latest /Algorithm/HTGTS_Full.sh -fastq1 <fastq1> -fastq2 <fastq2> -expInfo <expinfo> -expInfo2 <expinfo2> -outDir <outdir> -configType <configtype> -assembly <assembly>'])
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