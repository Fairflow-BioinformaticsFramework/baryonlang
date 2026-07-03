# Future Developments for Baryon

This document outlines planned implementations and enhancements for the Baryon DSL and framework.

## 1. Directory Support for Copy Operations (Tracking via Workdir/Scratch)

* **Description:** Extend the existing file-based tracking and caching mechanism to support entire directories.
* **Details:** Implement a `copy`-like parameter specifically for directories. When invoked, the target directory will be fully copied into the `workdir` or designated `scratch` space for each execution.
* **Objective:** Ensure that directory contents leave a distinct, traceable provenance trail for every pipeline execution, mirroring the behavior currently available for individual files.

## 2. Optional Parameters, Files, and Directories (Usage and Conditional Execution)

* **Description:** Introduce support for optional inputs (parameters, files, and directories) using a standardized conditional syntax.
* **Syntax Concept:** Aligning with the standard `.bala` usage specification format:

        [-a <filexx>]

* **Mechanism:** The entire instruction block or argument sequence associated with the optional element will only be considered and evaluated if a valid value is provided for `filexx`.

  If the optional parameter is omitted or missing during invocation, the framework will automatically inject the `dummy` keyword as a placeholder/filler value to maintain the expected parameter alignment and positional consistency.

## 3. Support for Default Values via Keyword Integration

* **Description:** Implement a fallback mechanism that automatically resolves to predefined default values when a specific keyword is detected in the input parameters.
* **Mechanism:** When the framework encounters the `default` keyword as an argument or parameter value during invocation, Baryon will intercept it and substitute it with the corresponding configuration-defined or context-aware `value`.
* **Objective:** Simplify parameter management and execution commands by allowing users to explicitly request standard or fallback behaviors without needing to provide full definitions manually.