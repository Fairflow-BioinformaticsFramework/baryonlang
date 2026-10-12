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

usage_str <- paste0(paste0("\033[93m<workdir>", RESET), ' ', paste0("\033[93m<genome>", RESET), ' ', paste0("\033[93m<scratch>", RESET))

args_raw <- commandArgs(trailingOnly = TRUE)

if (length(args_raw) != 3) {
  cat(WHITE, 'Usage: Rscript index_align_bulk_rna_seq.R ', usage_str, RESET, '\n\n', sep = '')
  cat_col("Bulk RNA-Seq analysis. Measures average gene expression across a cell population.", color = YELLOW)
  cat('\n')
  cat_col('Arguments:', color = WHITE)
  cat('\033[93mworkdir         [io]  working directory path', RESET, '\n', sep = '')
  cat('\033[93mgenome          [io]  genome directory path', RESET, '\n', sep = '')
  cat('\033[93mscratch         [io]  scratch directory path(Data)', RESET, '\n', sep = '')
  quit(status = 1)
}

# Parse positional arguments
args <- list()
args$workdir <- args_raw[1]
args$genome <- args_raw[2]
args$scratch <- args_raw[3]

# --- Resolve 'default' keyword using each parameter's configured value= ---

# --- Input validation ---
errors <- character(0)

if (!dir.exists(args$workdir)) {
  errors <- c(errors, paste0('Directory not found: workdir = ', args$workdir))
}
if (args$genome != 'dummy' && !dir.exists(args$genome)) {
  errors <- c(errors, paste0('Directory not found: genome = ', args$genome))
}
if (!dir.exists(args$scratch)) {
  errors <- c(errors, paste0('Directory not found: scratch = ', args$scratch))
}

if (length(errors) > 0) {
  for (e in errors) cat(RED, 'ERROR: ', RESET, WHITE, e, RESET, '\n', sep = '')
  quit(status = 1)
}

# --- Scratch directory setup ---
n <- 1
repeat {
  if (dir.exists(file.path(normalizePath(args$workdir), paste0('scratch', n)))) {
    n <- n + 1
  } else {
    break
  }
}

scratch_path <- file.path(normalizePath(args$workdir), paste0('scratch', n))
dir.create(scratch_path, recursive = TRUE, showWarnings = FALSE)

# --- Build docker volume mounts ---
mounts      <- character(0)
docker_vals <- list()
service_idx <- 1

# --- Explicit quoting flags from .bala 'quote=' keyword ---
force_quote <- list(workdir = FALSE, genome = FALSE, scratch = FALSE)

mounts <- c(mounts, paste0('-v "', scratch_path, ':/workDir"'))
docker_vals$workdir <- '/workDir'

# genome is optional: mount only if a real path is passed, use 'dummy' placeholder otherwise
if (args$genome != 'dummy') {
  # genome: copy into workdir, then mount the copy (read-write directory [io])
  src_genome <- normalizePath(args$genome)
  dst_genome <- file.path(scratch_path, basename(src_genome))
  invisible(file.copy(src_genome, scratch_path, recursive = TRUE))
  mounts <- c(mounts, paste0('-v "', dst_genome, ':/genome"'))
  docker_vals$genome <- '/genome'
} else {
  docker_vals$genome <- 'dummy'
}

# scratch: read-write directory [io]
mounts <- c(mounts, paste0('-v "', normalizePath(args$scratch), ':/scratch"'))
docker_vals$scratch <- '/scratch'

# --- Bind files and service volumes ---
mounted_folders <- list()


# --- Assemble docker command ---
mount_str <- paste(mounts, collapse = ' ')
cmd <- paste('docker run --rm', mount_str, 'repbioinfo/rnaseqstar_v2 /home/index_align.sh ')
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