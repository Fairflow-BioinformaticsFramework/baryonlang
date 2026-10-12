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

# --- Resolve 'default' keyword using each parameter's configured value= ---

# --- Input validation ---
errors=()

if [ ! -d "${workdir}" ]; then
    errors+=("Directory not found: workdir = ${workdir}")
fi
if [ "${genome}" != "dummy" ] && [ ! -d "${genome}" ]; then
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

# genome is optional: mount only if a real path is passed, use 'dummy' placeholder otherwise
if [ "${genome}" != "dummy" ]; then
    # genome: copy into workdir, then mount the copy (read-write directory [io])
    _copy_src_genome="$(realpath "${genome}")"
    _copy_dst_genome="${scratch_path}/$(basename "${_copy_src_genome}")"
    cp -r "${_copy_src_genome}" "${_copy_dst_genome}"
    mounts+=("-v \"${_copy_dst_genome}:/genome\"")
    docker_vals["genome"]="/genome"
else
    docker_vals["genome"]="dummy"
fi

# scratch: read-write directory [io]
mounts+=("-v \"$(realpath "${scratch}"):/scratch\"")
docker_vals["scratch"]="/scratch"

# --- Bind files and service volumes ---
declare -A mounted_folders

mount_str="${mounts[*]}"
PARAM_NAMES=()
QUOTE_KEYS=()
special_chars_re='[;&|()<>$`"'"'"'[:space:]]'
cmd="docker run --rm ${mount_str} repbioinfo/rnaseqstar_v2 /home/index_align.sh "
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