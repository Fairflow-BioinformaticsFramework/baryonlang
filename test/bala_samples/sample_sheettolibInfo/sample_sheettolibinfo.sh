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
    echo -e "${YELLOW}Converts experiment metadata from an Excel spreadsheet into a KEY=VALUE format readable by downstream HTGTS Bash pipeline scripts.${RESET}\n"
    echo -e "${WHITE}Arguments:${RESET}"
    echo -e "${YELLOW}workdir        ${RESET} [io]  working directory path"
    echo -e "${YELLOW}outdir         ${RESET} [out] output directory path"
    echo -e "${ORANGE}xmlfile        ${RESET} [copy=yes] name of the xml file"
    echo -e "${GREEN}configtype     ${RESET}       cell type"
    exit 1
fi

# Parse positional arguments
workdir="${1}"
outdir="${2}"
xmlfile="${3}"
configtype="${4}"

# --- Resolve 'default' keyword using each parameter's configured value= ---
if [ "${configtype}" = "default" ]; then
    configtype="HTGTS_mouse"
fi

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
if ! echo "${configtype}" | grep -qE "^(HTGTS_human|HTGTS_mouse|CELTICSseq|polyA)$"; then
    errors+=("Invalid value for configtype: ${configtype}. Allowed: ['HTGTS_human', 'HTGTS_mouse', 'CELTICSseq', 'polyA']")
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

mounts+=("-v \"${scratch_path}:/workingdir\"")
docker_vals["workdir"]="/workingdir"

mounts+=("-v \"${scratch_out_path}:/outDir\"")
docker_vals["outdir"]="/outDir"

# --- Bind files and service volumes ---
declare -A mounted_folders
_src_xmlfile="$(realpath "${xmlfile}")"
cp "${_src_xmlfile}" "${scratch_path}/"
docker_vals["xmlfile"]="/workingdir/$(basename "${_src_xmlfile}")"

docker_vals["configtype"]="${configtype}"

mount_str="${mounts[*]}"
PARAM_NAMES=("configtype")
QUOTE_KEYS=()
special_chars_re='[;&|()<>$`"'"'"'[:space:]]'
cmd="docker run --rm -v <workdir>:/work -v <outdir>:/Out ${mount_str} repbioinfo/htgts_pipeline_lts_v16:latest python3 /Algorithm/sample_sheetTolibInfo.py <xmlfile> <outdir>/fof.txt <outdir>/rof.txt <configtype>"
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