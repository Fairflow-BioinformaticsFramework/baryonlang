nextflow.enable.dsl=2

/*
 * Pipeline: index_align_bulk_rna_seq
 * Description: Bulk RNA-Seq analysis. Measures average gene expression across a cell population.
 */

// --- PARAMETERS ---
params.genome = "/path/to/directory/genome" // genome directory path
params.scratch = "/path/to/directory/scratch" // scratch directory path(Data)

process INDEX_ALIGN_BULK_RNA_SEQ {
    container 'repbioinfo/rnaseqstar_v2'
    containerOptions "--volume ${params.genome}:/genome --volume ${params.scratch}:/scratch"


    script:
    """
    /home/index_align.sh 
    """
}

workflow {
    INDEX_ALIGN_BULK_RNA_SEQ()
}