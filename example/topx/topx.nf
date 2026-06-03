nextflow.enable.dsl=2

/*
 * Pipeline: topx
 * Description: Seleziona i geni con i valori più alti secondo una metrica scelta (espressione o varianza) e restituisce solo i top X dalla matrice di conteggi.
 */

// --- PARAMETERS ---
params.data = "/path/to/directory/data" // percorso cartella contenente i dati e ricevente i risultati
params.matrixname = "annotated" // name del file di input senza estensione 
params.format = "csv" // formato del file di input  - Possible values: csv, txt
params.threshold = "10" // Soglia per selezionare i geni top (solitamente fra 10 e 2000 a seconda delle dimensioni del datase) 
params.separator = "," // Separatore del file (Separatore usato nel file Usare "," per CSV, "\t" per TSV)  - Possible values: ',','\t'
params.logged = "FALSE" // Indica se i valori della matrice di conteggi sono già log‑trasformati (TRUE) oppure no (FALSE).  - Possible values: FALSE,TRUE
params.type = "expression" // Tipo di analisi da eseguire.  - Possible values: expression, variance

process TOPX {
    container 'repbioinfo/topxv2:1'
    containerOptions "--volume ${params.data}:/data"


    script:
    """
    Rscript /bin/top.R ${params.matrixname} ${params.format} ${params.separator} ${params.logged} ${params.threshold} ${params.type}
    """
}

workflow {
    TOPX()
}