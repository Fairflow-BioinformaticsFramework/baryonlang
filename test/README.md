# Baryon Test Suite

This folder contains everything needed to try Baryon without preparing your own data: sample `.bala` files, the scripts generated from them, ready-to-launch runner scripts, and small input datasets.

It documents how the generated scripts were tested on each supported platform (Python, Bash, R, Nextflow, Streamflow, Galaxy, Singularity/Apptainer), so you can reproduce the tests or use them as a worked example of the end-to-end workflow.

> **Note on placeholders.** The commands below use `<user>` and `<server-ip>` in place of the account name and IP address of the Linux server used for the tests, and `<repo-root>` for the folder where the repository was cloned. **Replace them with your own values** before running anything.

---

## Contents

- [Directory Structure](#directory-structure)
- [Test Workflows](#test-workflows)
- [Getting the Files](#getting-the-files)
- [Workflow Overview](#workflow-overview)
- [Running on Python, Bash and R](#running-on-python-bash-and-r)
- [Running on Streamflow](#running-on-streamflow)
- [Running on Nextflow](#running-on-nextflow)
- [Running on Galaxy](#running-on-galaxy)
- [Running with Singularity/Apptainer](#running-with-singularityapptainer)
- [Working on a Remote Server](#working-on-a-remote-server)

---

## Directory Structure

```
test/
├── bala_samples/         # Source .bala specification files and generated target files
│   ├── htgts_full/       #   HTGTS pipeline specifications (.bala, .nf, .sh, .py, .R, .cwl, .xml, ...)
│   ├── index_align_bulk_rna_seq/
│   ├── index_align_scrs/
│   ├── sample_sheettolibInfo/
│   ├── seqkit/
│   └── topx/
├── ready_to_run/         # Executable runner scripts configured for immediate testing
│   ├── htgts_full/       #   Pre-configured execution scripts (run_bash.sh, run_nextflow.sh, etc.)
│   ├── index_align_bulk_rna_seq/
│   ├── index_align_scrs/
│   ├── sample_sheettolibInfo/
│   ├── seqkit/
│   └── topx/
└── testdata/             # Input datasets, reference files, and execution working directories
    ├── htgts_full/       #   FASTQ samples, metadata (libseqInfo.txt), workdir, and outdir
    ├── index_align_bulk_rna_seq/
    ├── index_align_scrs/
    ├── sample_sheettolibInfo/
    ├── seqkit/
    └── topx/
```

| Folder | Purpose |
|---|---|
| `bala_samples/` | Reference material: for each experiment, the original `.bala` file and every script Baryon generates from it (not meant to be run as is). Useful as a model when writing your own `.bala` file. |
| `ready_to_run/` | Launchers and configuration files already adapted to the data in `testdata/`. This is where you start. |
| `testdata/` | Input files, reference data, and the `workdir`/`outdir` directories used by the runs. |

---

## Test Workflows

| Workflow | Description |
|---|---|
| `htgts_full` | Analyzes sequencing data to map genomic translocations or large-scale DNA break sites. Processes two FASTQ files and two `libseq` files from `workdir`; outputs to `outdir`. |
| `index_align_bulk_rna_seq` | Bulk RNA-Seq analysis. Measures average gene expression across a cell population. Expects FASTA and annotation files in `/genome/` and FASTQ reads in `/scratch/`. Both directories are read at fixed paths, so `copy=true` does not redirect the script to the copy on Nextflow/Streamflow (see the [limitation](../README.md#platform-support-matrix-for-copy)). The reference files must be downloaded first (see [Reference Data](#reference-data)). |
| `index_align_scrs` | Single-cell RNA-Seq (scRNA-Seq) analysis. Tracks gene expression at single-cell level using cell barcodes. Same input structure as Bulk RNA-Seq. The reference files must be downloaded first (see [Reference Data](#reference-data)). |
| `sample_sheettolibInfo` | Converts experiment metadata from an Excel spreadsheet into a `KEY=VALUE` format readable by downstream HTGTS Bash pipeline scripts. |
| `seqkit` | Toolkit for FASTA/FASTQ manipulation, filtering, and statistics. Used here as a lightweight test to validate **Singularity** container integration. |
| `topx` | Filters a gene count matrix, selecting the most relevant genes by variance (using edgeR) or by total count. Reads a CSV from `/data/` and writes results to the same folder. |

---

## Getting the Files

The whole repository was cloned for the tests, but only the `test/` folder is actually needed, since it contains all test files and scripts.

```bash
git clone https://github.com/Fairflow-BioinformaticsFramework/Baryonlang.git
```

To download only `test/` (optional, requires Git ≥ 2.25):

```bash
git clone --depth 1 --filter=blob:none --sparse https://github.com/Fairflow-BioinformaticsFramework/Baryonlang.git
cd Baryonlang
git sparse-checkout set test
```

Baryon itself must be installed to regenerate scripts from the `.bala` files; see the [Installation](../README.md#installation) section of the main README.


### Reference Data

The `index_align_bulk_rna_seq` and `index_align_scrs` workflows need the *Drosophila melanogaster* genome (FASTA) and annotation (GTF) in a `Genome` folder inside each workflow directory (created by the commands below). They are not included in the repository because of their size (about 146 MB and 167 MB). Download them from Ensembl (release 112) and copy them into both folders:

```bash
cd test/testdata
BASE=https://ftp.ensembl.org/pub/release-112
curl -O $BASE/fasta/drosophila_melanogaster/dna/Drosophila_melanogaster.BDGP6.46.dna.toplevel.fa.gz
curl -O $BASE/gtf/drosophila_melanogaster/Drosophila_melanogaster.BDGP6.46.112.gtf.gz
gunzip Drosophila_melanogaster.BDGP6.46.*.gz
for d in index_align_bulk_rna_seq index_align_scrs; do
  mkdir -p "$d/Genome"
  cp Drosophila_melanogaster.BDGP6.46.* "$d/Genome/"
done
rm Drosophila_melanogaster.BDGP6.46.*
```

On Windows, use WSL or extract the `.gz` files with 7-Zip.

---

## Workflow Overview

For every platform the procedure is the same:

1. **Generate** the target files from a `.bala` file (already done for you in `bala_samples/`):
   ```bash
   baryon <name>.bala --lang all --overwrite
   ```
2. **Adjust** the generated files: parameter values, and the **full (absolute) paths** of input files and directories.
3. **Launch** the workflow through the platform-specific runner in `ready_to_run/<workflow>/`.

Some platforms need extra configuration, described in the sections below.

> **Absolute paths.** File and directory paths in the generated Streamflow/Nextflow files must be complete, starting from the filesystem root. For example:
> `/home/<user>/<repo-root>/test/testdata/htgts_full/filtered_JT8572_S1_R1_001.fastq`

---

## Running on Python, Bash and R

For testing, simple wrapper scripts (`run_python.sh`, `run_bash.sh`, `run_R.sh`) were written. They call the script generated by Baryon and pass **constant arguments**, so that parameters do not have to be retyped at every run.

1. Enter the workflow folder in `ready_to_run/`.
2. Adjust the parameters inside the wrapper if needed.
3. Launch the wrapper:
   ```bash
   ./run_bash.sh
   ```

---

## Running on Streamflow

**Files produced by Baryon:** `<name>.cwl`, `<name>.yml`, `<name>-params.yml`.

1. Edit `<name>-params.yml`: set the parameter values and the file paths, using the comments in the file as a guide.
2. Edit `<name>.yml`: set the host paths of the directories to mount.
3. If a directory has `copy=yes`, Baryon adds a `<dirname>_origin_name` parameter to `<name>-params.yml`. Set it to the **basename** of the folder configured for `<dirname>` in `<name>.yml` (for example `Genome` for `/data/project/Genome`). This is required because Streamflow cannot access the real path of a mounted volume and therefore cannot determine it at runtime.
4. In the folder containing the `.yml` and `.cwl` files, edit `run_streamflow.sh`, replacing `/common/base/path` with the **initial part of your actual path**. The path must be **identical on both sides of the `:`**, which mounts the volume under exactly the same name as the original.
   - It is enough to mount the common parent folder if all files and directories are its subfolders (for example `/home/<user>/<repo-root>`).
   - If paths start from different roots, mount each root separately.
5. Launch:
   ```bash
   ./run_streamflow.sh
   ```

---

## Running on Nextflow

**Files produced by Baryon:** `<name>.nf`, `nextflow.config`, and a sample launch command in `<name>_command.txt`.

1. Edit the `.nf` file: adjust the parameters and, above all, set the **full path** of every directory. The same paths must be used in the Docker launch command (see below).
2. Launch the workflow in one of two ways:
   - **Native Nextflow.** Install Nextflow on the server and run it directly (after fixing parameters and folders):
     ```bash
     nextflow run <name>.nf
     ```
   - **Dockerized Nextflow.** Use the almost-complete command found in `<name>_command.txt`. For testing, it is wrapped in `run_nextflow.sh`: in the folder containing the `.nf` file, replace `/common/base/path` with the initial part of your actual path (identical on both sides of the `:`) and run:
     ```bash
     ./run_nextflow.sh
     ```
3. Check the results:
   - Each run creates a random subfolder inside `work/` (Nextflow's task directory).
   - The logs worth reading are in the numbered `scratchN` subfolder of the mounted `workdir`: `output_log.txt` (stdout and stderr of the script run in the container) and `nextflow.log` (copy of the Nextflow log, added when the workflow completes).

---

## Running on Galaxy

**File produced by Baryon:** `<name>.xml` (and `<name>_targz.xml` when the workflow has input directories).

Tests were performed on a local Galaxy instance based on the [`galaxy-formed`](https://github.com/Fairflow-BioinformaticsFramework/galaxy-formed) project.

### 1. Start the Galaxy environment

On the Linux server, from your home directory, create (or enter) a `github` folder and run the following commands. **Write permissions are required** (for example `sudo -i`).

```bash
git clone https://github.com/Fairflow-BioinformaticsFramework/galaxy-formed.git
cd galaxy-formed
docker compose up -d
```

To rebuild the containers after changes:

```bash
docker compose up -d --build --force-recreate
```

### 2. Load the tool

1. Open **Lemaitre** at `http://<server-ip>:8081` and upload the XML file generated by Baryon.
2. Open **Galaxy** at `http://<server-ip>:8080`.
3. Select the uploaded experiment from the **custom functions** tool section.

### 3. Upload data and run

1. Click **Upload**, choose the input files, click **Start**, then **Close**.
2. Associate the files with the tool parameters, pick parameter values from the dropdown menus, and click **Run tool**.

> **Important:** for `.gz` files, specify the type **`tar.gz`** during upload instead of leaving *auto-detect*.

### Preparing directory inputs

Galaxy receives directories either as a collection or as a `tar.gz` archive (hence the two XML variants).

**Creating a collection from a directory:**

1. Upload all files from the directory.
2. Enable the selection checkbox and select all files.
3. Choose **Advanced build list** from the dropdown.
4. Select **flat list** and **disable** the option to strip file extensions, then click **Next**.
5. Name the collection after the source directory.

**Creating a `tar.gz` from a directory** (Linux and Windows):

```bash
tar -czf genome.tar.gz -C genome .
```

---

## Running with Singularity/Apptainer

Workflows whose `.bala` uses Singularity (for example `seqkit`) generate only the **Python, Bash and R** scripts; Galaxy, Nextflow and Streamflow files are not produced.

### One-time setup (Linux)

Singularity is now called Apptainer. If it is not installed:

```bash
sudo apt install apptainer
sudo apt update && sudo apt install -y squashfuse fuse3
sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0
```

Then configure temporary and cache directories:

```bash
mkdir -p ~/.apptainer/tmp ~/.apptainer/cache
echo 'export APPTAINER_TMPDIR=~/.apptainer/tmp' >> ~/.bashrc
echo 'export APPTAINER_CACHEDIR=~/.apptainer/cache' >> ~/.bashrc
source ~/.bashrc
```

### Run

Enter the folder containing the generated scripts, adjust the parameters, and launch `run_python.sh`, `run_bash.sh` or `run_R.sh` (see [Running on Python, Bash and R](#running-on-python-bash-and-r)).

---

## Working on a Remote Server

The tests were run on a Linux server accessed over SSH. A persistent terminal session keeps long runs alive after disconnecting:

```bash
ssh -t <user>@<server-ip> "tmux a || tmux new"
```

This attaches to an existing `tmux` session, or creates a new one if none exists.

**Copying text from the terminal:** hold **Shift**, select the text with the mouse as usual, press **Ctrl+C**, and then release **Shift**. (Holding Shift bypasses the terminal multiplexer's own mouse handling.)
