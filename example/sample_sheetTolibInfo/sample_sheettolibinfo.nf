nextflow.enable.dsl=2

/*
 * Pipeline: sample_sheettolibinfo
 * Description: produce in output il file fof.txt e rof.txt nella cartella outdir
 */

// --- PARAMETERS ---
params.outdir = "/path/to/directory/outdir" // percorso cartella di output
params.xmlfile = "/path/to/file/xmlfile" // name del file xml
params.configtype = "HTGTS_mouse" // tipo di cellule  - Possible values: HTGTS_mouse,HTGTS_human,CELTICSseq,polyA

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