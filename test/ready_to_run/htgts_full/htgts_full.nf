nextflow.enable.dsl=2

/*
 * Pipeline: htgts_full
 * Description: analyze sequencing data and map genomic translocations or DNA break sites on a large scale
 */

// --- PARAMETERS ---
params.workdir = "/home/baseolo/Baryon_SourceCode/test/testdata/htgts_full/workdir" // working directory path
params.outdir = "/home/baseolo/Baryon_SourceCode/test/testdata/htgts_full/outdir" // output directory path
params.fastq1 = "/home/baseolo/Baryon_SourceCode/test/testdata/htgts_full/filtered_JT8572_S1_R1_001.fastq"   // the first input FASTQ file name
params.fastq2 = "/home/baseolo/Baryon_SourceCode/test/testdata/htgts_full/filtered_JT8572_S1_R2_001.fastq" // optional, the second input FASTQ file name
params.expinfo = "/home/baseolo/Baryon_SourceCode/test/testdata/htgts_full/libseqInfo.txt" // name of the libseqInfo.txt file
params.expinfo2 = "/home/baseolo/Baryon_SourceCode/test/testdata/htgts_full/libseqInfo2.txt" // name of the libseqInfo2.txt file
params.configtype = "HTGTS_human" // optional, cell type  - Possible values: HTGTS_human,HTGTS_mouse,CELTICSseq,polyA
params.assembly = "hg38" // reference genome version  - Possible values: hg38,mm9,mm10,custom

process HTGTS_FULL {
    container 'repbioinfo/htgts_pipeline_lts_v16:latest'
    containerOptions "--user \$(id -u):\$(id -g) --volume ${params.workdir}:/workDir --volume ${params.outdir}:/outDir"


    input:
    path fastq1
    path fastq2
    path expinfo
    path expinfo2

    output:
    env 'N'

    script:
    """
    n=1
    while [ -d \"/workDir/scratch\$n\" ]; do
        n=`expr \$n + 1`
    done
    mkdir -p \"/workDir/scratch\$n\"
    mkdir -p \"/outDir/output\$n\"
    cp \"${fastq1}\" \"/workDir/scratch\$n/${fastq1.name}\"
    cp \"${fastq2}\" \"/workDir/scratch\$n/${fastq2.name}\"
    /Algorithm/HTGTS_Full.sh -fastq1 /workDir/scratch\$n/${fastq1.name} -fastq2 /workDir/scratch\$n/${fastq2.name} -expInfo ${expinfo} -expInfo2 ${expinfo2} -outDir /outDir/output\$n -configType ${params.configtype} -assembly ${params.assembly} > /workDir/scratch\$n/output_log.txt 2>&1
    export N=\$n
    """
}

workflow {
    def scratchN = null

    fastq1 = Channel.fromPath(params.fastq1)
    fastq2 = Channel.fromPath(params.fastq2)
    expinfo = Channel.fromPath(params.expinfo)
    expinfo2 = Channel.fromPath(params.expinfo2)
    HTGTS_FULL(fastq1, fastq2, expinfo, expinfo2)
    HTGTS_FULL.out.subscribe { scratchN = it }

    workflow.onComplete = {
        def src = new File("${workflow.launchDir}/.nextflow.log")
        if (scratchN) {
            def dst = new File("${params.workdir}/scratch${scratchN}/nextflow.log")
            if (src.exists()) dst.text = src.text
        }
    }
}