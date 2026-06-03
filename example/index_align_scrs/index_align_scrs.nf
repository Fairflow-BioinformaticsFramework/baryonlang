nextflow.enable.dsl=2

/*
 * Pipeline: index_align_scrs
 * Description: Funzione per eseguire l'allineamento e l'indicizzazione
 */

// --- PARAMETERS ---
params.genome = "/path/to/directory/genome" // percorso cartella di lavoro, Genome
params.scratch = "/path/to/directory/scratch" // percorso cartella Data, qui viene salvato il log e andrebbero piazzati i file di output. Scratch
params.bamsave = "true" // Whether to save the BAM file  - Possible values: true, false

process INDEX_ALIGN_SCRS {
    container 'repbioinfo/carncellranger2'
    containerOptions "--volume ${params.genome}:/genome --volume ${params.scratch}:/scratch"


    script:
    """
    bash /home/index_align.sh ${params.bamsave}
    """
}

workflow {
    INDEX_ALIGN_SCRS()
}