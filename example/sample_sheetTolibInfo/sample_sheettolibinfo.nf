nextflow.enable.dsl=2

/*
 * Pipeline: sample_sheettolibinfo
 * Description: Converts experiment metadata from an Excel spreadsheet into a KEY=VALUE format readable by downstream HTGTS Bash pipeline scripts.
 */

// --- PARAMETERS ---
params.outdir = "/path/to/directory/outdir" // output directory path
params.xmlfile = "/path/to/file/xmlfile" // name of the xml file
params.configtype = "HTGTS_mouse" // cell type  - Possible values: HTGTS_mouse,HTGTS_human,CELTICSseq,polyA

process SAMPLE_SHEETTOLIBINFO {
    container 'repbioinfo/htgts_pipeline_lts_v16:latest'
    containerOptions "--volume ${params.outdir}:/outDir"


    input:
    path xmlfile

    script:
    """
    python3 /Algorithm/sample_sheetTolibInfo.py ${xmlfile} ${params.outdir}/fof.txt ${params.outdir}/rof.txt ${params.configtype}
    """
}

workflow {
    xmlfile = Channel.fromPath(params.xmlfile)
    SAMPLE_SHEETTOLIBINFO(xmlfile)
}