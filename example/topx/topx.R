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

usage_str <- paste0(paste0("\033[93m<workdir", RESET), ' ', paste0("\033[93m<data", RESET), ' ', paste0("\033[92m<matrixname", RESET), ' ', paste0("\033[92m<format", RESET), ' ', paste0("\033[92m<threshold", RESET), ' ', paste0("\033[92m<separator", RESET), ' ', paste0("\033[92m<logged", RESET), ' ', paste0("\033[92m<type", RESET))

args_raw <- commandArgs(trailingOnly = TRUE)

if (length(args_raw) != 8) {
  cat(WHITE, 'Usage: Rscript topx.R ', usage_str, RESET, '\n\n', sep = '')
  cat_col("Seleziona i geni con i valori piÃ¹ alti secondo una metrica scelta (espressione o varianza) e restituisce solo i top X dalla matrice di conteggi.", color = YELLOW)
  cat('\n')
  cat_col('Arguments:', color = WHITE)
  cat('\033[93mworkdir         [io]  percorso cartella di lavoro', RESET, '\n', sep = '')
  cat('\033[93mdata            [io]  percorso cartella contenente i dati e ricevente i risultati', RESET, '\n', sep = '')
  cat('\033[92mmatrixname            name del file di input senza estensione', RESET, '\n', sep = '')
  cat('\033[92mformat                formato del file di input', RESET, '\n', sep = '')
  cat('\033[92mthreshold             Soglia per selezionare i geni top (solitamente fra 10 e 2000 a seconda delle dimensioni del datase)', RESET, '\n', sep = '')
  cat('\033[92mseparator             Separatore del file (Separatore usato nel file Usare \\\",\\\" per CSV, \\\"\t\\\" per TSV)', RESET, '\n', sep = '')
  cat('\033[92mlogged                Indica se i valori della matrice di conteggi sono giÃ  logâ€‘trasformati (TRUE) oppure no (FALSE).', RESET, '\n', sep = '')
  cat('\033[92mtype                  Tipo di analisi da eseguire.', RESET, '\n', sep = '')
  quit(status = 1)
}

# Parse positional arguments
args <- list()
args$workdir <- args_raw[1]
args$data <- args_raw[2]
args$matrixname <- args_raw[3]
args$format <- args_raw[4]
args$threshold <- args_raw[5]
args$separator <- args_raw[6]
args$logged <- args_raw[7]
args$type <- args_raw[8]

# --- Input validation ---
errors <- character(0)

if (!dir.exists(args$workdir)) {
  errors <- c(errors, paste0('Directory not found: workdir = ', args$workdir))
}
if (!dir.exists(args$data)) {
  errors <- c(errors, paste0('Directory not found: data = ', args$data))
}
if (!args$format %in% c("csv", "txt")) {
  errors <- c(errors, paste0('Invalid value for format: ', args$format, '. Allowed: csv, txt'))
}
if (!args$separator %in% c(",", "\t")) {
  errors <- c(errors, paste0('Invalid value for separator: ', args$separator, '. Allowed: ,, \t'))
}
if (!args$logged %in% c("FALSE", "TRUE")) {
  errors <- c(errors, paste0('Invalid value for logged: ', args$logged, '. Allowed: FALSE, TRUE'))
}
if (!args$type %in% c("expression", "variance")) {
  errors <- c(errors, paste0('Invalid value for type: ', args$type, '. Allowed: expression, variance'))
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

mounts <- c(mounts, paste0('-v "', scratch_path, ':/workdir"'))
docker_vals$workdir <- '/workdir'

# data: read-write directory [io]
mounts <- c(mounts, paste0('-v "', normalizePath(args$data), ':/data"'))
docker_vals$data <- '/data'

# --- Bind files and service volumes ---
mounted_folders <- list()

docker_vals$matrixname <- args$matrixname
docker_vals$format <- args$format
docker_vals$threshold <- args$threshold
docker_vals$separator <- args$separator
docker_vals$logged <- args$logged
docker_vals$type <- args$type

# --- Assemble docker command ---
cmd <- 'docker run --rm repbioinfo/topxv2:1 Rscript /bin/top.R <matrixname> <format> <separator> <logged> <threshold> <type>'
mount_str <- paste(mounts, collapse = ' ')
cmd <- sub('docker run', paste('docker run', mount_str), cmd, fixed = TRUE)

replace_placeholder <- function(m) {
  key <- regmatches(m, regexpr('[^<>]+', m))
  val <- docker_vals[[key]]
  if (!is.null(val)) as.character(val) else m
}

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