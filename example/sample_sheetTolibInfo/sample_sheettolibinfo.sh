#!/usr/bin/env bash
set -euo pipefail

# ANSI color codes
RED='\033[91m'
WHITE='\033[97m'
YELLOW='\033[93m'
ORANGE='\033[38;5;208m'
GREEN='\033[92m'
RESET='\033[0m'

USAGE_STR=$(echo -e "${YELLOW}<workdir>${RESET}" "${YELLOW}<outdir>${RESET}" "${ORANGE}<xmlfile>${RESET}" "${GREEN}<configtype>${RESET}")

if [ "$#" -ne 4 ]; then
    echo -e "${WHITE}Usage: bash sample_sheettolibinfo.sh ${USAGE_STR}${RESET}\n"
    echo -e "${YELLOW}produce in output il file fof.txt e rof.txt nella cartella outdir${RESET}\n"
    echo -e "${WHITE}Arguments:${RESET}"
    echo -e "${YELLOW}workdir        ${RESET} [io]  percorso cartella di lavoro"
    echo -e "${YELLOW}outdir         ${RESET} [out] percorso cartella di output"
    echo -e "${ORANGE}xmlfile        ${RESET} [nc]  name del file xml"
    echo -e "${GREEN}configtype     ${RESET}       tipo di cellule"
    exit 1
fi

# Parse positional arguments
workdir="${1}"
outdir="${2}"
xmlfile="${3}"
configtype="${4}"

# --- Input validation ---
errors=()

if [ ! -d "${workdir}" ]; then
    errors+=("Directory not found: workdir = ${workdir}")
fi
if [ ! -d "${outdir}" ]; then
    errors+=("Directory not found: outdir = ${outdir}")
fi
if [ ! -f "${xmlfile}" ]; then
    errors+=("File not found: xmlfile = ${xmlfile}")
fi
if ! echo "${configtype}" | grep -qE "^(HTGTS_mouse|HTGTS_human|CELTICSseq|polyA)$"; then
    errors+=("Invalid value for configtype: ${configtype}. Allowed: ['HTGTS_mouse', 'HTGTS_human', 'CELTICSseq', 'polyA']")
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
_src_xmlfile="$(realpath "${xmlfile}")"
_dir_xmlfile="$(dirname "${_src_xmlfile}")"
if [ -z "${mounted_folders[${_dir_xmlfile}]+x}" ]; then
    _m_point="/service${service_idx}"
    mounted_folders["${_dir_xmlfile}"]="${_m_point}"
    mounts+=("-v \"${_dir_xmlfile}:${_m_point}:ro\"")
    service_idx=$((service_idx + 1))
fi
docker_vals["xmlfile"]="${mounted_folders[${_dir_xmlfile}]}/$(basename "${_src_xmlfile}")"

docker_vals["configtype"]="${configtype}"

# --- Assemble docker command ---
cmd="docker run --rm -v <workdir>:/work -v <outdir>:/Out repbioinfo/htgts_pipeline_lts_v16:latest python3 /Algorithm/sample_sheetTolibInfo.py <xmlfile> <outdir>/fof.txt <outdir>/rof.txt <configtype>"
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