# Future Developments for Baryon

This document outlines planned implementations and enhancements for the Baryon DSL and framework.

## Planned for v1.2

### 1. Script-Generated Configuration Files for Galaxy, Streamflow, and Nextflow

* **Description:** For Galaxy, Streamflow, and Nextflow, replace the current approach of emitting configuration files that require manual adjustment with a generated script — consistent with the other supported languages — that produces those configuration files already filled in and validated.
* **Objective:** Remove the manual editing step currently required after generation, so that Galaxy, Streamflow, and Nextflow outputs are immediately runnable, in line with the other generated targets.

### 2. Value Validation Controls (Pattern/Range)

* **Description:** Add validation controls on parameter values, such as pattern/format checks (e.g. `picture`-style masks) and numeric range checks.
* **Objective:** Catch invalid parameter values at generation or runtime, before they reach the underlying script.

---

## Implemented in v1.1

> **Deprecation note:** on `[file]` sections, the legacy `flag=cp` and `flag=nc` values are now deprecated in favor of `copy=`. They are automatically converted to `copy=yes` and `copy=no` respectively (with a non-blocking warning) for backward compatibility; new `.bala` files should use `copy=` directly.

### 1. Directory Support for Copy Operations (Tracking via Workdir/Scratch)

* **Description:** Extended the existing file-based tracking and caching mechanism to support entire directories.
* **Details:** Added a `copy` keyword to `[directory]` sections, extending the tracking mechanism already available for `[file]` — but with an asymmetric default (`copy=false` for directories vs. `copy=true` for files), since directories can be arbitrarily large and unconditional copying would introduce unacceptable overhead. When set to `true`, the target directory is fully copied into the `workdir`/designated `scratch` space for each execution, under a subfolder matching the origin folder's real name, instead of being mounted directly from its host path. On Python, Bash and R the copy is mounted in place of the original; on Nextflow and Streamflow the original stays mounted and the copy is only used when the directory is referenced as `<name>` in `usage=`.
* **Platform support:** the origin folder's real name is recovered automatically at runtime in **Python**, **Bash**, **R**, and **Nextflow**. On **Streamflow**, Baryon cannot recover it automatically — directories are static Docker volumes, invisible to the container's own filesystem view — so an additional `<name>_origin_name` string parameter is generated in `<name>-params.yml` for the end user to fill in by hand. On **Galaxy**, `copy` is not supported for directories at all.
* **Objective:** Ensure that directory contents leave a distinct, traceable provenance trail for every pipeline execution, mirroring — where each target's architecture allows it — the behavior currently available for individual files.

### 2. Optional Parameters, Files, and Directories (Usage and Conditional Execution)

* **Description:** The `optional` keyword is a parameter directive used within the `[file]`, `[directory]`, and `[parameter]` sections of a `.bala` configuration file. It specifies whether a particular input file, folder, or execution parameter is strictly required to execute the pipeline. By default, it assumes a boolean value of `false` (`optional=false`), unless explicitly enabled (`optional=true` or `optional=yes`). The directive cannot be set to `true` on system-mandatory directories such as `workdir` and `outdir`.
* **Mechanism:** When an item is marked with `optional=true`, runtime handling across generated scripts operates as follows:
- **Passing `dummy`:** If the literal string `dummy` is supplied in place of the argument at runtime:
  - **Files and Directories:** The execution wrapper bypasses existence checks, skips file copying or container bind-mounting, and substitutes the corresponding `<name>` placeholder in the `usage=` command line with the literal word `dummy`.
  - **Parameters:** Value validation against the predefined `values=` constraint list is skipped, and the literal value `dummy` is passed directly to the execution invocation.
- **Passing a Valid Value:** If a real path or parameter string is supplied instead of `dummy`, standard validation logic applies (e.g., verifying file/directory presence on disk or checking parameter values against the allowed list).
- **Platform Support:** Runtime parsing via the `dummy` placeholder is supported natively in generated **Python**, **Bash**, and **R** scripts. For target platforms like **Nextflow** and  **Streamflow** the directive is either ignored during script generation or rendered purely as visual documentation in generated configuration comments, as these engines manage input optionality through their own runtime schemas.  **Galaxy** renders `optional="true"` on the corresponding `<param>` elements, but the generated `<command>` does not yet wrap their usage in conditionals.
* **Objective:** The primary goal of the `optional` keyword is to provide flexibility during pipeline execution. It allows users to omit non-essential inputs or parameters on demand without altering the root `.bala` file specification, modifying the `usage=` template, or generating separate platform configurations.

### 3. Support for Default Values via Keyword Integration

* **Description:** Implement a fallback mechanism that automatically resolves to predefined default values when a specific keyword is detected in the input parameters.
* **Mechanism:** the value set with `default=` on a `[parameter]` is used by every target: it pre-fills the parameter in the generated Nextflow (`params.<name>`), Streamflow (`<name>-params.yml`) and Galaxy (selected option or text field value) files, and it appears in the sample commands of Python, Bash and R. If `default=` is absent but `values=` is present, Nextflow and Streamflow fall back to the first listed value. In addition, in the generated **Python**, **Bash** and **R** scripts, when the literal word `default` is supplied as an argument at runtime, Baryon substitutes it with the configured `default=` value before validation.
* **Deprecation:** The legacy `value=` spelling is deprecated in favor of `default=` on `[parameter]` sections. It is automatically converted to `default=` (with a non-blocking warning) for backward compatibility; new `.bala` files should use `default=` directly. Specifying both `value=` and `default=` on the same `[parameter]` is a hard error.
* **Objective:** Simplify parameter management and execution commands by allowing users to explicitly request standard or fallback behaviors without needing to provide full definitions manually.

### 4. `quote` Keyword for Command-Line Argument Quoting

* **Description:** Add a `quote` keyword to `[file]`, `[directory]`, and `[parameter]` sections.
* **Mechanism:** `quote` accepts `true`/`yes`/`false`/`no` and defaults to `false`. When set to `true`, the corresponding value is wrapped in double quotes when substituted into the generated command line, ensuring it reaches the script as a single argument even if it contains spaces.
* **Objective:** Prevent values containing spaces (e.g. multi-word parameter values or paths) from being unintentionally split into multiple arguments by the shell, without `quote=true`, Nextflow, Streamflow and Galaxy never quote; Python and Bash still auto-quote `[parameter]` values containing spaces or shell-special characters, and R auto-quotes any such value (files and directories included).