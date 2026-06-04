import re

def parse_values(raw_values):
    """Parse comma-separated values respecting single/double quoted tokens."""
    tokens = []
    for match in re.finditer(r"'[^']*'|\"[^\"]*\"|[^,]+", raw_values):
        token = match.group(0).strip()
        if token:
            tokens.append(token.strip("'\""))
    return tokens
def gen_erre(sections):
    for item in sections:
        if isinstance(item, dict) and 'content' in item:
            content = item['content']
            if isinstance(content, dict) and 'description' in content:
                desc = content['description']
                if isinstance(desc, str):
                    desc = desc.replace("\\'", "'")
                    desc = desc.replace('"', '\\\\"')
                    content['description'] = desc
    res_sec   = next((s['content'] for s in sections if s['type'] == 'research'), {})
    run_sec   = next((s['content'] for s in sections if s['type'] == 'run'), {})
    exec_name = res_sec.get('name', 'baryon_tool').lower().replace(" ", "_")
    # -------------------------------------------------------------------------
    # Collect directories
    # -------------------------------------------------------------------------
    directories = {}   # name -> {mount, flag, description}
    for item in sections:
        if item['type'] == 'directory':
            c    = item['content']
            name = c.get('name', '')
            directories[name] = {
                'mount':       c.get('mount', f'/{name}').strip(),
                'flag':        c.get('flag', 'io').strip().lower(),
                'description': c.get('description', name),
            }
    has_workdir = 'workdir' in directories
    has_outdir  = 'outdir'  in directories

    # -------------------------------------------------------------------------
    # Collect files
    # -------------------------------------------------------------------------
    files = []
    for item in sections:
        if item['type'] == 'file':
            c = item['content']
            files.append({
                'name':        c.get('name', 'input_file'),
                'flag':        c.get('flag', 'cp').strip().lower(),
                'description': c.get('description', ''),
            })

    # -------------------------------------------------------------------------
    # Collect parameters and their allowed values
    # -------------------------------------------------------------------------
    parameters = []
    for item in sections:
        if item['type'] == 'parameter':
            c          = item['content']
            raw_values = c.get('values', '')
            parameters.append({
                'name':        c.get('name', 'param'),
                'description': c.get('description', ''),
                'values':      parse_values(raw_values),
            })

    # -------------------------------------------------------------------------
    # Build docker command template
    # -------------------------------------------------------------------------
    bala_cmd    = run_sec.get('command', 'docker run --rm').strip()
    bala_img    = run_sec.get('image', '').strip()
    bala_script = run_sec.get('script', '').strip()
    bala_usage  = run_sec.get('usage', '').strip()
    dynamic_items = []
    for item in sections:
        if item['type'] in ('directory', 'file', 'parameter') and 'name' in item['content']:
            dynamic_items.append(item)

    TYPE_COLORS = {
        'directory': '\\033[93m',        # yellow
        'file':      '\\033[38;5;208m',  # orange
        'parameter': '\\033[92m',        # green
    }
    DEFAULT_COLOR = '\\033[97m'

    # -------------------------------------------------------------------------
    # Start building the generated R script lines
    # -------------------------------------------------------------------------
    L = []  # lines

    def w(*lines):
        for line in lines:
            L.append(line)

    # --- Header / color constants ---
    w(
        "# ANSI color codes",
        "RED    <- '\\033[91m'",
        "WHITE  <- '\\033[97m'",
        "YELLOW <- '\\033[93m'",
        "ORANGE <- '\\033[38;5;208m'",
        "GREEN  <- '\\033[92m'",
        "RESET  <- '\\033[0m'",
        "",
        "cat_col <- function(..., color = WHITE) {",
        "  cat(color, ..., RESET, '\\n', sep = '')",
        "}",
        "",
    )

    # --- Build usage string ---
    usage_parts = []
    for item in dynamic_items:
        name  = item['content']['name']
        color = TYPE_COLORS.get(item['type'], DEFAULT_COLOR)
        usage_parts.append(f'paste0("{color}<{name}>", RESET)')

    usage_join = ", ' ', ".join(usage_parts)
    w(f"usage_str <- paste0({usage_join})")
    w("")

    # --- Expected argument count ---
    n_args = len(dynamic_items)
    research_desc = res_sec.get('description', '')

    w(
        "args_raw <- commandArgs(trailingOnly = TRUE)",
        "",
        f"if (length(args_raw) != {n_args}) {{",
        f"  cat(WHITE, 'Usage: Rscript {exec_name}.R ', usage_str, RESET, '\\n\\n', sep = '')",
    )
    if research_desc:
        w(f'  cat_col("{research_desc}", color = YELLOW)')
        w("  cat('\\n')")
    w("  cat_col('Arguments:', color = WHITE)")

    for item in dynamic_items:
        name  = item['content']['name']
        color = TYPE_COLORS.get(item['type'], DEFAULT_COLOR)
        desc  = item['content'].get('description', '')
        flag  = item['content'].get('flag', '')
        flag_str = f" [{flag}]" if flag else ""
        padded = name.ljust(15)
        w(f"  cat('{color}{padded}{flag_str.ljust(6)} {desc}', RESET, '\\n', sep = '')")

    w(
        "  quit(status = 1)",
        "}",
        "",
    )

    # --- Parse positional arguments ---
    w("# Parse positional arguments")
    w("args <- list()")
    for idx, item in enumerate(dynamic_items):
        name = item['content']['name']
        w(f"args${name} <- args_raw[{idx + 1}]")
    w("")

    # -------------------------------------------------------------------------
    # Validation block
    # -------------------------------------------------------------------------
    w(
        "# --- Input validation ---",
        "errors <- character(0)",
        "",
    )

    for item in dynamic_items:
        if item['type'] != 'directory':
            continue
        name = item['content']['name']
        w(
            f"if (!dir.exists(args${name})) {{",
            f"  errors <- c(errors, paste0('Directory not found: {name} = ', args${name}))",
            "}",
        )

    for item in dynamic_items:
        if item['type'] != 'file':
            continue
        name = item['content']['name']
        w(
            f"if (!file.exists(args${name})) {{",
            f"  errors <- c(errors, paste0('File not found: {name} = ', args${name}))",
            "}",
        )

    for p in parameters:
        if not p['values']:
            continue
        allowed_r       = 'c(' + ', '.join(f'"{v}"' for v in p['values']) + ')'
        name            = p['name']
        allowed_display = ', '.join(p['values'])
        w(
            f"if (!args${name} %in% {allowed_r}) {{",
            f"  errors <- c(errors, paste0('Invalid value for {name}: ', args${name}, '. Allowed: {allowed_display}'))",
            "}",
        )

    w(
        "",
        "if (length(errors) > 0) {",
        "  for (e in errors) cat(RED, 'ERROR: ', RESET, WHITE, e, RESET, '\\n', sep = '')",
        "  quit(status = 1)",
        "}",
        "",
    )

    # -------------------------------------------------------------------------
    # Scratch directory setup
    # -------------------------------------------------------------------------
    w(
        "# --- Scratch directory setup ---",
        "n <- 1",
        "repeat {",
    )

    conds = [f"dir.exists(file.path(normalizePath(args$workdir), paste0('scratch', n)))"]
    if has_outdir:
        conds.append("dir.exists(file.path(normalizePath(args$outdir), paste0('scratch', n)))")

    w(f"  if ({' || '.join(conds)}) {{")
    w("    n <- n + 1")
    w("  } else {")
    w("    break")
    w("  }")
    w("}", "")

    w(
        "scratch_path <- file.path(normalizePath(args$workdir), paste0('scratch', n))",
        "dir.create(scratch_path, recursive = TRUE, showWarnings = FALSE)",
    )
    if has_outdir:
        w(
            "scratch_out_path <- file.path(normalizePath(args$outdir), paste0('scratch', n))",
            "dir.create(scratch_out_path, recursive = TRUE, showWarnings = FALSE)",
        )
    w("")

    # -------------------------------------------------------------------------
    # Docker volume mounts construction
    # -------------------------------------------------------------------------
    w(
        "# --- Build docker volume mounts ---",
        "mounts      <- character(0)",
        "docker_vals <- list()",
        "service_idx <- 1",
        "",
    )

    if has_workdir:
        wdir_mount = directories['workdir']['mount']
        w(
            f"mounts <- c(mounts, paste0('-v \"', scratch_path, ':{wdir_mount}\"'))",
            f"docker_vals$workdir <- '{wdir_mount}'",
            "",
        )

    if has_outdir:
        odir_mount = directories['outdir']['mount']
        w(
            f"host_out_base <- normalizePath(args$outdir)",
            f"mounts <- c(mounts, paste0('-v \"', host_out_base, ':{odir_mount}\"'))",
            f"docker_vals$outdir <- paste0('{odir_mount}/scratch', n)",
            "",
        )

    for name, d in directories.items():
        if name in ('workdir', 'outdir'):
            continue
        mount = d['mount']
        flag  = d['flag']
        if flag == 'ro':
            w(
                f"# {name}: read-only directory",
                f"mounts <- c(mounts, paste0('-v \"', normalizePath(args${name}), ':{mount}:ro\"'))",
                f"docker_vals${name} <- '{mount}'",
                "",
            )
        else:
            w(
                f"# {name}: read-write directory [{flag}]",
                f"mounts <- c(mounts, paste0('-v \"', normalizePath(args${name}), ':{mount}\"'))",
                f"docker_vals${name} <- '{mount}'",
                "",
            )

    w(
        "# --- Bind files and service volumes ---",
        "mounted_folders <- list()",
        "",
    )

    for f in files:
        name = f['name']
        flag = f['flag']
        wdir_mount = directories.get('workdir', {}).get('mount', '/workdir')

        if flag == 'cp' or flag not in ('ro', 'nc'):
            w(
                f"src_{name} <- normalizePath(args${name})",
                f"file.copy(src_{name}, scratch_path)",
                f"docker_vals${name} <- paste0('{wdir_mount}/', basename(src_{name}))",
                "",
            )
        elif flag in ('ro', 'nc'):
            w(
                f"src_{name} <- normalizePath(args${name})",
                f"dir_{name} <- dirname(src_{name})",
                f"if (is.null(mounted_folders[[dir_{name}]])) {{",
                f"  m_point <- paste0('/service', service_idx)",
                f"  mounted_folders[[dir_{name}]] <- m_point",
                f"  mounts <- c(mounts, paste0('-v \"', dir_{name}, ':', m_point, ':ro\"'))",
                f"  service_idx <- service_idx + 1",
                f"}}",
                f"docker_vals${name} <- paste0(mounted_folders[[dir_{name}]], '/', basename(src_{name}))",
                "",
            )

    for p in parameters:
        name = p['name']
        w(f"docker_vals${name} <- args${name}")
    w("")

    # -------------------------------------------------------------------------
    # Assemble and run docker command
    # -------------------------------------------------------------------------
    full_template = f"{bala_img} {bala_script} {bala_usage}"
    w(
    "# --- Assemble docker command ---",
    "mount_str <- paste(mounts, collapse = ' ')",
    )

    if bala_cmd.split()[0].lower() == 'singularity':
        w(
            "mount_str <- gsub('-v \"', ' --bind ', mount_str, fixed = TRUE)",
            "mount_str <- gsub('\"', '', mount_str, fixed = TRUE)",
        )
    w(
        f"cmd <- paste('{bala_cmd}', mount_str, {repr(full_template)})",
        "placeholders <- regmatches(cmd, gregexpr('<[^>]+>', cmd))[[1]]",
        "for (ph in placeholders) {",
        "  key <- gsub('<|>', '', ph)",
        "  val <- docker_vals[[key]]",
        "  if (!is.null(val)) cmd <- gsub(ph, val, cmd, fixed = TRUE)",
        "}",
        "cat('\\n', YELLOW, 'Running:\\n', RESET, WHITE, cmd, RESET, '\\n\\n', sep = '')",
    )
    w(
        "log_path <- file.path(scratch_path, 'output_log.txt')",
        "cat(YELLOW, 'Log: ', RESET, WHITE, log_path, RESET, '\\n\\n', sep = '')",
        "",
        "con <- file(log_path, open = 'w')",
        "p   <- pipe(paste(cmd, '2>&1'), open = 'r')",
        "while (length(line <- readLines(p, n = 1, warn = FALSE)) > 0) {",
        "  cat(line, '\\n', sep = '')",
        "  writeLines(line, con)",
        "}",
        "ret <- close(p)",
        "close(con)",
        "",
        "if (ret == 0) {",
        "  cat('\\n', GREEN, 'Done. Log saved to: ', log_path, RESET, '\\n', sep = '')",
        "} else {",
        "  cat('\\n', RED, 'Docker exited with code ', ret, '. See log: ', log_path, RESET, '\\n', sep = '')",
        "}",
        "quit(status = ret)",
    )

    # -------------------------------------------------------------------------
    # Write output file
    # -------------------------------------------------------------------------
    output_filename = f"{exec_name}.R"
    with open(output_filename, "w", encoding="utf-8") as out_f:
        out_f.write("\n".join(L))
    print(f"\033[92mR script '{output_filename}' generated successfully.\033[0m")
