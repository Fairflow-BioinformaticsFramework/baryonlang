# Baryon

**Baryon** is a tool that enables bioinformatics workflows to run across different environments and operating systems without any manual conversion or adaptation. Researchers simply describe their pipeline once in a `.bala` configuration file, and Baryon takes care of generating ready-to-use scripts for multiple execution platforms.

> **Publication.** Baryon implements the `.bala`-based script generation described in: D'Onofrio A., Martelli E., Alessandri M., *et al.*, *FairFlow: A transparency-first framework for verifiable and reproducible bioinformatics*, Array 31 (2026) 101150, [doi:10.1016/j.array.2026.101150](https://doi.org/10.1016/j.array.2026.101150). Version **1.0** is the release associated with the publication (see [Install a specific version](#install-a-specific-version)).

---

## Overview

The core idea is straightforward: a researcher creates a `.bala` file containing all the information needed for a bioinformatics analysis — parameters, input files, directories, and execution logic — in a simple, structured format. Baryon reads this file, validates it, and automatically generates execution scripts for:

- **Python**
- **Galaxy**
- **R**
- **Bash**
- **Nextflow**
- **Streamflow**

Each generated script guides the user to customize paths and parameters, then runs the appropriate Docker container. Any researcher who wants to reproduce the analysis only needs to supply their own files and parameters.

> **Prerequisite:** The script to be executed, along with its full environment, must be packaged as a Docker image.

---

## The `.bala` File

The `.bala` file is the single configuration file that drives Baryon's script generation.

### General Rules

- Keywords are **case-insensitive** (can be written in uppercase, lowercase, or mixed).
- Values after `=` are **case-sensitive**, with these exceptions: the values of `name`, `flag`, `copy`, `optional` and `quote` are converted to lowercase by the parser, and so are the `<placeholders>` inside `command` and `usage`. For example `name = Genome` is stored as `genome` (and appears as `params.genome` in the generated Nextflow file), and `<Genome>` in `usage` still matches it. All other values (`mount`, `default`, `values`, `description`, `script`, `image`) keep the case you write, so `default` must match one of the listed `values` exactly, including uppercase and lowercase letters.
- Because names are lowercased, two sections whose names differ only by case (e.g. `Genome` and `genome`) are reported as duplicates. Use lowercase names in your `.bala` files to avoid surprises in the generated scripts.
- Lines starting with `#` are comments and are ignored.
- Each piece of information must be on a **single line**.
- Information is organized into **named sections** enclosed in square brackets.

---

### Sections

#### `[research]`
Contains metadata about the experiment or publication. Only one section is allowed.

| Keyword | Description |
|---|---|
| `name` | Name of the experiment; used to name the generated scripts. Letters, digits and underscores only. |
| `description` | Optional. Description propagated into generated files. |

#### `[file]`
Defines input files to pass to the application. Multiple sections are allowed.

| Keyword | Description |
|---|---|
| `name` | Unique name for the file (required). Letters, digits and underscores only. |
| `flag` | Optional. `ro` = protect the original file by not copying it (`copy` defaults to `false`) and, on Python, Bash and R, mounting its parent folder read-only. On Nextflow, Streamflow and Galaxy the file is handed over by the workflow engine, so `ro` only changes the `copy` default. Omit for the default (copy) behavior. |
| `copy` | `true`/`yes`/`false`/`no`. Defaults to `true` if omitted — the file is copied into `workdir`/scratch before processing. If `flag=ro` is set and `copy` is omitted, `copy` is inferred as `false`. Setting `flag=ro` together with `copy=true` is allowed but triggers a non-blocking warning (redundant: the copy already protects the original). |
| `optional` | `true`/`yes`/`false`/`no`. Defaults to `false`. See [Optional Files, Directories, and Parameters](#optional-files-directories-and-parameters). |
| `quote` | `true`/`yes`/`false`/`no`. Defaults to `false`. When `true`, the file's path is wrapped in double quotes when substituted into the generated command line — recommended for paths containing spaces. |
| `description` | Optional description propagated to generated scripts. |

> **Deprecated:** `flag=cp` and `flag=nc` are legacy values, automatically converted to `copy=yes` and `copy=no` respectively (with a non-blocking warning) — no need to update existing `.bala` files immediately, but new files should use `copy=` directly. `nc` never behaved differently from `ro` in any generator and has been removed as a distinct value.
>
> Setting `copy=false` alone (without `flag=ro`) mounts the original file directly, without the additional read-only protection that `flag=ro` provides.
> On Python, Bash and R each parent folder is mounted only once: if two `copy=false` files live in the same folder, the first one processed decides whether that mount is read-only.

#### `[directory]`
Defines directories to pass to the application. Multiple sections are allowed.

| Keyword | Description |
|---|---|
| `name` | Unique name (letters, digits and underscores only). `workdir` is **mandatory** — it is used for copied files and to write `output_log.txt` (not on Galaxy, where the log is the `output_log` dataset) |
| `mount` | **Required.** The path/name by which the directory will be mounted inside Docker. |
| `flag` | **Required.** `ro` = mounted read-only; `io`, `in`, `out` = mounted read-write. `in`, `out` and `io` only matter on Galaxy, where they decide whether the directory becomes an input (`in`, `io`, and also `ro`) and/or an archived output (`out`, `io`); on every other target they behave identically. `out` additionally forbids `copy=true`. |
| `copy` | `true`/`yes`/`false`/`no`. Defaults to `false` — the directory is mounted directly from its host path. If `true`, the directory is copied into `workdir`/scratch first, and, on Python/Bash/R, the copy is mounted in place of the original at the same `mount` path; on Nextflow/Streamflow the original stays mounted and the copy is used only when the directory is referenced as `<name>` in `usage=`. Not allowed on `workdir`/`outdir`, nor on a directory with `flag=out`. On Streamflow, this also requires filling in an `<name>_origin_name` parameter — see the [Platform Support Matrix](#platform-support-matrix-for-copy). |
| `optional` | `true`/`yes`/`false`/`no`. Defaults to `false`. Not allowed on `workdir`/`outdir`. See [Optional Files, Directories, and Parameters](#optional-files-directories-and-parameters). |
| `quote` | `true`/`yes`/`false`/`no`. Defaults to `false`. When `true`, the mounted path is wrapped in double quotes when substituted into the generated command line — recommended for paths containing spaces. |
| `description` | Optional description propagated to generated scripts. |

> A numbered `scratch` subdirectory is created inside `workdir` for each run to preserve logs and copied files across executions.
>
> If an `outdir` directory is defined, a numbered `output` subdirectory aligned with `workdir`'s counter is created inside it. **Do not use `outdir` for scripts that expect a specific mount path.**
>
> `workdir` and `outdir` cannot be read-only.

#### `[parameter]`
Defines parameters to pass to the application. Multiple sections are allowed.

| Keyword | Description |
|---|---|
| `name` | Unique name for the parameter (required). Letters, digits and underscores only. |
| `default` | Default value. The older `value=` spelling is still accepted and automatically converted, with a non-blocking warning. |
| `values` | Comma-separated list of accepted values (e.g. `values=x,y,z`). Use double quotes for values with spaces or special characters (e.g. `"my value"`). This is unrelated to the `quote=` keyword below, which controls quoting in the *generated command line*, not in the `.bala` file itself. |
| `optional` | `true`/`yes`/`false`/`no`. Defaults to `false`. See [Optional Files, Directories, and Parameters](#optional-files-directories-and-parameters). |
| `quote` | `true`/`yes`/`false`/`no`. Defaults to `false`. When `true`, the value is wrapped in double quotes when substituted into the generated command line — recommended for values containing spaces. |
| `description` | Optional description propagated to generated scripts. |

#### `[run]`
Defines how the Docker container is executed. Only one section is allowed.

| Keyword | Description |
|---|---|
| `command` | **Required.** The Docker run command and its flags (e.g. `docker run --rm`), or `singularity exec ...`. Flags and `<name>` placeholders written here are applied only by the Python, Bash and R generators; Nextflow, Streamflow and Galaxy ignore everything except the first word (used to detect Singularity). |
| `script` | **Required.** The script to execute inside the container. Prefix with interpreter if needed (e.g. `python3 /path/to/script.py`). |
| `image` | **Required.** The Docker image to use. |
| `usage` | Optional. Defines the order and flags of parameters. Use `<name>` as placeholders referencing section names. Constants can be placed directly. |

**Example `usage` with placeholders:**
```
usage = <param1> --param2 <param2> --parammulti <paramx> <paramy> constant_value
```

For output files in a specific location:
```
usage = <outdir>/output_file.txt
```
Define the corresponding directory section with `name=outdir` and set `mount` to the expected disk path.

---

### Copying Files and Directories (`copy=`)

By default, Baryon applies an asymmetric copying strategy to protect source data without introducing unnecessary performance overhead:

- **Files (`[file]`)**: `copy=true` (default). Files are copied into `workdir/scratch` before execution to prevent accidental modification of original inputs.
- **Directories (`[directory]`)**: `copy=false` (default). Directories are mounted directly from their host paths to avoid long copying times and disk saturation for large datasets (e.g., genomic indexes).

Set `copy=true` or `copy=false` explicitly in a section to override the default behavior.

> **Important Constraints:**
> - `copy=true` cannot be used on `workdir`, `outdir`, or any `[directory]` with `flag=out`.
> - If `flag=ro` is set on a `[file]`, `copy` defaults to `false` (on Python/Bash/R the parent directory is mounted read-only instead of copying).

#### Platform Support Matrix for `copy=`

Since execution engines handle data staging differently, the `copy` keyword is interpreted according to each generator's native capabilities:

| Target Language | Files (`[file]`) | Directories (`[directory]`) | Notes / Behavior |
|---|---|---|---|
| **Python / Bash / R** | ✅ Supported | ✅ Supported | Explicitly executes file/directory copies to `workdir/scratch` in generated code. |
| **Streamflow** | ✅ Supported | ✅ Supported | Files/directories with `copy=true` trigger an explicit `cp`/`cp -r` step into `workdir/scratch$n` in generated CWL (`<name>.cwl`); the `<name>` placeholder in `usage=` then resolves to the copied path. With `copy=false`, files/directories reference the original path. Directory volume mounts in `<name>.yml` are always manually filled in regardless of `copy`; for `copy=true` directories, the end user must additionally fill in an `<name>_origin_name` parameter in `<name>-params.yml` with the real folder name (name only, not a full path), since Baryon cannot infer it from the `.bala` file alone. As on Nextflow, the copy is only used when the directory is referenced as `<name>` in `usage=` (see the limitation below). |
| **Nextflow** | ✅ Supported | ✅ Supported | When `copy=true`, the generated process script explicitly `cp`/`cp -r`s the file or directory into `workdir/scratch$n` before execution. When `copy=false` (or the applicable default), files are staged via Nextflow's own `path` input mechanism and directories are bind-mounted directly from their host path.  Directories are always bind-mounted at their `mount` path, even with `copy=true`: the copy is only used when the directory is referenced as `<name>` in `usage=` (see the limitation below).|
| **Galaxy** | ❌ Ignored | ❌ Ignored | Handled natively by Galaxy dataset history and collection staging. |

> **Known limitation — directories accessed at a fixed, hardcoded path:** the notes above assume the tool script reaches a directory through the `<name>` placeholder in `usage=`. Some tools instead read and write a directory at a constant, hardcoded path built into the script itself (e.g. a tool that always operates on `/data`, with no corresponding `<name>` in `usage=`). For such directories:
> - **Python, Bash, R:** unaffected — the copy is bound to the very same mount point the script always uses, so it transparently reads and writes the copy regardless of whether a placeholder is used.
> - **Nextflow, Streamflow:** `copy=true` still creates a copy in `workdir/scratch`, but the script keeps reading from and writing to the **original** mounted directory — the copy is not fed back into the running container. Treat `copy=true` on such a directory as a traceability snapshot only, not as a guarantee that the original is protected from writes.
>
> To get real protection on Nextflow/Streamflow, either reference the directory through `<name>` in `usage=` (and make the script accept the path as an argument), or mount it read-only with `flag=ro`, so that the script fails visibly instead of silently modifying the original. For tools with hardcoded paths, Python/Bash/R are the safe choice.

### Optional Files, Directories, and Parameters

Any `[file]`, `[directory]`, or `[parameter]` can be marked `optional=true`. This tells Baryon that the corresponding argument in the generated script does not need to be checked, and — for files and directories — does not need to be mounted or copied at all.

To skip an optional item at runtime, pass the literal placeholder value `dummy` in its position. When `dummy` is received:
- **Files/directories**: no existence check is performed, no copy/mount happens, and the corresponding `<name>` placeholder in the `usage=` command is replaced with the literal text `dummy`.
- **Parameters**: no value check against `values=` is performed; `dummy` is passed through as-is.

If a real value is passed instead of `dummy` for an optional item, it is validated normally (existence check for files/directories, allowed-values check for parameters).

`optional=true` is not allowed on `workdir` or `outdir` (they are always required).

> **Platform note:** this convention currently applies only to the **Python, Bash, and R** generated scripts, which parse arguments positionally at runtime. **Galaxy**, **Nextflow**, and **Streamflow** do not have an equivalent runtime concept — see the "Known limitations" note under each platform below.

### Parameter Defaults with `default`

A `[parameter]` can declare a default value with `default=` (the older `value=` spelling still works but is automatically converted with a non-blocking warning). In the **Python, Bash, and R** generated scripts, passing the literal string `default` in place of that parameter's value causes the script to substitute it with the configured `default=` before any validation runs.

```ini
[parameter]
name = pca_type
description = Specifies the normalization and transformation method to apply to the expression matrix prior to Principal Component Analysis (PCA).
values = "Standard","deseq","deseqNormalized"
default = Standard
```

To use the configured default, pass the literal word `default` in the position where `pca_type` is expected — this is equivalent to passing `Standard` directly.

> **Platform note:** **Nextflow** and **Streamflow** read `default=` directly and write it into the generated parameter file (`.nf` / `-params.yml`), which the user edits or overrides directly — the `default` runtime keyword convention only applies to Python/Bash/R's CLI-argument model. **Galaxy** preselects `default=` in its dropdown, or pre-fills it in a free-text field when no `values=` is set — see the Galaxy section below.

### Validation Rules

Baryon performs the following checks on the `.bala` file before generating scripts:

- Lines starting with `#` and blank lines are ignored.
- `name` and `mount` values must be a single word (no spaces). In addition, `name` may contain only letters, digits and underscores (`A-Z`, `a-z`, `0-9`, `_`): hyphens, dots and other symbols are rejected.
- Sections `[research]` and `[run]` are **mandatory**, as is the `workdir` directory. `[research]` and `[run]` must each appear **exactly once**; duplicates are reported as an error.
- Every placeholder in `usage` (`<name>`) must have a corresponding section with a matching `name=`.
- `flag` for files accepts only `ro` (or omitted); for directories only `ro`, `in`, `out`, or `io`.
- `copy`, `optional`, and `quote` accept only `true`, `false`, `yes`, or `no`.
- `copy=true` is not allowed on a directory with `flag=out`, nor on `workdir`/`outdir`.
- `optional=true` is not allowed on `workdir`/`outdir`.
- `value=` is a deprecated alias for `default=` on `[parameter]`, automatically converted with a non-blocking warning. Specifying both `value=` and `default=` together on the same `[parameter]` is a hard error.
- `flag=cp` and `flag=nc` are deprecated aliases on `[file]`, automatically converted to `copy=yes` and `copy=no` respectively, with a non-blocking warning.
- If a `[parameter]` has both `default=` and `values=`, the default must be one of the listed `values`.
- Extra (unparsed) characters after a value are reported as an **error** (`Error: ... Ignored characters: ...`) and halt processing — not merely a warning.
- Duplicate `name` values are not allowed.
- Duplicate `mount` values across `[directory]` sections are not allowed.
- Missing `name` keywords are flagged as errors.
- All directories must have a `mount` and a `flag` keyword.
- Section `[run]` must contain `command`, `script` and `image`; only `usage` is optional.

---

## Writing a `.bala` File — Step-by-Step Guide

1. Find the Docker image name and set it in `image` under `[run]`.
2. Find the script entry point and set it in `script` under `[run]`. Prefix with the interpreter if necessary (e.g. `python3 /Algorithm/script.py`).
3. Always include a `workdir` directory. A `scratch` subdirectory will be created for each run.
4. If the script accepts an output folder, use `outdir` to keep numbered scratch folders aligned with `workdir`.
5. Add any additional directories; use an appropriate `flag` usually `flag=io`.
6. Build the `usage` line with the appropriate placeholders and define a `[file]`, `[directory]`, or `[parameter]` section for each.
7. For file sections, use `flag=ro` to protect the original file (on Python/Bash/R its folder is mounted read-only instead of copying; on Nextflow/Streamflow/Galaxy it only avoids the copy); otherwise the file is copied to `workdir`/scratch by default. For directory sections, set `copy=true` if you need the directory duplicated into scratch instead of mounted directly.  On Nextflow and Streamflow the copy is only used when the directory is referenced as `<name>` in `usage=` (see the limitation under the `copy=` matrix).
8. Mark any file, directory, or parameter that the user may skip as `optional=true`. Document in your usage instructions that `dummy` is the placeholder to use for skipped items.
9. Set `quote=true` on any file, directory, or parameter whose resolved value may contain spaces, to ensure it reaches the script as a single argument.

---

## Container

Baryon supports both **Docker** and **Singularity** as container environments.  
To use Singularity as a Docker‑compatible backend, simply modify the `run` section by setting:

- `command = singularity exec --writable-tmpfs`
- prefixing the image name with `docker://`

This allows Baryon to execute containers through Singularity while pulling images from Docker registries.

When a `.bala` uses Singularity as its Docker environment, **configuration files for Galaxy, Nextflow, and StreamFlow will not be generated**, as these platforms require native Docker‑compatible metadata.

---

## Sample Launch Command File

In addition to the target scripts, Baryon maintains a single shared file, `<name>_command.txt`, in the current directory. Each generator appends or updates its own block, delimited by a marker:

```text
# ------- <language> sample command ------- #

<sample command>
```

Running Baryon for different `--lang` targets (including repeated runs with `--lang all`) only touches the block matching the language just generated — blocks belonging to other languages are preserved as-is. This means `<name>_command.txt` accumulates ready-to-copy examples as you generate more targets over time.

**Python, R, Bash:** the block shows a positional invocation of the generated script:
- `[file]`/`[directory]` values are shown as placeholder paths (`/path/to/directory/<name>`, `/path/to/file/<name>`) to be replaced with real paths.
- `[parameter]` values with a configured `default=` are substituted directly with that default.
- `[parameter]` values without a default are shown as `<name>` placeholders to fill in.
- In standalone mode, values of `[file]`, `[directory]` and `[parameter]` sections with `quote=true` are wrapped in double quotes in the command line, matching the quoting Baryon applies at runtime. With `--generate_function` (Python, R) the values are always string literals, so no extra quoting is needed.

**Nextflow, Streamflow:** the block shows the full `docker run` command needed to launch the container that executes the generated configuration files (`.nf` / `.yml` + `.cwl`).

**Galaxy** does not produce a block in this file, since it has no command-line invocation.

> **Note:** `<name>_command.txt` is never deleted by `--overwrite` — it is always merged in place, one marker block at a time.

## Supported Platforms

### Streamflow

A container-based Workflow Management System designed for complex, distributed data analysis pipelines (such as bioinformatics ones).

**Generated files** (named after the `[research]` name):
- `<name>-params.yml` — all parameters, file paths, and (for `copy=true` directories) origin folder names (customize this)
- `<name>.yml` — directory mounts, with placeholder host paths to replace (customize this)
- `<name>.cwl` — CWL workflow definition (do not modify)

**Philosophy:**
- All parameters are written to `<name>-params.yml` with descriptions from `description` keywords; default values are set from `default` or the first entry in `values`.
- All files appear in `<name>-params.yml` as customizable paths.
- All directories are listed in `<name>.yml` as volume mounts, with the host path set to the placeholder `/path/to/directory/<name>` (the `[directory]` description is kept as a comment above each line). Replace every placeholder with the real host path before running.
- Files are copied to `workdir` before the script is called by default (`copy=true`); set `copy=false` (or `flag=ro`) to reference the original file's folder instead.

- `copy` on `[directory]` sections **does** control the generated CWL, mirroring `[file]` behavior: directories with `copy=true` (default `false`) get a `mkdir` + `cp -r` step into `workdir/scratch$n` in `<name>.cwl`; directories with `copy=false` reference the original mounted path from `<name>.yml` directly. Either way, the directory is always listed as a placeholder volume mount in `<name>.yml` to fill in by hand — `copy` only affects *where inside the container* the script reads from, not whether the mount itself needs manual editing.
- Baryon cannot know, at `.bala`-authoring time, what the real folder name will be when the end user later fills in the volume line in `<name>.yml` — that name is decided independently, after generation. So for every `copy=true` directory, Baryon also adds a matching `<name>_origin_name` string parameter to `<name>-params.yml` and `<name>.cwl`. Fill it in with the folder **name only** — the last segment of the host path on the corresponding `<name>.yml` volume line (e.g. `Genome` for `/data/project/Genome`), never a full path, otherwise the whole path hierarchy is recreated inside `workdir/scratch$n`: the copy created in `workdir/scratch$n` is named after this value, and the `<name>` placeholder in `usage=` then resolves to that named copy.
- `copy` on `[file]` sections controls the generated CWL the same way: files with `copy=yes` (the default) get a `cp` step into `workdir/scratch$n` in `<name>.cwl`; files with `copy=no` reference the original path directly.
- `optional` has no effect on validation or execution, but optional items are marked with an `optional,` prefix in the generated comments, as a visual reminder when editing the files manually.

**Prerequisites:** Docker and WSL installed; the Streamflow image from UniTO downloaded (note: the original image does not include Docker — use the local variant).

**Run command (Windows):**
```bash
docker run --rm -it \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "${PWD}:/workflow" \
  -w /workflow \
  streamflow-unito-local streamflow run <name>.yml
```

> **Note:** the sample command Baryon appends to `<name>_command.txt` for Streamflow uses the base image `alphaunito/streamflow` (the original UniTO image, **not** the local Docker-enabled variant shown above). Edit that line — or your local build's image name — before running, since the original image does not include Docker.

---

### Nextflow

A code-based Workflow Management System using a Groovy-derived DSL.

**Generated files:**
- `nextflow.config`
- `<name>.nf`

Configure parameters, files, and directories in the first section of the `.nf` file.

Each run creates a random subdirectory under `work/` (Nextflow's own task directory, containing the standard hidden `.command.*` files; since the script redirects all its output, `.command.out`/`.command.err` are empty). The logs worth reading are written inside the mounted `workdir`, in the numbered `scratchN` subdirectory: `output_log.txt` (stdout and stderr of the script run in the container) and `nextflow.log` (copy of the Nextflow log, added when the workflow completes).

`copy` is respected for both `[file]` and `[directory]` sections: when `copy=true`, the generated process script explicitly `cp`/`cp -r`s the file or directory into `workdir/scratch$n` before execution; when `copy=false` (or the applicable default), files are staged directly through Nextflow's own `path` input mechanism and directories are bind-mounted from their host path without copying.  The directory copy is named after the `basename` of the host path set in `params.<name>`, so no extra parameter is needed (unlike Streamflow). Unlike Python/Bash/R, the original directory stays bind-mounted at its `mount` path even with `copy=true`.

**Known limitations:** `optional` is ignored by the Nextflow generator, for both `[file]` and `[directory]` sections — items marked `optional=true` receive an `optional,` prefix in the generated parameter comments, but the corresponding parameter is still always required in the `.nf` file.  Also note that `copy=true` on a directory does not redirect scripts that read it at a hardcoded path — see the limitation under the [Platform Support Matrix](#platform-support-matrix-for-copy).

**Run command (Windows `.bat` example):**
```bat
set MY_PATH=/c/my_project/nextflow/my_analysis

docker run -it --rm ^
  -v /var/run/docker.sock:/var/run/docker.sock ^
  -v %MY_PATH%:%MY_PATH% ^
  -w %MY_PATH% ^
  -e DOCKER_API_VERSION=1.44 ^
  nextflow/nextflow:26.04.6 nextflow run my_analysis.nf

pause
```

---

### Galaxy

When input directories are present, Baryon generates **two XML variants**: one using Galaxy collections, one using `.tar.gz` archives. Output directories are always `.tar.gz` due to collection limitations.
**Known limitations:** `copy` is ignored by the Galaxy generator — Galaxy already isolates job inputs through its own dataset/collection staging, which makes `copy` redundant. `optional` is only partially supported: files, input directories (collections/tar archives), and parameters marked `optional=true` are rendered with Galaxy's native `optional="true"` attribute on the corresponding `<param>`, but the generated `<command>` template does not yet wrap their usage in Cheetah `#if`/`#end if` conditionals — so leaving an optional input unset may still break the command line at runtime. Directories with `flag=ro` are also exposed as inputs (collection or tar.gz), since Galaxy has no host mount to read them from. `workdir` is ignored on Galaxy: its mount is not created, so do not reference `<workdir>` in `usage`; the job log is returned as the `output_log` dataset.

**Parameter rendering:** a `[parameter]` with `values=` becomes a Galaxy dropdown (`<param type="select">`) listing every allowed value, with `default=` (if set and present among `values`) preselected. A `[parameter]` with only `default=` (no `values=`) becomes a free-text field (`<param type="text">`) pre-filled with that default. A `[parameter]` with neither `values=` nor `default=` becomes an empty free-text field (`<param type="text">`), required unless `optional=true`.

**Creating a collection from a directory:**
1. Upload all files from the directory.
2. Enable the selection checkbox and select all files.
3. Choose **Advanced build list** from the dropdown.
4. Select **flat list** and **disable** the option to strip file extensions.
5. Name the collection after the source directory.

**Creating a `.tar.gz` from a directory (Windows):**
```bash
tar -czf genome.tar.gz -C genome .
```
When uploading, specify the type as `tar.gz` instead of auto-detect.

---

## Test Data and Examples

The `test/` folder contains sample `.bala` files, the scripts generated from them, ready-to-run launchers and input data. See [`test/README.md`](test/README.md) for the description of each workflow and step-by-step instructions to reproduce the tests.

---

## Running Baryon

Baryon is launched from the command line. All arguments are optional: if omitted,
Baryon will prompt interactively for any missing information.

```bash
python baryon.py [BALA_FILE] [--lang LANGUAGE] [--output SCRIPT_NAME] [--overwrite] [--generate_function]
```

### Arguments

| Argument | Short | Description |
|---|---|---|
| `BALA_FILE` | | Path or name of the `.bala` file to process. Extension `.bala` can be omitted. If not provided, Baryon lists all `.bala` files in the current directory and lets you choose. |
| `--lang` | `-l` | Target language to generate. Valid values: `nextflow`, `streamflow`, `galaxy`, `python`, `r`, `bash`, `all`. If not provided, Baryon shows a numbered list to choose from (default: `all`). |
| `--output` | `-n` | Base name for the generated script files. If not provided, the name is derived from the `name` field in the `[research]` section of the `.bala` file. |
| `--overwrite` | `-w` | Overwrite existing output files without asking for confirmation. If not set, Baryon will warn and prompt before deleting any existing files. |
| `--generate_function` | `-f` | Generate Python, R, and Bash scripts as self-contained functions instead of standalone scripts. Has no effect on `nextflow`, `streamflow`, or `galaxy` targets. |

### Examples

```bash
# Fully interactive — Baryon will prompt for file and language
python baryon.py

# Specify the .bala file; choose language interactively
python baryon.py htgts_full

# Generate only the R script
python baryon.py htgts_full --lang r

# Generate all scripts with a custom output base name
python baryon.py htgts_full --lang all --output my_analysis

# Regenerate without confirmation prompts
python baryon.py htgts_full --lang python --overwrite

# Generate Python and R scripts as functions instead of standalone scripts
python baryon.py htgts_full --lang python --generate_function
python baryon.py htgts_full --lang all -f
```

> **Note:** The `--overwrite` flag only checks and removes files relevant to the selected language.
> For example, `--lang python` will only look for an existing `<name>.py` file,
> while `--lang all` checks all possible output files.

> **Note:** The `--generate_function` flag applies only to `python`, `r`, and `bash` targets.
> When used with `--lang all`, `nextflow`, `streamflow`, and `galaxy` scripts are generated
> normally as standalone workflows.

---

## Installation

Baryon can be installed as a regular Python package, which makes the `baryon` command available system-wide (no need to call `python baryon.py` from inside the repo).

### Requirements

- Python ≥ 3.9
- `pip`

### Install from source (recommended for now)

Clone the repository and install it in editable mode from the **repository root** (the folder containing `pyproject.toml`):

```bash
git clone https://github.com/Fairflow-BioinformaticsFramework/Baryonlang.git
cd Baryonlang
pip install -e .
```

Editable mode (`-e`) means any change you make to the source code is immediately reflected without reinstalling — useful for development.

### Install directly from GitHub

If you just want to use Baryon without cloning the repo manually:

```bash
pip install git+https://github.com/Fairflow-BioinformaticsFramework/Baryonlang.git
```

### Install a specific version

> **Version 1.0** (Git tag `v1.0.0`) is the release associated with the publication ([doi:10.1016/j.array.2026.101150](https://doi.org/10.1016/j.array.2026.101150)). To reproduce the published results, install exactly this version:

```bash
pip install "git+https://github.com/Fairflow-BioinformaticsFramework/Baryonlang.git@v1.0.0"
```

> **Version 1.1** 

```bash
pip install "git+https://github.com/Fairflow-BioinformaticsFramework/Baryonlang.git@main"
```

### Verify the installation

```bash
baryon --help
```

If the command is found and the help message is printed, the installation was successful. You can now run `baryon` from **any directory**, exactly as you would with `python baryon.py`:

```bash
baryon htgts_full --lang python
```

### Uninstall

```bash
pip uninstall baryonlang
```

## Citation

If you use Baryon, please cite:

```bibtex
@article{DONOFRIO2026101150,
title = {FairFlow: A transparency-first framework for verifiable and reproducible bioinformatics},
journal = {Array},
volume = {31},
pages = {101150},
year = {2026},
issn = {2590-0056},
doi = {https://doi.org/10.1016/j.array.2026.101150},
url = {https://www.sciencedirect.com/science/article/pii/S259000562600473X},
author = {Agata D'Onofrio and Eliseo Martelli and Maurizio Alessandri and Sebastian Bucatariu and Sandro Gepiro Contaldo and Maria Luisa Ratto and Jianli Tao and Beatrice Nuvolari and Isabella Castellano and Andrea Loiacono and Sara Bianchi and Maddalena Arigoni and Alessandro Bertero and Elisa Balmas and Roberto Chiarle and Luca Alessandri},
keywords = {Computational reproducibility, Bioinformatics workflows, Containerization, Docker, Workflow managers, Version control, FAIR data},
abstract = {Bioinformatics analyses depend on external software that itself relies on further programs, or dependencies, each with its own release cycle. Because tools are updated to fix bugs and add features, identical code can produce different results depending on which versions are installed, and incomplete documentation of dependencies and versions therefore undermines reproducibility. Containerization packages software with all its dependencies, but demands technical expertise and lacks a standard operating procedure. Existing workflow managers and container tools have improved reproducibility, yet each works differently and requires specialized knowledge, forcing developers to rebuild equivalent solutions from scratch. Here we present FairFlow, a framework that makes rigorous, reproducible analysis accessible without specialized technical knowledge. Developers describe a pipeline once in a declarative, INI-style specification file written in Baryon, and FairFlow automatically generates ready-to-run interfaces for R, Python, Bash, Galaxy, Nextflow and StreamFlow, each executing the analysis inside a version-locked container. The generated interfaces are self-contained: end users need only Docker and their preferred language. As a proof of concept we reanalyzed a published study in two ways: following the original protocol, which does not account for dependency installation, and with a FairFlow-based script. The first yielded only ∼21% concordance with the original findings, traced to an unspecified sequence-alignment tool version, whereas the FairFlow-based reanalysis achieved 98.8–100% concordance across operating systems and reduced setup from months of troubleshooting to a single Docker installation.}
}
```

---

## Reporting Issues & Feature Requests

Found a bug, an inconsistency in the documentation, or have an idea for a new feature? Please open an issue on GitHub:

👉 [https://github.com/Fairflow-BioinformaticsFramework/Baryonlang/issues](https://github.com/Fairflow-BioinformaticsFramework/Baryonlang/issues)

When reporting a bug, please include:
- The `.bala` file (or a minimal excerpt) that triggers the issue.
- The exact command you ran (e.g. `baryon htgts_full --lang streamflow`).
- The full error output.
- The target language(s) involved (Python, Bash, R, Nextflow, Streamflow, Galaxy).

Feature requests and enhancement ideas are also welcome — check [`future.md`](future.md) first to see if something similar is already planned.