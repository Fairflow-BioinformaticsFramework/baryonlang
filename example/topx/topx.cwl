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
          while [ -d "/workdir/scratch$n" ]; do
            n=`expr $n + 1`
          done
          mkdir -p "/workdir/scratch$n"
          mkdir -p "/data"
          Rscript /bin/top.R $(inputs.matrixname) $(inputs.format) $(inputs.separator) $(inputs.logged) $(inputs.threshold) $(inputs.type) &&
          cp output_log.txt /workdir/scratch$n/output_log.txt &&
          rm output_log.txt
        writable: false
inputs:
  matrixname:
    type: string
  format:
    type: string
  threshold:
    type: string
  separator:
    type: string
  logged:
    type: string
  type:
    type: string
outputs: []