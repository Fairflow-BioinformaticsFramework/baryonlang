# ----------------------------------------------------------------------------------------------------------------------
# Date      : 2026-06-05
# Project   : https://github.com/Fairflow-BioinformaticsFramework
# Authors   : 
# Version   : 1.1
# ----------------------------------------------------------------------------------------------------------------------

from baryonlang.functions.gen_nextflow import gen_nextflow
from baryonlang.functions.gen_streamflow import gen_streamflow
from baryonlang.functions.gen_galaxy import gen_galaxy
from baryonlang.functions.gen_python import gen_python
from baryonlang.functions.gen_r import gen_r
from baryonlang.functions.gen_bash import gen_bash
from baryonlang.functions.parse_and_validate import parse_and_validate
from baryonlang.functions.colors import WHITE, BLUE, YELLOW, ORANGE, RED, GREEN, GRAY, PINK, BROWN, RESET

import argparse
import os
import sys


VALID_LANGUAGES = ['nextflow', 'streamflow', 'galaxy', 'python', 'r', 'bash', 'all']

# --------------------------- Files produced by each language generator -------------------------------------------------
LANGUAGE_FILES = {
    'nextflow':   lambda tool_id: [f"{tool_id}.nf", "nextflow.config", f"{tool_id}_nextflow.txt"],
    'streamflow': lambda tool_id: [f"{tool_id}.cwl", f"{tool_id}-params.yml", f"{tool_id}.yml"],
    'galaxy':     lambda tool_id: [f"{tool_id}_targz.xml", f"{tool_id}.xml"],
    'python':     lambda tool_id: [f"{tool_id}.py"],
    'r':          lambda tool_id: [f"{tool_id}.R"],
    'bash':       lambda tool_id: [f"{tool_id}.sh"],
}

# -------------------------- get color for section ---------------------------------------------------------------------
def get_color_for_section(section_type):
    stype = section_type.lower()
    if stype == 'research':  return PINK
    if stype == 'file':      return ORANGE
    if stype == 'run':       return PINK
    if stype == 'directory': return ORANGE
    if stype == 'parameter': return BROWN
    return GRAY

# -------------------------- resolve bala file -------------------------------------------------------------------------
def resolve_bala_file(bala_arg):
    """Return a valid .bala filepath, prompting interactively if needed."""
    if bala_arg:
        filename = bala_arg if bala_arg.lower().endswith('.bala') else bala_arg + '.bala'
        if not os.path.exists(filename):
            print(f"\n{RED}Error: The specified file '{filename}' does not exist.{RESET}\n")
            sys.exit(1)
        return filename
    bala_files = [f for f in os.listdir('.') if f.lower().endswith('.bala')]
    if not bala_files:
        filename = input(f"{WHITE}Enter .bala file path/name: {RESET}").strip()
        filename = filename if filename.lower().endswith('.bala') else filename + '.bala'
        if not os.path.exists(filename):
            print(f"\n{RED}Error: The specified file '{filename}' does not exist.{RESET}\n")
            sys.exit(1)
        return filename

    print(f"\n{YELLOW}Available .bala files:{RESET}")
    for i, f in enumerate(bala_files, 1):
        print(f"  [{i}] {f}")
    print()
    user_input = input(
        f"{WHITE}Enter .bala file path/name or the corresponding number: {RESET}"
    ).strip()

    if user_input.isdigit():
        choice = int(user_input)
        if 1 <= choice <= len(bala_files):
            return bala_files[choice - 1]
        print(f"{RED}Error: Invalid selection number.{RESET}")
        sys.exit(1)

    filename = user_input if user_input.lower().endswith('.bala') else user_input + '.bala'
    return filename
# -------------------------- resolve language --------------------------------------------------------------------------
def resolve_language(lang_arg):
    """Return a validated language string, prompting interactively if needed."""
    if lang_arg:
        value = lang_arg.strip().lower()
        if value not in VALID_LANGUAGES:
            print(f"\n{RED}Error: Invalid language '{lang_arg}'. "
                  f"Valid options: {', '.join(VALID_LANGUAGES)}{RESET}\n")
            sys.exit(1)
        return value

    print(f"\n{YELLOW}Available language targets:{RESET}")
    for i, lang in enumerate(VALID_LANGUAGES, 1):
        print(f"  [{i}] {lang}")
    print()
    user_input = input(
        f"{WHITE}Enter language name or the corresponding number (default: all): {RESET}"
    ).strip()

    if not user_input:
        return 'all'
    if user_input.isdigit():
        choice = int(user_input)
        if 1 <= choice <= len(VALID_LANGUAGES):
            return VALID_LANGUAGES[choice - 1]
        print(f"{RED}Error: Invalid selection number.{RESET}")
        sys.exit(1)

    value = user_input.lower()
    if value not in VALID_LANGUAGES:
        print(f"\n{RED}Error: Invalid language '{user_input}'. "
              f"Valid options: {', '.join(VALID_LANGUAGES)}{RESET}\n")
        sys.exit(1)
    return value

# -------------------------- get candidate files for language ----------------------------------------------------------

def get_candidate_files(language, tool_id):
    if language == 'all':
        candidates = []
        for builder in LANGUAGE_FILES.values():
            candidates.extend(builder(tool_id))
        return candidates
    if language in LANGUAGE_FILES:
        return LANGUAGE_FILES[language](tool_id)
    return []

# -------------------------- display summary sections ------------------------------------------------------------------
def display_summary(sections):
    print(f"\n{GRAY}--- FILE CONTENT SUMMARY ---{RESET}")
    for sec in sections:
        color = get_color_for_section(sec['type']) 
        display_values = []
        content = sec['content']
        for key, val in content.items():
            display_values.append(val) 
        if display_values:
            print(f"{color}{', '.join(display_values)}{RESET}") 
    print(f"{GRAY}----------------------------{RESET}\n")

# ----------------------------------------------------------------------------------------------------------------------
# -------------------------- M A I N ----------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------
def main():
    if os.name == 'nt':
        os.system('color')
    parser = argparse.ArgumentParser(
        description="Baryon — Bioinformatics script generator from .bala files",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "bala_file",
        nargs="?",
        default=None,
        metavar="BALA_FILE",
        help="Path/name of the .bala file to process (optional, prompted if omitted)"
    )
    parser.add_argument(
        "--lang", "-l",
        default=None,
        metavar="LANGUAGE",
        help=(
            "Target language to generate.\n"
            f"Valid values: {', '.join(VALID_LANGUAGES)}\n"
            "(optional, prompted if omitted)"
        )
    )
    parser.add_argument(
        "--output", "-n",
        default=None,
        metavar="SCRIPT_NAME",
        help="Base name for the generated script(s) (optional, derived from .bala if omitted)"
    )
    parser.add_argument(
        "--overwrite", "-w",
        action="store_true",
        default=False,
        help="Overwrite existing output files without asking for confirmation"
    )
    parser.add_argument(
    "--generate_function", "-f",
    action="store_true",
    default=False,
    help="Generate R, Bash, and Python scripts as functions instead of standalone scripts"
    )

    args = parser.parse_args()
    bala_filename = resolve_bala_file(args.bala_file)
    if not bala_filename:
        sys.exit(1)
    language = resolve_language(args.lang)
    sections = parse_and_validate(bala_filename)
    if not sections:
        return
    display_summary(sections)
    research_sec = next((s['content'] for s in sections if s['type'] == 'research'), {})
    if args.output:
        script_name = args.output.strip()
    else:
        script_name = research_sec.get('name', 'baryon_tool').lower().replace(" ", "_")
    candidate_files = get_candidate_files(language, script_name)
    existing_files  = [f for f in candidate_files if os.path.exists(f)]
    if existing_files:
        if args.overwrite:
            print(f"\n{GREEN}[Overwrite Mode] Deleting existing target files automatically...{RESET}")
            for f in existing_files:
                try:
                    os.remove(f)
                except OSError as e:
                    print(f"{RED}Error deleting '{f}': {e}{RESET}")
        else:
            print(f"\n{YELLOW}Warning: The following target file(s) already exist:{RESET}")
            for f in existing_files:
                print(f"  - {f}")
            user_response = input(
                f"\n{WHITE}Do you want to delete them and regenerate? (yes/no): {RESET}"
            ).strip().lower()
            if user_response in ['yes', 'y']:
                print(f"{GREEN}Deleting existing files and proceeding with generation...{RESET}")
                for f in existing_files:
                    try:
                        os.remove(f)
                    except OSError as e:
                        print(f"{RED}Error deleting '{f}': {e}{RESET}")
            else:
                print(f"{ORANGE}Operation cancelled by user. Exiting without changes.{RESET}")
                sys.exit(0)
    if language in ('nextflow', 'all'):
        gen_nextflow(sections, script_name)
    if language in ('streamflow', 'all'):
        gen_streamflow(sections, script_name)
    if language in ('galaxy', 'all'):
        gen_galaxy(sections, script_name)
    if language in ('python', 'all'):
        gen_python(sections, script_name, as_function=args.generate_function)
    if language in ('r', 'all'):
        gen_r(sections, script_name, as_function=args.generate_function)
    if language in ('bash', 'all'):
        gen_bash(sections, script_name, as_function=args.generate_function)

if __name__ == "__main__":
    main()
