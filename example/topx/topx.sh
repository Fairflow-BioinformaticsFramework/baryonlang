#!/usr/bin/env bash
set -euo pipefail

# ANSI color codes
RED='\033[91m'
WHITE='\033[97m'
YELLOW='\033[93m'
ORANGE='\033[38;5;208m'
GREEN='\033[92m'
RESET='\033[0m'

USAGE_STR=$(echo -e "${YELLOW}<workdir>${RESET}" "${YELLOW}<data>${RESET}" "${GREEN}<matrixname>${RESET}" "${GREEN}<format>${RESET}" "${GREEN}<threshold>${RESET}" "${GREEN}<separator>${RESET}" "${GREEN}<logged>${RESET}" "${GREEN}<type>${RESET}")

if [ "$#" -ne 8 ]; then
    echo -e "${WHITE}Usage: bash topx.sh ${USAGE_STR}${RESET}\n"
    echo -e "${YELLOW}Filters a gene count matrix, selecting the most relevant genes by variance (using edgeR) or by total count.${RESET}\n"
    echo -e "${WHITE}Arguments:${RESET}"
    echo -e "${YELLOW}workdir        ${RESET} [io]  Path to the working directory"
    echo -e "${YELLOW}data           ${RESET} [io]  Path to the folder containing input data and receiving output results"
    echo -e "${GREEN}matrixname     ${RESET}       Input file name without extension"
    echo -e "${GREEN}format         ${RESET}       Input file format"
    echo -e "${GREEN}threshold      ${RESET}       Threshold for selecting top genes (typically between 10 and 2000 depending on dataset size)"
    echo -e "${GREEN}separator      ${RESET}       File separator (use \\\\",\\\\" for CSV, \\\\"\t\\\\" for TSV)"
    echo -e "${GREEN}logged         ${RESET}       Indicates whether the count matrix values are already log-transformed (TRUE) or not (FALSE)."
    echo -e "${GREEN}type           ${RESET}       Type of analysis to perform."
    exit 1
fi

# Parse positional arguments
workdir="${1}"
data="${2}"
matrixname="${3}"
format="${4}"
threshold="${5}"
separator="${6}"
logged="${7}"
type="${8}"

# --- Input validation ---
errors=()

if [ ! -d "${workdir}" ]; then
    errors+=("Directory not found: workdir = ${workdir}")
fi
if [ ! -d "${data}" ]; then
    errors+=("Directory not found: data = ${data}")
fi
if ! echo "${format}" | grep -qE "^(csv|txt)$"; then
    errors+=("Invalid value for format: ${format}. Allowed: ['csv', 'txt']")
fi
if ! echo "${separator}" | grep -qE "^(,|\\t)$"; then
    errors+=("Invalid value for separator: ${separator}. Allowed: [',', '\\t']")
fi
if ! echo "${logged}" | grep -qE "^(FALSE|TRUE)$"; then
    errors+=("Invalid value for logged: ${logged}. Allowed: ['FALSE', 'TRUE']")
fi
if ! echo "${type}" | grep -qE "^(expression|variance)$"; then
    errors+=("Invalid value for type: ${type}. Allowed: ['expression', 'variance']")
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

mounts+=("-v \"${scratch_path}:/workdir\"")
docker_vals["workdir"]="/workdir"

# data: read-write directory [io]
mounts+=("-v \"$(realpath "${data}"):/data\"")
docker_vals["data"]="/data"

# --- Bind files and service volumes ---
declare -A mounted_folders
docker_vals["matrixname"]="${matrixname}"
docker_vals["format"]="${format}"
docker_vals["threshold"]="${threshold}"
docker_vals["separator"]="${separator}"
docker_vals["logged"]="${logged}"
docker_vals["type"]="${type}"

mount_str="${mounts[*]}"
cmd="docker run --rm ${mount_str} repbioinfo/topxv2:1 Rscript /bin/top.R <matrixname> <format> <separator> <logged> <threshold> <type>"
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