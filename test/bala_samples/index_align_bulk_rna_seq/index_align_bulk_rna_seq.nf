nextflow.enable.dsl=2

/*
 * Pipeline: index_align_bulk_rna_seq
 * Description: Bulk RNA-Seq analysis. Measures average gene expression across a cell population.
 */

// --- PARAMETERS ---
params.workdir = "/path/to/directory/workdir" // working directory path
params.genome = "/path/to/directory/genome" // optional, genome directory path
params.scratch = "/path/to/directory/scratch" // scratch directory path(Data)

process INDEX_ALIGN_BULK_RNA_SEQ {
    container 'repbioinfo/rnaseqstar_v2'
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
    genome_src="${params.genome}"
    genome_base=\$(basename \"\$genome_src\")
    mkdir -p \"/workDir/scratch\$n/\$genome_base\"
    cp -r \"/genome/.\" \"/workDir/scratch\$n/\$genome_base/\"
    /home/index_align.sh  > /workDir/scratch\$n/output_log.txt 2>&1
    export N=\$n
    """
}

workflow {
    def scratchN = null

    INDEX_ALIGN_BULK_RNA_SEQ()
    INDEX_ALIGN_BULK_RNA_SEQ.out.subscribe { scratchN = it }

    workflow.onComplete = {
        def src = new File("${workflow.launchDir}/.nextflow.log")
        if (scratchN) {
            def dst = new File("${params.workdir}/scratch${scratchN}/nextflow.log")
            if (src.exists()) dst.text = src.text
        }
    }
}