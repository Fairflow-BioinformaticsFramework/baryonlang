nextflow.enable.dsl=2

/*
 * Pipeline: sample_sheettolibinfo
 * Description: Converts experiment metadata from an Excel spreadsheet into a KEY=VALUE format readable by downstream HTGTS Bash pipeline scripts.
 */

// --- PARAMETERS ---
params.workdir = "/path/to/directory/workdir" // working directory path
params.outdir = "/path/to/directory/outdir" // output directory path
params.xmlfile = "/path/to/file/xmlfile" // name of the xml file
params.configtype = "HTGTS_mouse" // cell type  - Possible values: HTGTS_human,HTGTS_mouse,CELTICSseq,polyA

process SAMPLE_SHEETTOLIBINFO {
    container 'repbioinfo/htgts_pipeline_lts_v16:latest'
    containerOptions "--user \$(id -u):\$(id -g) --volume ${params.workdir}:/workingdir --volume ${params.outdir}:/outDir"


    input:
    path xmlfile

    output:
    env 'N'

    script:
    """
    n=1
    while [ -d \"/workingdir/scratch\$n\" ]; do
        n=`expr \$n + 1`
    done
    mkdir -p \"/workingdir/scratch\$n\"
    mkdir -p \"/outDir/output\$n\"
    cp \"${xmlfile}\" \"/workingdir/scratch\$n/${xmlfile.name}\"
    python3 /Algorithm/sample_sheetTolibInfo.py /workingdir/scratch\$n/${xmlfile.name} /outDir/output\$n/fof.txt /outDir/output\$n/rof.txt ${params.configtype} > /workingdir/scratch\$n/output_log.txt 2>&1
    export N=\$n
    """
}

workflow {
    def scratchN = null

    xmlfile = Channel.fromPath(params.xmlfile)
    SAMPLE_SHEETTOLIBINFO(xmlfile)
    SAMPLE_SHEETTOLIBINFO.out.subscribe { scratchN = it }

    workflow.onComplete = {
        def src = new File("${workflow.launchDir}/.nextflow.log")
        if (scratchN) {
            def dst = new File("${params.workdir}/scratch${scratchN}/nextflow.log")
            if (src.exists()) dst.text = src.text
        }
    }
}