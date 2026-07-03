nextflow.enable.dsl=2

/*
 * Pipeline: htgts_full
 * Description: analyze sequencing data and map genomic translocations or DNA break sites on a large scale
 */

// --- PARAMETERS ---
params.outdir = "/path/to/directory/outdir" // output directory path
params.fastq1 = "/path/to/file/fastq1" // the first input FASTQ file name
params.fastq2 = "/path/to/file/fastq2" // the second input FASTQ file name
params.expinfo = "/path/to/file/expinfo" // name of the libseqInfo.txt file
params.expinfo2 = "/path/to/file/expinfo2" // name of the libseqInfo2.txt file
params.configtype = "HTGTS_human" // cell type  - Possible values: HTGTS_human,HTGTS_mouse,CELTICSseq,polyA
params.assembly = "hg38" // reference genome version  - Possible values: hg38,mm9,mm10,custom

process HTGTS_FULL {
    container 'repbioinfo/htgts_pipeline_lts_v16:latest'
    containerOptions "--volume ${params.outdir}:/outDir"


    input:
    path fastq1
    path fastq2
    path expinfo
    path expinfo2

    script:
    """
    /Algorithm/HTGTS_Full.sh -fastq1 ${fastq1} -fastq2 ${fastq2} -expInfo ${expinfo} -expInfo2 ${expinfo2} -outDir ${params.outdir} -configType ${params.configtype} -assembly ${params.assembly}
    """
}

workflow {
    fastq1 = Channel.fromPath(params.fastq1)
    fastq2 = Channel.fromPath(params.fastq2)
    expinfo = Channel.fromPath(params.expinfo)
    expinfo2 = Channel.fromPath(params.expinfo2)
    HTGTS_FULL(fastq1, fastq2, expinfo, expinfo2)
}