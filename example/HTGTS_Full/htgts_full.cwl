cwlVersion: v1.2
class: CommandLineTool
baseCommand: [bash, elabora.sh]
stdout: output_log.txt 
requirements:
  ShellCommandRequirement: {}
  InitialWorkDirRequirement:
    listing:
      - entryname: elabora.sh
        entry: |
          #!/bin/bash
          n=1
          while [ -d "/workDir/scratch$n" ]; do
            n=`expr $n + 1`
          done
          mkdir -p "/workDir/scratch$n"
          mkdir -p "/outDir/scratch$n"
          /Algorithm/HTGTS_Full.sh -fastq1 $(inputs.fastq1.path) -fastq2 $(inputs.fastq2.path) -expInfo $(inputs.expinfo.path) -expInfo2 $(inputs.expinfo2.path) -outDir /outDir/scratch$n -configType $(inputs.configtype) -assembly $(inputs.assembly) &&
          cp output_log.txt /workDir/scratch$n/output_log.txt &&
          rm output_log.txt
        writable: false
inputs:
  fastq1:
    type: File
  fastq2:
    type: File
  expinfo:
    type: File
  expinfo2:
    type: File
  configtype:
    type: string
  assembly:
    type: string
outputs: []