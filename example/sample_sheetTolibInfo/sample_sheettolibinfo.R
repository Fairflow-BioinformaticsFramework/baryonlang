# ANSI color codes
RED    <- '\033[91m'
WHITE  <- '\033[97m'
YELLOW <- '\033[93m'
ORANGE <- '\033[38;5;208m'
GREEN  <- '\033[92m'
RESET  <- '\033[0m'

cat_col <- function(..., color = WHITE) {
  cat(color, ..., RESET, '\n', sep = '')
}

usage_str <- paste0(paste0("\033[93m<workdir>", RESET), ' ', paste0("\033[93m<outdir>", RESET), ' ', paste0("\033[38;5;208m<xmlfile>", RESET), ' ', paste0("\033[92m<configtype>", RESET))

args_raw <- commandArgs(trailingOnly = TRUE)

if (length(args_raw) != 4) {
  cat(WHITE, 'Usage: Rscript sample_sheettolibinfo.R ', usage_str, RESET, '\n\n', sep = '')
  cat_col("Converts experiment metadata from an Excel spreadsheet into a KEY=VALUE format readable by downstream HTGTS Bash pipeline scripts.", color = YELLOW)
  cat('\n')
  cat_col('Arguments:', color = WHITE)
  cat('\033[93mworkdir         [io]  working directory path', RESET, '\n', sep = '')
  cat('\033[93moutdir          [out] output directory path', RESET, '\n', sep = '')
  cat('\033[38;5;208mxmlfile         [nc]  name of the xml file', RESET, '\n', sep = '')
  cat('\033[92mconfigtype            cell type', RESET, '\n', sep = '')
  quit(status = 1)
}

# Parse positional arguments
args <- list()
args$workdir <- args_raw[1]
args$outdir <- args_raw[2]
args$xmlfile <- args_raw[3]
args$configtype <- args_raw[4]

# --- Input validation ---
errors <- character(0)

if (!dir.exists(args$workdir)) {
  errors <- c(errors, paste0('Directory not found: workdir = ', args$workdir))
}
if (!dir.exists(args$outdir)) {
  errors <- c(errors, paste0('Directory not found: outdir = ', args$outdir))
}
if (!file.exists(args$xmlfile)) {
  errors <- c(errors, paste0('File not found: xmlfile = ', args$xmlfile))
}
if (!args$configtype %in% c("HTGTS_mouse", "HTGTS_human", "CELTICSseq", "polyA")) {
  errors <- c(errors, paste0('Invalid value for configtype: ', args$configtype, '. Allowed: HTGTS_mouse, HTGTS_human, CELTICSseq, polyA'))
}

if (length(errors) > 0) {
  for (e in errors) cat(RED, 'ERROR: ', RESET, WHITE, e, RESET, '\n', sep = '')
  quit(status = 1)
}

# --- Scratch directory setup ---
n <- 1
repeat {
  if (dir.exists(file.path(normalizePath(args$workdir), paste0('scratch', n))) || dir.exists(file.path(normalizePath(args$outdir), paste0('scratch', n)))) {
    n <- n + 1
  } else {
    break
  }
}

scratch_path <- file.path(normalizePath(args$workdir), paste0('scratch', n))
dir.create(scratch_path, recursive = TRUE, showWarnings = FALSE)
scratch_out_path <- file.path(normalizePath(args$outdir), paste0('scratch', n))
dir.create(scratch_out_path, recursive = TRUE, showWarnings = FALSE)

# --- Build docker volume mounts ---
mounts      <- character(0)
docker_vals <- list()
service_idx <- 1

mounts <- c(mounts, paste0('-v "', scratch_path, ':/workDir"'))
docker_vals$workdir <- '/workDir'

host_out_base <- normalizePath(args$outdir)
mounts <- c(mounts, paste0('-v "', host_out_base, ':/outDir"'))
docker_vals$outdir <- paste0('/outDir/scratch', n)

# --- Bind files and service volumes ---
mounted_folders <- list()

src_xmlfile <- normalizePath(args$xmlfile)
dir_xmlfile <- dirname(src_xmlfile)
if (is.null(mounted_folders[[dir_xmlfile]])) {
  m_point <- paste0('/service', service_idx)
  mounted_folders[[dir_xmlfile]] <- m_point
  mounts <- c(mounts, paste0('-v "', dir_xmlfile, ':', m_point, ':ro"'))
  service_idx <- service_idx + 1
}
docker_vals$xmlfile <- paste0(mounted_folders[[dir_xmlfile]], '/', basename(src_xmlfile))

docker_vals$configtype <- args$configtype

# --- Assemble docker command ---
mount_str <- paste(mounts, collapse = ' ')
cmd <- paste('docker run --rm -v <workdir>:/work -v <outdir>:/Out', mount_str, 'repbioinfo/htgts_pipeline_lts_v16:latest python3 /Algorithm/sample_sheetTolibInfo.py <xmlfile> <outdir>/fof.txt <outdir>/rof.txt <configtype>')
placeholders <- regmatches(cmd, gregexpr('<[^>]+>', cmd))[[1]]
for (ph in placeholders) {
  key <- gsub('<|>', '', ph)
  val <- docker_vals[[key]]
  if (!is.null(val)) cmd <- gsub(ph, val, cmd, fixed = TRUE)
}
cat('\n', YELLOW, 'Running:\n', RESET, WHITE, cmd, RESET, '\n\n', sep = '')
log_path <- file.path(scratch_path, 'output_log.txt')
cat(YELLOW, 'Log: ', RESET, WHITE, log_path, RESET, '\n\n', sep = '')

con <- file(log_path, open = 'w')
p   <- pipe(paste(cmd, '2>&1'), open = 'r')
while (length(line <- readLines(p, n = 1, warn = FALSE)) > 0) {
  cat(line, '\n', sep = '')
  writeLines(line, con)
}
ret <- close(p)
close(con)

if (ret == 0) {
  cat('\n', GREEN, 'Done. Log saved to: ', log_path, RESET, '\n', sep = '')
} else {
  cat('\n', RED, 'Docker exited with code ', ret, '. See log: ', log_path, RESET, '\n', sep = '')
}
quit(status = ret)