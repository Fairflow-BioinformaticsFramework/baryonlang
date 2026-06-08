args_raw <- commandArgs(trailingOnly = FALSE)

# Find --file= argument (path of this script) to locate itself
script_path <- sub("--file=", "", args_raw[grep("--file=", args_raw)])

# Extract trailing arguments (after --)
trailing <- commandArgs(trailingOnly = TRUE)

if (length(trailing) < 1) {
  cat("Usage: Rscript run_function.R <script.R> [arg1 arg2 ...]\n")
  quit(status = 1)
}

filepath <- trailing[1]
func_args <- if (length(trailing) > 1) as.list(trailing[-1]) else list()

if (!file.exists(filepath)) {
  cat("Error: File '", filepath, "' not found.\n", sep = "")
  quit(status = 1)
}

# Derive function name from filename (without extension)
func_name <- tools::file_path_sans_ext(basename(filepath))

# Source the file into a dedicated environment
env <- new.env(parent = globalenv())
tryCatch(
  source(filepath, local = env),
  error = function(e) {
    cat("Error sourcing '", filepath, "': ", conditionMessage(e), "\n", sep = "")
    quit(status = 1)
  }
)

func <- get(func_name, envir = env, inherits = FALSE)
if (!is.function(func)) {
  cat("Error: No function named '", func_name, "' found in '", filepath, "'\n", sep = "")
  quit(status = 1)
}

# Call the function and handle missing-argument errors
result <- tryCatch(
  do.call(func, func_args),
  error = function(e) {
    msg <- conditionMessage(e)
    if (!grepl("Missing required arguments", msg)) {
      cat("Error: ", msg, "\n", sep = "")
    }
    quit(status = 1)
  }
)

if (!is.null(result)) {
  quit(status = as.integer(result))
}
