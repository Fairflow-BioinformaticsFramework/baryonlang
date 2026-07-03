nextflow.enable.dsl=2

/*
 * Pipeline: index_align_scrs
 * Description: Single-Cell RNA-Seq (scRNA-Seq) analysis. Tracks gene expression at single-cell level using cell barcodes.
 */

// --- PARAMETERS ---
params.genome = "/path/to/directory/genome" // working directory path, Genome
params.scratch = "/path/to/directory/scratch" // Data directory path
params.bamsave = "true" // Whether to save the BAM file  - Possible values: true, false

process INDEX_ALIGN_SCRS {
    container 'repbioinfo/carncellranger2'
    containerOptions "--volume ${params.genome}:/genome --volume ${params.scratch}:/scratch"


    script:
    """
    bash /home/index_align.sh ${params.bamsave}
    """
}

workflow {
    INDEX_ALIGN_SCRS()
}