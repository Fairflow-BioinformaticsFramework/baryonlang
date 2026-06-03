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
          python3 /Algorithm/sample_sheetTolibInfo.py $(inputs.xmlfile.path) /outDir/scratch$n/fof.txt /outDir/scratch$n/rof.txt $(inputs.configtype) &&
          cp output_log.txt /workDir/scratch$n/output_log.txt &&
          rm output_log.txt
        writable: false
inputs:
  xmlfile:
    type: File
  configtype:
    type: string
outputs: []