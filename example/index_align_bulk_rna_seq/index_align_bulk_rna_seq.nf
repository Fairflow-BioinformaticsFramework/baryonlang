nextflow.enable.dsl=2

/*
 * Pipeline: index_align_bulk_rna_seq
 * Description: Funzione per eseguire l'allineamento e l'indicizzazione
 */

// --- PARAMETERS ---
params.genome = "/path/to/directory/genome" // percorso cartella di lavoro, Genome
params.scratch = "/path/to/directory/scratch" // percorso cartella Data, qui viene salvato il log e andrebbero piazzati i file di output. Scratch

process INDEX_ALIGN_BULK_RNA_SEQ {
    container 'repbioinfo/rnaseqstar_v2'
    containerOptions "--volume ${params.genome}:/genome --volume ${params.scratch}:/scratch"


    script:
    """
    /home/index_align.sh 
    """
}

workflow {
    INDEX_ALIGN_BULK_RNA_SEQ()
}