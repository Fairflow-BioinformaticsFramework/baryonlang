nextflow.enable.dsl=2

/*
 * Pipeline: index_align_scrs
 * Description: Single-Cell RNA-Seq (scRNA-Seq) analysis. Tracks gene expression at single-cell level using cell barcodes.
 */

// --- PARAMETERS ---   index_align_scrs
params.workdir = "/home/baseolo/Baryon_SourceCode/test/testdata/index_align_scrs/workdir"
params.genome = "/home/baseolo/Baryon_SourceCode/test/testdata/index_align_scrs/Genome"
params.scratch = "/home/baseolo/Baryon_SourceCode/test/testdata/index_align_scrs/Data"
params.bamsave = "false" // optional, Whether to save the BAM file  - Possible values: true, false

process INDEX_ALIGN_SCRS {
    container 'repbioinfo/carncellranger2'
    containerOptions "--user \$(id -u):\$(id -g) --volume ${params.workdir}:/workDir --volume ${params.genome}:/genome --volume ${params.scratch}:/scratch"


    output:
    env 'N'

    script:
    """
    n=1
    while [ -d \"/workDir/scratch\$n\" ]; do
        n=`expr \$n + 1`
    done
    mkdir -p \"/workDir/scratch\$n\"
    mkdir -p "/genome"
    mkdir -p "/scratch"
    bash /home/index_align.sh ${params.bamsave} > /workDir/scratch\$n/output_log.txt 2>&1
    export N=\$n
    """
}

workflow {
    def scratchN = null

    INDEX_ALIGN_SCRS()
    INDEX_ALIGN_SCRS.out.subscribe { scratchN = it }

    workflow.onComplete = {
        def src = new File("${workflow.launchDir}/.nextflow.log")
        if (scratchN) {
            def dst = new File("${params.workdir}/scratch${scratchN}/nextflow.log")
            if (src.exists()) dst.text = src.text
        }
    }
}