#!/usr/bin/env bash
set -euo pipefail

# ANSI color codes
RED='\033[91m'
WHITE='\033[97m'
YELLOW='\033[93m'
ORANGE='\033[38;5;208m'
GREEN='\033[92m'
RESET='\033[0m'

USAGE_STR=$(echo -e "${ORANGE}<filein>${RESET}" "${YELLOW}<workdir>${RESET}" "${YELLOW}<outdir>${RESET}" "${GREEN}<fileout>${RESET}" "${GREEN}<command>${RESET}" "${GREEN}<length>${RESET}")

if [ "$#" -ne 6 ]; then
    echo -e "${WHITE}Usage: bash seqkit.sh ${USAGE_STR}${RESET}\n"
    echo -e "${YELLOW}A comprehensive toolkit for FASTA/FASTQ file manipulation, filtering, and statistics.${RESET}\n"
    echo -e "${WHITE}Arguments:${RESET}"
    echo -e "${ORANGE}filein         ${RESET} [copy=yes] file to analize"
    echo -e "${YELLOW}workdir        ${RESET} [io]  working directory"
    echo -e "${YELLOW}outdir         ${RESET} [out] output directory"
    echo -e "${GREEN}fileout        ${RESET}       output file name"
    echo -e "${GREEN}command        ${RESET}       SeqKit subcommands to run"
    echo -e "${GREEN}length         ${RESET}       maximum sequence length to keep (-M option)"
    exit 1
fi

# Parse positional arguments
filein="${1}"
workdir="${2}"
outdir="${3}"
fileout="${4}"
command="${5}"
length="${6}"

# --- Resolve 'default' keyword using each parameter's configured value= ---
if [ "${command}" = "default" ]; then
    command="stats"
fi

# --- Input validation ---
errors=()

if [ ! -d "${workdir}" ]; then
    errors+=("Directory not found: workdir = ${workdir}")
fi
if [ ! -d "${outdir}" ]; then
    errors+=("Directory not found: outdir = ${outdir}")
fi
if [ ! -f "${filein}" ]; then
    errors+=("File not found: filein = ${filein}")
fi
if ! echo "${command}" | grep -qE "^(seq|stats)$"; then
    errors+=("Invalid value for command: ${command}. Allowed: ['seq', 'stats']")
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
    if [ -d "$(realpath "${workdir}")/scratch${n}" ] || [ -d "$(realpath "${outdir}")/output${n}" ]; then
        n=$((n + 1))
    else
        break
    fi
done

scratch_path="$(realpath "${workdir}")/scratch${n}"
mkdir -p "${scratch_path}"
scratch_out_path="$(realpath "${outdir}")/output${n}"
mkdir -p "${scratch_out_path}"

# --- Build docker volume mounts ---
mounts=()
declare -A docker_vals
service_idx=1

mounts+=("-v \"${scratch_path}:/workDir\"")
docker_vals["workdir"]="/workDir"

mounts+=("-v \"${scratch_out_path}:/outDir\"")
docker_vals["outdir"]="/outDir"

# --- Bind files and service volumes ---
declare -A mounted_folders
_src_filein="$(realpath "${filein}")"
cp "${_src_filein}" "${scratch_path}/"
docker_vals["filein"]="/workDir/$(basename "${_src_filein}")"

docker_vals["fileout"]="${fileout}"
docker_vals["command"]="${command}"
docker_vals["length"]="${length}"

mount_str="${mounts[*]}"
mount_str="${mount_str//-v \"/ --bind }"
mount_str="${mount_str//\"}"
PARAM_NAMES=("fileout" "command" "length")
QUOTE_KEYS=()
special_chars_re='[;&|()<>$`"'"'"'[:space:]]'
cmd="singularity exec --writable-tmpfs ${mount_str} docker://quay.io/biocontainers/seqkit:2.8.1--h9ee0642_0 seqkit <command> -N <length> <filein> -o <outdir>/<fileout>"
for key in "${!docker_vals[@]}"; do
    val="${docker_vals[${key}]}"
    is_param=0
    for p_name in "${PARAM_NAMES[@]}"; do
        if [ "${key}" = "${p_name}" ]; then is_param=1; break; fi
    done
    force_quote=0
    for q_name in "${QUOTE_KEYS[@]}"; do
        if [ "${key}" = "${q_name}" ]; then force_quote=1; break; fi
    done
    if [ "${force_quote}" -eq 1 ] || ( [ "${is_param}" -eq 1 ] && [[ "${val}" =~ ${special_chars_re} ]] ); then
        escaped_val=$(echo "${val}" | sed 's/"/\\"/g')
        cmd="${cmd//<${key}>/\"${escaped_val}\"}"
    else
        cmd="${cmd//<${key}>/${val}}"
    fi
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