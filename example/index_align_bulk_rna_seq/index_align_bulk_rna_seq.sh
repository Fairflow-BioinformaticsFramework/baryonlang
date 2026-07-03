#!/usr/bin/env bash
set -euo pipefail

# ANSI color codes
RED='\033[91m'
WHITE='\033[97m'
YELLOW='\033[93m'
ORANGE='\033[38;5;208m'
GREEN='\033[92m'
RESET='\033[0m'

USAGE_STR=$(echo -e "${YELLOW}<workdir>${RESET}" "${YELLOW}<genome>${RESET}" "${YELLOW}<scratch>${RESET}")

if [ "$#" -ne 3 ]; then
    echo -e "${WHITE}Usage: bash index_align_bulk_rna_seq.sh ${USAGE_STR}${RESET}\n"
    echo -e "${YELLOW}Bulk RNA-Seq analysis. Measures average gene expression across a cell population.${RESET}\n"
    echo -e "${WHITE}Arguments:${RESET}"
    echo -e "${YELLOW}workdir        ${RESET} [io]  working directory path"
    echo -e "${YELLOW}genome         ${RESET} [io]  genome directory path"
    echo -e "${YELLOW}scratch        ${RESET} [io]  scratch directory path(Data)"
    exit 1
fi

# Parse positional arguments
workdir="${1}"
genome="${2}"
scratch="${3}"

# --- Input validation ---
errors=()

if [ ! -d "${workdir}" ]; then
    errors+=("Directory not found: workdir = ${workdir}")
fi
if [ ! -d "${genome}" ]; then
    errors+=("Directory not found: genome = ${genome}")
fi
if [ ! -d "${scratch}" ]; then
    errors+=("Directory not found: scratch = ${scratch}")
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
    if [ -d "$(realpath "${workdir}")/scratch${n}" ]; then
        n=$((n + 1))
    else
        break
    fi
done

scratch_path="$(realpath "${workdir}")/scratch${n}"
mkdir -p "${scratch_path}"

# --- Build docker volume mounts ---
mounts=()
declare -A docker_vals
service_idx=1

mounts+=("-v \"${scratch_path}:/workDir\"")
docker_vals["workdir"]="/workDir"

# genome: read-write directory [io]
mounts+=("-v \"$(realpath "${genome}"):/genome\"")
docker_vals["genome"]="/genome"

# scratch: read-write directory [io]
mounts+=("-v \"$(realpath "${scratch}"):/scratch\"")
docker_vals["scratch"]="/scratch"

# --- Bind files and service volumes ---
declare -A mounted_folders

mount_str="${mounts[*]}"
cmd="docker run --rm ${mount_str} repbioinfo/rnaseqstar_v2 /home/index_align.sh "
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