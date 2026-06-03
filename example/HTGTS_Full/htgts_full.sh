#!/usr/bin/env bash
set -euo pipefail

# ANSI color codes
RED='\033[91m'
WHITE='\033[97m'
YELLOW='\033[93m'
ORANGE='\033[38;5;208m'
GREEN='\033[92m'
RESET='\033[0m'

USAGE_STR=$(echo -e "${ORANGE}<fastq1>${RESET}" "${ORANGE}<fastq2>${RESET}" "${ORANGE}<expinfo>${RESET}" "${ORANGE}<expinfo2>${RESET}" "${YELLOW}<workdir>${RESET}" "${YELLOW}<outdir>${RESET}" "${GREEN}<configtype>${RESET}" "${GREEN}<assembly>${RESET}")

if [ "$#" -ne 8 ]; then
    echo -e "${WHITE}Usage: bash htgts_full.sh ${USAGE_STR}${RESET}\n"
    echo -e "${YELLOW}analizzare dati di sequenziamento e mappare le traslocazioni genomiche o i siti di rottura del DNA su larga scala${RESET}\n"
    echo -e "${WHITE}Arguments:${RESET}"
    echo -e "${ORANGE}fastq1         ${RESET} [cp]  the first input FASTQ file name"
    echo -e "${ORANGE}fastq2         ${RESET} [cp]  the second input FASTQ file name"
    echo -e "${ORANGE}expinfo        ${RESET} [ro]  name of the libseqInfo.txt file"
    echo -e "${ORANGE}expinfo2       ${RESET} [nc]  name of the libseqInfo2.txt file"
    echo -e "${YELLOW}workdir        ${RESET} [io]  percorso cartella di lavoro"
    echo -e "${YELLOW}outdir         ${RESET} [out] percorso cartella di output"
    echo -e "${GREEN}configtype     ${RESET}       tipo di cellule"
    echo -e "${GREEN}assembly       ${RESET}       reference genome version"
    exit 1
fi

# Parse positional arguments
fastq1="${1}"
fastq2="${2}"
expinfo="${3}"
expinfo2="${4}"
workdir="${5}"
outdir="${6}"
configtype="${7}"
assembly="${8}"

# --- Input validation ---
errors=()

if [ ! -d "${workdir}" ]; then
    errors+=("Directory not found: workdir = ${workdir}")
fi
if [ ! -d "${outdir}" ]; then
    errors+=("Directory not found: outdir = ${outdir}")
fi
if [ ! -f "${fastq1}" ]; then
    errors+=("File not found: fastq1 = ${fastq1}")
fi
if [ ! -f "${fastq2}" ]; then
    errors+=("File not found: fastq2 = ${fastq2}")
fi
if [ ! -f "${expinfo}" ]; then
    errors+=("File not found: expinfo = ${expinfo}")
fi
if [ ! -f "${expinfo2}" ]; then
    errors+=("File not found: expinfo2 = ${expinfo2}")
fi
if ! echo "${configtype}" | grep -qE "^(HTGTS_human|HTGTS_mouse|CELTICSseq|polyA)$"; then
    errors+=("Invalid value for configtype: ${configtype}. Allowed: ['HTGTS_human', 'HTGTS_mouse', 'CELTICSseq', 'polyA']")
fi
if ! echo "${assembly}" | grep -qE "^(hg38|mm9|mm10|custom)$"; then
    errors+=("Invalid value for assembly: ${assembly}. Allowed: ['hg38', 'mm9', 'mm10', 'custom']")
fi

if [ "${#errors[@]}" -gt 0 ]; then
    for e in "${errors[@]}"; do
        echo -e "${RED}ERROR:${RESET} ${WHITE}${e}${RESET}"
    done
    exit 1
fi

# --- Scratch directory setup ---
n=1
while true; do
    if [ -d "$(realpath "${workdir}")/scratch${n}" ] || [ -d "$(realpath "${outdir}")/scratch${n}" ]; then
        n=$((n + 1))
    else
        break
    fi
done

scratch_path="$(realpath "${workdir}")/scratch${n}"
mkdir -p "${scratch_path}"
scratch_out_path="$(realpath "${outdir}")/scratch${n}"
mkdir -p "${scratch_out_path}"

# --- Build docker volume mounts ---
mounts=()
declare -A docker_vals
service_idx=1

mounts+=("-v \"${scratch_path}:/workDir\"")
docker_vals["workdir"]="/workDir"

_host_out_base="$(realpath "${outdir}")"
mounts+=("-v \"${_host_out_base}:/outDir\"")
docker_vals["outdir"]="/outDir/scratch${n}"

# --- Bind files and service volumes ---
declare -A mounted_folders
_src_fastq1="$(realpath "${fastq1}")"
cp "${_src_fastq1}" "${scratch_path}/"
docker_vals["fastq1"]="/workDir/$(basename "${_src_fastq1}")"

_src_fastq2="$(realpath "${fastq2}")"
cp "${_src_fastq2}" "${scratch_path}/"
docker_vals["fastq2"]="/workDir/$(basename "${_src_fastq2}")"

_src_expinfo="$(realpath "${expinfo}")"
_dir_expinfo="$(dirname "${_src_expinfo}")"
if [ -z "${mounted_folders[${_dir_expinfo}]+x}" ]; then
    _m_point="/service${service_idx}"
    mounted_folders["${_dir_expinfo}"]="${_m_point}"
    mounts+=("-v \"${_dir_expinfo}:${_m_point}:ro\"")
    service_idx=$((service_idx + 1))
fi
docker_vals["expinfo"]="${mounted_folders[${_dir_expinfo}]}/$(basename "${_src_expinfo}")"

_src_expinfo2="$(realpath "${expinfo2}")"
_dir_expinfo2="$(dirname "${_src_expinfo2}")"
if [ -z "${mounted_folders[${_dir_expinfo2}]+x}" ]; then
    _m_point="/service${service_idx}"
    mounted_folders["${_dir_expinfo2}"]="${_m_point}"
    mounts+=("-v \"${_dir_expinfo2}:${_m_point}:ro\"")
    service_idx=$((service_idx + 1))
fi
docker_vals["expinfo2"]="${mounted_folders[${_dir_expinfo2}]}/$(basename "${_src_expinfo2}")"

docker_vals["configtype"]="${configtype}"
docker_vals["assembly"]="${assembly}"

# --- Assemble docker command ---
cmd="docker run --rm repbioinfo/htgts_pipeline_lts_v16:latest /Algorithm/HTGTS_Full.sh -fastq1 <fastq1> -fastq2 <fastq2> -expInfo <expinfo> -expInfo2 <expinfo2> -outDir <outdir> -configType <configtype> -assembly <assembly>"
mount_str="${mounts[*]}"
cmd="${cmd/docker run/docker run ${mount_str}}"

# Replace <placeholder> tokens with docker_vals
for key in "${!docker_vals[@]}"; do
    cmd="${cmd//<${key}>/${docker_vals[${key}]}}"
done

echo -e "\n${YELLOW}Running:${RESET}\n${WHITE}${cmd}${RESET}\n"

log_path="${scratch_path}/output_log.txt"
echo -e "${YELLOW}Log:${RESET} ${WHITE}${log_path}${RESET}\n"

eval "${cmd}" 2>&1 | tee "${log_path}"
exit_code=${PIPESTATUS[0]}

if [ "${exit_code}" -eq 0 ]; then
    echo -e "\n${GREEN}Done. Log saved to: ${log_path}${RESET}"
else
    echo -e "\n${RED}Docker exited with code ${exit_code}. See log: ${log_path}${RESET}"
fi
exit ${exit_code}