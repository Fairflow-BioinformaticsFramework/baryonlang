nextflow.enable.dsl=2

/*
 * Pipeline: topx
 * Description: Filters a gene count matrix, selecting the most relevant genes by variance (using edgeR) or by total count.
 */

// --- PARAMETERS ---
params.workdir = "/path/to/directory/workdir" // Path to the working directory
params.data = "/path/to/directory/data" // Path to the folder containing input data and receiving output results
params.matrixname = "annotated" // Input file name without extension 
params.format = "csv" // Input file format  - Possible values: csv, txt
params.threshold = "10" // Threshold for selecting top genes (typically between 10 and 2000 depending on dataset size) 
params.separator = "," // File separator (use "," for CSV, "\t" for TSV)  - Possible values: ',','\t'
params.logged = "FALSE" // Indicates whether the count matrix values are already log-transformed (TRUE) or not (FALSE).  - Possible values: FALSE,TRUE
params.type = "expression" // Type of analysis to perform.  - Possible values: expression, variance

process TOPX {
    container 'repbioinfo/topxv2:1'
    containerOptions "--user \$(id -u):\$(id -g) --volume ${params.workdir}:/workdir --volume ${params.data}:/data"


    output:
    env 'N'

    script:
    """
    n=1
    while [ -d \"/workdir/scratch\$n\" ]; do
        n=`expr \$n + 1`
    done
    mkdir -p \"/workdir/scratch\$n\"
    mkdir -p "/data"
    data_src="${params.data}"
    data_base=\$(basename \"\$data_src\")
    mkdir -p \"/workdir/scratch\$n/\$data_base\"
    cp -r \"/data/.\" \"/workdir/scratch\$n/\$data_base/\"
    Rscript /bin/top.R ${params.matrixname} "${params.format}" "${params.separator}" ${params.logged} ${params.threshold} ${params.type} > /workdir/scratch\$n/output_log.txt 2>&1
    export N=\$n
    """
}

workflow {
    def scratchN = null

    TOPX()
    TOPX.out.subscribe { scratchN = it }

    workflow.onComplete = {
        def src = new File("${workflow.launchDir}/.nextflow.log")
        if (scratchN) {
            def dst = new File("${params.workdir}/scratch${scratchN}/nextflow.log")
            if (src.exists()) dst.text = src.text
        }
    }
}