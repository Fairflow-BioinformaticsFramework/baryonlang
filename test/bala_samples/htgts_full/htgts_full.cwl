cwlVersion: v1.2
class: CommandLineTool
baseCommand: [bash, wrapper.sh]
stdout: output_log.txt 
requirements:
  ShellCommandRequirement: {}
  InitialWorkDirRequirement:
    listing:
      - entryname: wrapper.sh
        entry: |
          #!/bin/bash
          n=1
          while [ -d "/workDir/scratch$n" ]; do
            n=`expr $n + 1`
          done
          mkdir -p "/workDir/scratch$n"
          mkdir -p "/outDir/output$n"
          cp "$(inputs.fastq1.path)" "/workDir/scratch$n/$(inputs.fastq1.basename)"
          cp "$(inputs.fastq2.path)" "/workDir/scratch$n/$(inputs.fastq2.basename)"
          /Algorithm/HTGTS_Full.sh -fastq1 /workDir/scratch$n/$(inputs.fastq1.basename) -fastq2 /workDir/scratch$n/$(inputs.fastq2.basename) -expInfo $(inputs.expinfo.path) -expInfo2 $(inputs.expinfo2.path) -outDir /outDir/output$n -configType $(inputs.configtype) -assembly $(inputs.assembly)
          exit_code=$?
          cp output_log.txt /workDir/scratch$n/output_log.txt
          cp wrapper.sh "/workDir/scratch$n/wrapper.sh"
          exit $exit_code
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