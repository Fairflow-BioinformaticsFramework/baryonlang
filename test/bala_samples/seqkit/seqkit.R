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

usage_str <- paste0(paste0("\033[38;5;208m<filein>", RESET), ' ', paste0("\033[93m<workdir>", RESET), ' ', paste0("\033[93m<outdir>", RESET), ' ', paste0("\033[92m<fileout>", RESET), ' ', paste0("\033[92m<command>", RESET), ' ', paste0("\033[92m<length>", RESET))

args_raw <- commandArgs(trailingOnly = TRUE)

if (length(args_raw) != 6) {
  cat(WHITE, 'Usage: Rscript seqkit.R ', usage_str, RESET, '\n\n', sep = '')
  cat_col("A comprehensive toolkit for FASTA/FASTQ file manipulation, filtering, and statistics.", color = YELLOW)
  cat('\n')
  cat_col('Arguments:', color = WHITE)
  cat('\033[38;5;208mfilein          [copy=yes] file to analize', RESET, '\n', sep = '')
  cat('\033[93mworkdir         [io]  working directory', RESET, '\n', sep = '')
  cat('\033[93moutdir          [out] output directory', RESET, '\n', sep = '')
  cat('\033[92mfileout               output file name', RESET, '\n', sep = '')
  cat('\033[92mcommand               SeqKit subcommands to run', RESET, '\n', sep = '')
  cat('\033[92mlength                maximum sequence length to keep (-M option)', RESET, '\n', sep = '')
  quit(status = 1)
}

# Parse positional arguments
args <- list()
args$filein <- args_raw[1]
args$workdir <- args_raw[2]
args$outdir <- args_raw[3]
args$fileout <- args_raw[4]
args$command <- args_raw[5]
args$length <- args_raw[6]

# --- Resolve 'default' keyword using each parameter's configured value= ---
if (args$command == 'default') {
  args$command <- 'stats'
}

# --- Input validation ---
errors <- character(0)

if (!dir.exists(args$workdir)) {
  errors <- c(errors, paste0('Directory not found: workdir = ', args$workdir))
}
if (!dir.exists(args$outdir)) {
  errors <- c(errors, paste0('Directory not found: outdir = ', args$outdir))
}
if (!file.exists(args$filein)) {
  errors <- c(errors, paste0('File not found: filein = ', args$filein))
}
if (!(args$command %in% c("seq", "stats"))) {
  errors <- c(errors, paste0('Invalid value for command: ', args$command, '. Allowed: seq, stats'))
}

if (length(errors) > 0) {
  for (e in errors) cat(RED, 'ERROR: ', RESET, WHITE, e, RESET, '\n', sep = '')
  quit(status = 1)
}

# --- Scratch directory setup ---
n <- 1
repeat {
  if (dir.exists(file.path(normalizePath(args$workdir), paste0('scratch', n))) || dir.exists(file.path(normalizePath(args$outdir), paste0('output', n)))) {
    n <- n + 1
  } else {
    break
  }
}

scratch_path <- file.path(normalizePath(args$workdir), paste0('scratch', n))
dir.create(scratch_path, recursive = TRUE, showWarnings = FALSE)
scratch_out_path <- file.path(normalizePath(args$outdir), paste0('output', n))
dir.create(scratch_out_path, recursive = TRUE, showWarnings = FALSE)

# --- Build docker volume mounts ---
mounts      <- character(0)
docker_vals <- list()
service_idx <- 1

# --- Explicit quoting flags from .bala 'quote=' keyword ---
force_quote <- list(filein = FALSE, workdir = FALSE, outdir = FALSE, fileout = FALSE, command = FALSE, length = FALSE)

mounts <- c(mounts, paste0('-v "', scratch_path, ':/workDir"'))
docker_vals$workdir <- '/workDir'

mounts <- c(mounts, paste0('-v "', scratch_out_path, ':/outDir"'))
docker_vals$outdir <- '/outDir'

# --- Bind files and service volumes ---
mounted_folders <- list()

src_filein <- normalizePath(args$filein)
invisible(file.copy(src_filein, scratch_path))
docker_vals$filein <- paste0('/workDir/', basename(src_filein))

docker_vals$fileout <- args$fileout
docker_vals$command <- args$command
docker_vals$length <- args$length

# --- Assemble docker command ---
mount_str <- paste(mounts, collapse = ' ')
mount_str <- gsub('-v "', ' --bind ', mount_str, fixed = TRUE)
mount_str <- gsub('"', '', mount_str, fixed = TRUE)
cmd <- paste('singularity exec --writable-tmpfs', mount_str, 'docker://quay.io/biocontainers/seqkit:2.8.1--h9ee0642_0 seqkit <command> -N <length> <filein> -o <outdir>/<fileout>')
placeholders <- regmatches(cmd, gregexpr('<[^>]+>', cmd))[[1]]
for (ph in placeholders) {
  key <- gsub('<|>', '', ph)
  val <- docker_vals[[key]]
  if (!is.null(val)) {
    needs_quote <- val != 'dummy' && (isTRUE(force_quote[[key]]) || grepl('[;&|()<>$`"\'\\s]', val, perl = TRUE))
    if (needs_quote) val <- paste0('"', gsub('"', '\\"', val, fixed = TRUE), '"')
    cmd <- gsub(ph, val, cmd, fixed = TRUE)
  }
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