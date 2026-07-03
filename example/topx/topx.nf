nextflow.enable.dsl=2

/*
 * Pipeline: topx
 * Description: Filters a gene count matrix, selecting the most relevant genes by variance (using edgeR) or by total count.
 */

// --- PARAMETERS ---
params.data = "/path/to/directory/data" // Path to the folder containing input data and receiving output results
params.matrixname = "annotated" // Input file name without extension 
params.format = "csv" // Input file format  - Possible values: csv, txt
params.threshold = "10" // Threshold for selecting top genes (typically between 10 and 2000 depending on dataset size) 
params.separator = "," // File separator (use "," for CSV, "\t" for TSV)  - Possible values: ',','\t'
params.logged = "FALSE" // Indicates whether the count matrix values are already log-transformed (TRUE) or not (FALSE).  - Possible values: FALSE,TRUE
params.type = "expression" // Type of analysis to perform.  - Possible values: expression, variance

process TOPX {
    container 'repbioinfo/topxv2:1'
    containerOptions "--volume ${params.data}:/data"


    script:
    """
    Rscript /bin/top.R ${params.matrixname} ${params.format} ${params.separator} ${params.logged} ${params.threshold} ${params.type}
    """
}

workflow {
    TOPX()
}